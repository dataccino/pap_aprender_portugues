"""
Tests for generate_stories.py

Run with:
    pytest test_generate_stories.py -v
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import generate_stories
from generate_stories import (
    A1A2_CHAPTERS,
    B1_CHAPTERS,
    GENRES,
    SYSTEM_PROMPT,
    build_user_prompt,
    generate_from_file,
    generate_story,
    main,
    parse_prompt_file,
    save_story,
)

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

CHAPTER = {
    "id": "A1-1",
    "title": "Identificação e Dados Pessoais",
    "grammar": [
        "Pronomes pessoais, interrogativos, reflexivos",
        "Verbos ser, ter, morar em — Presente do Indicativo",
    ],
    "objectives": ["Identificar-se a si e ao outro"],
}

GENRE = {
    "name": "Absurdist Comedy",
    "description": "Kafka-meets-Machado de Assis absurdism.",
}


def _make_mock_client(story_text="GENERATED STORY"):
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text=story_text)]
    client.messages.create.return_value = msg
    return client


# ---------------------------------------------------------------------------
# INDEX.md helpers
# ---------------------------------------------------------------------------

def _data_rows(output_dir: Path) -> list[str]:
    """Return the data rows (non-header, non-separator) from INDEX.md."""
    text = (output_dir / "INDEX.md").read_text(encoding="utf-8")
    return [
        line for line in text.splitlines()
        if line.startswith("| ") and "Chapter" not in line and "---" not in line
    ]


def _count_index_rows(output_dir: Path) -> int:
    return len(_data_rows(output_dir))


def _index_genres(output_dir: Path) -> list[str]:
    genres = []
    for line in _data_rows(output_dir):
        cols = [c.strip() for c in line.split("|")]
        # cols: ["", Chapter, Title, Genre, File, ""]
        genres.append(cols[3])
    return genres


# ---------------------------------------------------------------------------
# 1. build_user_prompt
# ---------------------------------------------------------------------------

class TestBuildUserPrompt:
    def test_contains_chapter_id(self):
        assert "A1-1" in build_user_prompt(CHAPTER, GENRE, "A1/A2")

    def test_contains_chapter_title(self):
        assert CHAPTER["title"] in build_user_prompt(CHAPTER, GENRE, "A1/A2")

    def test_contains_book_level(self):
        assert "A1/A2" in build_user_prompt(CHAPTER, GENRE, "A1/A2")

    def test_grammar_formatted_as_bullets(self):
        prompt = build_user_prompt(CHAPTER, GENRE, "A1/A2")
        for item in CHAPTER["grammar"]:
            assert f"  - {item}" in prompt

    def test_objectives_formatted_as_bullets(self):
        prompt = build_user_prompt(CHAPTER, GENRE, "A1/A2")
        for item in CHAPTER["objectives"]:
            assert f"  - {item}" in prompt

    def test_contains_genre_name(self):
        assert GENRE["name"] in build_user_prompt(CHAPTER, GENRE, "A1/A2")

    def test_contains_genre_description(self):
        assert GENRE["description"] in build_user_prompt(CHAPTER, GENRE, "A1/A2")

    def test_no_inspiration_block_when_empty_string(self):
        assert "Story inspiration" not in build_user_prompt(CHAPTER, GENRE, "A1/A2", inspiration="")

    def test_no_inspiration_block_when_whitespace_only(self):
        assert "Story inspiration" not in build_user_prompt(CHAPTER, GENRE, "A1/A2", inspiration="   \n\t  ")

    def test_inspiration_block_included_when_provided(self):
        prompt = build_user_prompt(CHAPTER, GENRE, "A1/A2", inspiration="Ana encontra um pássaro.")
        assert "Story inspiration" in prompt
        assert "Ana encontra um pássaro." in prompt

    def test_inspiration_is_stripped(self):
        prompt = build_user_prompt(CHAPTER, GENRE, "A1/A2", inspiration="  Some plot seed  ")
        assert "  Some plot seed  " not in prompt
        assert "Some plot seed" in prompt

    def test_multiple_grammar_points_all_appear(self):
        chapter = dict(CHAPTER, grammar=["Point A", "Point B", "Point C"])
        prompt = build_user_prompt(chapter, GENRE, "A1/A2")
        for point in ["Point A", "Point B", "Point C"]:
            assert f"  - {point}" in prompt


# ---------------------------------------------------------------------------
# 2. generate_story
# ---------------------------------------------------------------------------

class TestGenerateStory:
    def test_dry_run_returns_user_prompt(self):
        result = generate_story(None, CHAPTER, GENRE, "A1/A2", dry_run=True)
        assert result == build_user_prompt(CHAPTER, GENRE, "A1/A2")

    def test_dry_run_contains_chapter_id_in_return(self):
        result = generate_story(None, CHAPTER, GENRE, "A1/A2", dry_run=True)
        assert "A1-1" in result

    def test_dry_run_prints_header(self, capsys):
        generate_story(None, CHAPTER, GENRE, "A1/A2", dry_run=True)
        out = capsys.readouterr().out
        assert "DRY RUN" in out
        assert CHAPTER["id"] in out
        assert CHAPTER["title"] in out

    def test_prompts_only_returns_user_prompt(self):
        result = generate_story(None, CHAPTER, GENRE, "A1/A2", prompts_only=True)
        assert result == build_user_prompt(CHAPTER, GENRE, "A1/A2")

    def test_prompts_only_does_not_print_generating(self, capsys):
        generate_story(None, CHAPTER, GENRE, "A1/A2", prompts_only=True)
        assert "Generating" not in capsys.readouterr().out

    def test_live_path_calls_messages_create(self):
        client = _make_mock_client()
        generate_story(client, CHAPTER, GENRE, "A1/A2")
        assert client.messages.create.called

    def test_live_path_uses_correct_model(self):
        client = _make_mock_client()
        generate_story(client, CHAPTER, GENRE, "A1/A2")
        assert client.messages.create.call_args.kwargs["model"] == "claude-sonnet-4-6"

    def test_live_path_uses_correct_max_tokens(self):
        client = _make_mock_client()
        generate_story(client, CHAPTER, GENRE, "A1/A2")
        assert client.messages.create.call_args.kwargs["max_tokens"] == 3000

    def test_live_path_passes_system_prompt(self):
        client = _make_mock_client()
        generate_story(client, CHAPTER, GENRE, "A1/A2")
        assert client.messages.create.call_args.kwargs["system"] == SYSTEM_PROMPT

    def test_live_path_passes_user_message(self):
        client = _make_mock_client()
        generate_story(client, CHAPTER, GENRE, "A1/A2")
        messages = client.messages.create.call_args.kwargs["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert "A1-1" in messages[0]["content"]

    def test_live_path_returns_api_text(self):
        assert generate_story(_make_mock_client("STORY TEXT"), CHAPTER, GENRE, "A1/A2") == "STORY TEXT"

    def test_live_path_prints_generating_and_checkmark(self, capsys):
        generate_story(_make_mock_client(), CHAPTER, GENRE, "A1/A2")
        out = capsys.readouterr().out
        assert "Generating" in out
        assert "✓" in out

    def test_inspiration_in_dry_run_return(self):
        result = generate_story(None, CHAPTER, GENRE, "A1/A2", dry_run=True, inspiration="Uma tempestade de papel.")
        assert "Uma tempestade de papel." in result

    def test_inspiration_appears_in_live_api_messages(self):
        client = _make_mock_client()
        generate_story(client, CHAPTER, GENRE, "A1/A2", inspiration="Uma tempestade de papel.")
        content = client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "Uma tempestade de papel." in content


# ---------------------------------------------------------------------------
# 3. save_story
# ---------------------------------------------------------------------------

class TestSaveStory:
    def _md_path(self, tmp_path):
        safe_id = CHAPTER["id"].replace("/", "-")
        safe_genre = GENRE["name"].lower().replace(" / ", "-").replace(" ", "-")
        return tmp_path / f"{safe_id}_{safe_genre}.md"

    def _txt_path(self, tmp_path):
        safe_id = CHAPTER["id"].replace("/", "-")
        safe_genre = GENRE["name"].lower().replace(" / ", "-").replace(" ", "-")
        return tmp_path / f"{safe_id}_{safe_genre}.txt"

    def test_creates_md_file(self, tmp_path):
        save_story("CONTENT", CHAPTER, GENRE, tmp_path)
        assert self._md_path(tmp_path).exists()

    def test_returns_md_filepath(self, tmp_path):
        assert save_story("CONTENT", CHAPTER, GENRE, tmp_path) == self._md_path(tmp_path)

    def test_frontmatter_starts_with_dashes(self, tmp_path):
        save_story("CONTENT", CHAPTER, GENRE, tmp_path)
        assert self._md_path(tmp_path).read_text(encoding="utf-8").startswith("---\n")

    def test_frontmatter_chapter_field(self, tmp_path):
        save_story("CONTENT", CHAPTER, GENRE, tmp_path)
        assert f"chapter: {CHAPTER['id']}" in self._md_path(tmp_path).read_text(encoding="utf-8")

    def test_frontmatter_title_field(self, tmp_path):
        save_story("CONTENT", CHAPTER, GENRE, tmp_path)
        assert f"title: {CHAPTER['title']}" in self._md_path(tmp_path).read_text(encoding="utf-8")

    def test_frontmatter_genre_field(self, tmp_path):
        save_story("CONTENT", CHAPTER, GENRE, tmp_path)
        assert f"genre: {GENRE['name']}" in self._md_path(tmp_path).read_text(encoding="utf-8")

    def test_frontmatter_grammar_is_valid_json(self, tmp_path):
        save_story("CONTENT", CHAPTER, GENRE, tmp_path)
        text = self._md_path(tmp_path).read_text(encoding="utf-8")
        line = next(l for l in text.splitlines() if l.startswith("grammar: "))
        assert json.loads(line[len("grammar: "):]) == CHAPTER["grammar"]

    def test_frontmatter_objectives_is_valid_json(self, tmp_path):
        save_story("CONTENT", CHAPTER, GENRE, tmp_path)
        text = self._md_path(tmp_path).read_text(encoding="utf-8")
        line = next(l for l in text.splitlines() if l.startswith("objectives: "))
        assert json.loads(line[len("objectives: "):]) == CHAPTER["objectives"]

    def test_content_appears_after_frontmatter(self, tmp_path):
        save_story("CONTENT", CHAPTER, GENRE, tmp_path)
        text = self._md_path(tmp_path).read_text(encoding="utf-8")
        # Second occurrence of "---\n" closes the frontmatter
        close = text.index("---\n", 4)
        assert "CONTENT" in text[close:]

    def test_prompts_only_creates_txt_file(self, tmp_path):
        save_story("CONTENT", CHAPTER, GENRE, tmp_path, prompts_only=True)
        assert self._txt_path(tmp_path).exists()

    def test_prompts_only_returns_txt_filepath(self, tmp_path):
        assert str(save_story("CONTENT", CHAPTER, GENRE, tmp_path, prompts_only=True)).endswith(".txt")

    def test_prompts_only_contains_system_prompt_header(self, tmp_path):
        save_story("CONTENT", CHAPTER, GENRE, tmp_path, prompts_only=True)
        assert "=== SYSTEM PROMPT ===" in self._txt_path(tmp_path).read_text(encoding="utf-8")

    def test_prompts_only_contains_system_prompt_body(self, tmp_path):
        save_story("CONTENT", CHAPTER, GENRE, tmp_path, prompts_only=True)
        assert "Portuguese and Play" in self._txt_path(tmp_path).read_text(encoding="utf-8")

    def test_prompts_only_contains_user_prompt_header(self, tmp_path):
        save_story("CONTENT", CHAPTER, GENRE, tmp_path, prompts_only=True)
        assert "=== USER PROMPT ===" in self._txt_path(tmp_path).read_text(encoding="utf-8")

    def test_prompts_only_content_follows_user_prompt_header(self, tmp_path):
        save_story("CONTENT", CHAPTER, GENRE, tmp_path, prompts_only=True)
        text = self._txt_path(tmp_path).read_text(encoding="utf-8")
        pos = text.index("=== USER PROMPT ===")
        assert "CONTENT" in text[pos:]

    def test_filename_sanitises_slash_in_chapter_id(self, tmp_path):
        chapter = dict(CHAPTER, id="B1/extra")
        save_story("CONTENT", chapter, GENRE, tmp_path)
        names = [f.name for f in tmp_path.iterdir()]
        assert all("/" not in n for n in names)
        assert any("B1-extra" in n for n in names)

    def test_filename_sanitises_slash_in_genre_name(self, tmp_path):
        genre = {"name": "Noir / Crime Thriller", "description": "desc"}
        save_story("CONTENT", CHAPTER, genre, tmp_path)
        assert any("noir-crime-thriller" in f.name for f in tmp_path.iterdir())

    def test_utf8_encoding_roundtrip(self, tmp_path):
        content = "Olá, história! Ação, emoção."
        save_story(content, CHAPTER, GENRE, tmp_path)
        assert content in self._md_path(tmp_path).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 4. main / CLI
# ---------------------------------------------------------------------------

class TestMain:
    # ---- Chapter counts ----

    def test_default_book_is_both(self, tmp_path, capsys):
        with patch("sys.argv", ["prog", "--dry-run", "--output", str(tmp_path)]):
            main()
        capsys.readouterr()
        assert _count_index_rows(tmp_path) == len(A1A2_CHAPTERS) + len(B1_CHAPTERS)

    def test_book_a1a2_filters_to_correct_count(self, tmp_path, capsys):
        with patch("sys.argv", ["prog", "--book", "a1a2", "--dry-run", "--output", str(tmp_path)]):
            main()
        capsys.readouterr()
        assert _count_index_rows(tmp_path) == len(A1A2_CHAPTERS)

    def test_book_b1_filters_to_correct_count(self, tmp_path, capsys):
        with patch("sys.argv", ["prog", "--book", "b1", "--dry-run", "--output", str(tmp_path)]):
            main()
        capsys.readouterr()
        assert _count_index_rows(tmp_path) == len(B1_CHAPTERS)

    def test_chapter_argument_filters_to_single(self, tmp_path, capsys):
        with patch("sys.argv", ["prog", "--chapter", "A1-1", "--dry-run", "--output", str(tmp_path)]):
            main()
        capsys.readouterr()
        assert _count_index_rows(tmp_path) == 1

    def test_invalid_chapter_prints_not_found(self, tmp_path, capsys):
        with patch("sys.argv", ["prog", "--chapter", "X99-99", "--dry-run", "--output", str(tmp_path)]):
            main()
        out = capsys.readouterr().out
        assert "not found" in out.lower() or "X99-99" in out

    def test_invalid_chapter_does_not_create_index(self, tmp_path, capsys):
        with patch("sys.argv", ["prog", "--chapter", "X99-99", "--dry-run", "--output", str(tmp_path)]):
            main()
        capsys.readouterr()
        assert not (tmp_path / "INDEX.md").exists()

    # ---- Genre cycling ----

    def test_genre_cycles_in_order_for_a1a2(self, tmp_path, capsys):
        with patch("sys.argv", ["prog", "--book", "a1a2", "--dry-run", "--output", str(tmp_path)]):
            main()
        capsys.readouterr()
        genres = _index_genres(tmp_path)
        for i, name in enumerate(genres):
            assert name == GENRES[i % len(GENRES)]["name"]

    def test_genre_wraps_around_at_index_len_genres(self, tmp_path, capsys):
        with patch("sys.argv", ["prog", "--book", "both", "--dry-run", "--output", str(tmp_path)]):
            main()
        capsys.readouterr()
        genres = _index_genres(tmp_path)
        assert genres[len(GENRES)] == GENRES[0]["name"]

    def test_single_chapter_gets_genre_at_index_zero(self, tmp_path, capsys):
        # After filtering to 1 chapter, enumerate starts at 0 → GENRES[0]
        with patch("sys.argv", ["prog", "--chapter", "A1-3", "--dry-run", "--output", str(tmp_path)]):
            main()
        capsys.readouterr()
        assert _index_genres(tmp_path)[0] == GENRES[0]["name"]

    # ---- --inspire / --inspire-file ----

    def test_inspire_text_passed_to_generate_story(self, tmp_path, capsys):
        with patch("generate_stories.generate_story") as mock_gen, \
             patch("sys.argv", ["prog", "--chapter", "A1-1", "--dry-run", "--output", str(tmp_path),
                                "--inspire", "Uma praia em tempestade."]):
            mock_gen.return_value = "FAKE STORY"
            main()
        capsys.readouterr()
        inspiration = mock_gen.call_args.args[-1]
        assert inspiration == "Uma praia em tempestade."

    def test_inspire_file_reads_and_passes_contents(self, tmp_path, capsys):
        inspire_file = tmp_path / "inspiration.txt"
        inspire_file.write_text("Uma tempestade de papel.", encoding="utf-8")
        with patch("generate_stories.generate_story") as mock_gen, \
             patch("sys.argv", ["prog", "--chapter", "A1-1", "--dry-run", "--output", str(tmp_path),
                                "--inspire-file", str(inspire_file)]):
            mock_gen.return_value = "FAKE STORY"
            main()
        capsys.readouterr()
        assert mock_gen.call_args.args[-1] == "Uma tempestade de papel."

    def test_inspire_file_not_found_prints_warning(self, tmp_path, capsys):
        with patch("sys.argv", ["prog", "--chapter", "A1-1", "--dry-run", "--output", str(tmp_path),
                               "--inspire-file", "/nonexistent/inspiration.txt"]):
            main()
        out = capsys.readouterr().out
        assert "not found" in out.lower() or "⚠" in out

    def test_inspire_without_chapter_prints_warning(self, tmp_path, capsys):
        with patch("sys.argv", ["prog", "--book", "a1a2", "--dry-run", "--output", str(tmp_path),
                               "--inspire", "seed text"]):
            main()
        out = capsys.readouterr().out
        assert "--chapter" in out or "best with" in out

    # ---- Output directory ----

    def test_creates_output_directory_if_not_exists(self, tmp_path, capsys):
        nested = tmp_path / "nested" / "new_dir"
        with patch("sys.argv", ["prog", "--dry-run", "--output", str(nested)]):
            main()
        capsys.readouterr()
        assert nested.exists() and nested.is_dir()

    # ---- INDEX.md ----

    def test_creates_index_md(self, tmp_path, capsys):
        with patch("sys.argv", ["prog", "--book", "a1a2", "--dry-run", "--output", str(tmp_path)]):
            main()
        capsys.readouterr()
        assert (tmp_path / "INDEX.md").exists()

    def test_index_md_has_correct_header_row(self, tmp_path, capsys):
        with patch("sys.argv", ["prog", "--book", "a1a2", "--dry-run", "--output", str(tmp_path)]):
            main()
        capsys.readouterr()
        assert "| Chapter | Title | Genre | File |" in (tmp_path / "INDEX.md").read_text(encoding="utf-8")

    def test_index_md_file_links_use_md_extension_in_normal_mode(self, tmp_path, capsys):
        with patch("sys.argv", ["prog", "--book", "a1a2", "--dry-run", "--output", str(tmp_path)]):
            main()
        capsys.readouterr()
        for row in _data_rows(tmp_path):
            assert ".md)" in row

    def test_index_md_file_links_use_txt_extension_for_prompts_only(self, tmp_path, capsys):
        with patch("sys.argv", ["prog", "--book", "a1a2", "--prompts-only", "--output", str(tmp_path)]):
            main()
        capsys.readouterr()
        for row in _data_rows(tmp_path):
            assert ".txt)" in row

    # ---- ALL_PROMPTS.md ----

    def test_prompts_only_creates_all_prompts_md(self, tmp_path, capsys):
        with patch("sys.argv", ["prog", "--book", "a1a2", "--prompts-only", "--output", str(tmp_path)]):
            main()
        capsys.readouterr()
        assert (tmp_path / "ALL_PROMPTS.md").exists()

    def test_all_prompts_md_contains_system_prompt_section(self, tmp_path, capsys):
        with patch("sys.argv", ["prog", "--book", "a1a2", "--prompts-only", "--output", str(tmp_path)]):
            main()
        capsys.readouterr()
        text = (tmp_path / "ALL_PROMPTS.md").read_text(encoding="utf-8")
        assert "## System Prompt" in text
        assert "Portuguese and Play" in text

    def test_all_prompts_md_contains_section_per_chapter(self, tmp_path, capsys):
        with patch("sys.argv", ["prog", "--book", "a1a2", "--prompts-only", "--output", str(tmp_path)]):
            main()
        capsys.readouterr()
        text = (tmp_path / "ALL_PROMPTS.md").read_text(encoding="utf-8")
        for ch in A1A2_CHAPTERS:
            assert ch["id"] in text

    def test_all_prompts_md_not_created_in_dry_run(self, tmp_path, capsys):
        with patch("sys.argv", ["prog", "--book", "a1a2", "--dry-run", "--output", str(tmp_path)]):
            main()
        capsys.readouterr()
        assert not (tmp_path / "ALL_PROMPTS.md").exists()

    def test_all_prompts_md_not_created_in_api_mode(self, tmp_path, capsys):
        with patch("generate_stories.anthropic.Anthropic") as mock_anthropic, \
             patch("sys.argv", ["prog", "--chapter", "A1-1", "--output", str(tmp_path)]):
            mock_anthropic.return_value = _make_mock_client()
            main()
        capsys.readouterr()
        assert not (tmp_path / "ALL_PROMPTS.md").exists()

    # ---- API mode (mocked) ----

    def test_api_mode_calls_anthropic_constructor_once(self, tmp_path, capsys):
        with patch("generate_stories.anthropic.Anthropic") as mock_anthropic, \
             patch("sys.argv", ["prog", "--chapter", "A1-1", "--output", str(tmp_path)]):
            mock_anthropic.return_value = _make_mock_client()
            main()
        capsys.readouterr()
        mock_anthropic.assert_called_once()

    def test_api_mode_creates_story_file(self, tmp_path, capsys):
        with patch("generate_stories.anthropic.Anthropic") as mock_anthropic, \
             patch("sys.argv", ["prog", "--chapter", "A1-1", "--output", str(tmp_path)]):
            mock_anthropic.return_value = _make_mock_client("STORY CONTENT")
            main()
        capsys.readouterr()
        story_files = [f for f in tmp_path.glob("*.md") if f.name != "INDEX.md"]
        assert len(story_files) == 1

    def test_api_mode_sleeps_between_chapters_not_after_last(self, tmp_path, capsys):
        with patch("generate_stories.anthropic.Anthropic") as mock_anthropic, \
             patch("generate_stories.time.sleep") as mock_sleep, \
             patch("sys.argv", ["prog", "--book", "a1a2", "--output", str(tmp_path)]):
            mock_anthropic.return_value = _make_mock_client()
            main()
        capsys.readouterr()
        # 14 chapters → 13 sleeps (not after the last)
        assert mock_sleep.call_count == len(A1A2_CHAPTERS) - 1

    def test_api_mode_respects_delay_argument(self, tmp_path, capsys):
        with patch("generate_stories.anthropic.Anthropic") as mock_anthropic, \
             patch("generate_stories.time.sleep") as mock_sleep, \
             patch("sys.argv", ["prog", "--book", "a1a2", "--output", str(tmp_path), "--delay", "0.5"]):
            mock_anthropic.return_value = _make_mock_client()
            main()
        capsys.readouterr()
        for c in mock_sleep.call_args_list:
            assert c.args[0] == 0.5

    def test_single_chapter_no_sleep(self, tmp_path, capsys):
        with patch("generate_stories.anthropic.Anthropic") as mock_anthropic, \
             patch("generate_stories.time.sleep") as mock_sleep, \
             patch("sys.argv", ["prog", "--chapter", "A1-1", "--output", str(tmp_path)]):
            mock_anthropic.return_value = _make_mock_client()
            main()
        capsys.readouterr()
        mock_sleep.assert_not_called()

    # ---- Error handling ----

    def test_error_in_one_chapter_does_not_abort_others(self, tmp_path, capsys):
        call_count = {"n": 0}

        def fail_first(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("API error")
            return "STORY"

        with patch("generate_stories.generate_story", side_effect=fail_first), \
             patch("sys.argv", ["prog", "--book", "a1a2", "--dry-run", "--output", str(tmp_path)]):
            main()
        capsys.readouterr()
        story_files = [f for f in tmp_path.glob("*.md") if f.name != "INDEX.md"]
        assert len(story_files) == len(A1A2_CHAPTERS) - 1

    def test_error_summary_is_printed(self, tmp_path, capsys):
        with patch("generate_stories.generate_story", side_effect=RuntimeError("API error")), \
             patch("sys.argv", ["prog", "--chapter", "A1-1", "--dry-run", "--output", str(tmp_path)]):
            main()
        out = capsys.readouterr().out
        assert "error" in out.lower() or "✗" in out or "Error" in out


# ---------------------------------------------------------------------------
# 5. parse_prompt_file
# ---------------------------------------------------------------------------

def _make_txt_file(tmp_path: Path, system: str = "SYS", user: str = "USR") -> Path:
    sep = "=" * 60
    content = f"=== SYSTEM PROMPT ===\n\n{system}\n\n{sep}\n=== USER PROMPT ===\n\n{user}"
    p = tmp_path / "A1-1_absurdist-comedy.txt"
    p.write_text(content, encoding="utf-8")
    return p


class TestParsePromptFile:
    def test_parses_user_prompt(self, tmp_path):
        p = _make_txt_file(tmp_path, user="Write a story about a cat.")
        _, user = parse_prompt_file(p)
        assert "Write a story about a cat." in user

    def test_parses_system_prompt(self, tmp_path):
        p = _make_txt_file(tmp_path, system="You are a helpful writer.")
        sys_p, _ = parse_prompt_file(p)
        assert "You are a helpful writer." in sys_p

    def test_falls_back_to_system_prompt_constant_when_missing(self, tmp_path):
        p = tmp_path / "minimal.txt"
        p.write_text("=== USER PROMPT ===\n\nJust the user prompt.", encoding="utf-8")
        sys_p, _ = parse_prompt_file(p)
        assert sys_p == SYSTEM_PROMPT

    def test_raises_when_user_marker_missing(self, tmp_path):
        p = tmp_path / "bad.txt"
        p.write_text("No markers here at all.", encoding="utf-8")
        with pytest.raises(ValueError):
            parse_prompt_file(p)

    def test_user_prompt_does_not_include_marker_text(self, tmp_path):
        p = _make_txt_file(tmp_path, user="My user prompt.")
        _, user = parse_prompt_file(p)
        assert "=== USER PROMPT ===" not in user

    def test_roundtrip_with_real_prompts_only_output(self, tmp_path):
        """Prompt saved by save_story(prompts_only=True) should parse cleanly."""
        save_story(build_user_prompt(CHAPTER, GENRE, "A1/A2"), CHAPTER, GENRE, tmp_path, prompts_only=True)
        txt_files = list(tmp_path.glob("*.txt"))
        assert len(txt_files) == 1
        sys_p, user_p = parse_prompt_file(txt_files[0])
        assert "A1-1" in user_p
        assert "Portuguese and Play" in sys_p


# ---------------------------------------------------------------------------
# 6. generate_from_file
# ---------------------------------------------------------------------------

class TestGenerateFromFile:
    def test_calls_api_with_parsed_system_prompt(self, tmp_path):
        txt = _make_txt_file(tmp_path, system="Custom system prompt.", user="Write something.")
        client = _make_mock_client("RESULT")
        generate_from_file(client, txt, tmp_path / "out")
        assert client.messages.create.call_args.kwargs["system"] == "Custom system prompt."

    def test_calls_api_with_parsed_user_prompt(self, tmp_path):
        txt = _make_txt_file(tmp_path, user="Write something specific.")
        client = _make_mock_client("RESULT")
        generate_from_file(client, txt, tmp_path / "out")
        messages = client.messages.create.call_args.kwargs["messages"]
        assert "Write something specific." in messages[0]["content"]

    def test_creates_md_file_in_output_dir(self, tmp_path):
        txt = _make_txt_file(tmp_path, user="Write something.")
        out_dir = tmp_path / "out"
        generate_from_file(_make_mock_client("STORY"), txt, out_dir)
        assert (out_dir / "A1-1_absurdist-comedy.md").exists()

    def test_md_content_matches_api_response(self, tmp_path):
        txt = _make_txt_file(tmp_path, user="Write something.")
        out_dir = tmp_path / "out"
        generate_from_file(_make_mock_client("THE STORY CONTENT"), txt, out_dir)
        text = (out_dir / "A1-1_absurdist-comedy.md").read_text(encoding="utf-8")
        assert "THE STORY CONTENT" in text

    def test_creates_output_dir_if_missing(self, tmp_path):
        txt = _make_txt_file(tmp_path, user="Write something.")
        out_dir = tmp_path / "nested" / "new"
        generate_from_file(_make_mock_client("STORY"), txt, out_dir)
        assert out_dir.exists()

    def test_uses_correct_model(self, tmp_path):
        txt = _make_txt_file(tmp_path, user="Write something.")
        client = _make_mock_client()
        generate_from_file(client, txt, tmp_path / "out")
        assert client.messages.create.call_args.kwargs["model"] == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# 7. main / CLI — --from-file
# ---------------------------------------------------------------------------

class TestMainFromFile:
    def test_from_file_calls_generate_from_file(self, tmp_path, capsys):
        txt = _make_txt_file(tmp_path, user="Write something.")
        with patch("generate_stories.generate_from_file") as mock_gen, \
             patch("generate_stories.anthropic.Anthropic") as mock_anthropic, \
             patch("sys.argv", ["prog", "--from-file", str(txt), "--output", str(tmp_path / "out")]):
            mock_anthropic.return_value = _make_mock_client()
            main()
        capsys.readouterr()
        mock_gen.assert_called_once()

    def test_from_file_passes_correct_path(self, tmp_path, capsys):
        txt = _make_txt_file(tmp_path, user="Write something.")
        with patch("generate_stories.generate_from_file") as mock_gen, \
             patch("generate_stories.anthropic.Anthropic") as mock_anthropic, \
             patch("sys.argv", ["prog", "--from-file", str(txt), "--output", str(tmp_path / "out")]):
            mock_anthropic.return_value = _make_mock_client()
            main()
        capsys.readouterr()
        assert mock_gen.call_args.args[1] == txt

    def test_from_file_missing_prints_warning(self, tmp_path, capsys):
        with patch("sys.argv", ["prog", "--from-file", "/nonexistent/file.txt",
                                "--output", str(tmp_path)]):
            main()
        out = capsys.readouterr().out
        assert "not found" in out.lower() or "⚠" in out

    def test_from_file_does_not_call_generate_story(self, tmp_path, capsys):
        txt = _make_txt_file(tmp_path, user="Write something.")
        with patch("generate_stories.generate_from_file"), \
             patch("generate_stories.generate_story") as mock_story, \
             patch("generate_stories.anthropic.Anthropic") as mock_anthropic, \
             patch("sys.argv", ["prog", "--from-file", str(txt), "--output", str(tmp_path / "out")]):
            mock_anthropic.return_value = _make_mock_client()
            main()
        capsys.readouterr()
        mock_story.assert_not_called()
