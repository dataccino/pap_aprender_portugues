"""
Tests for Portuguese and Play modules.

Run with:
    pytest test_generate_stories.py -v
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from curriculum import A1A2_CHAPTERS, B1_CHAPTERS, GENRES
from prompts import SYSTEM_PROMPT, build_user_prompt, parse_prompt_file
from output import save_prompt, save_story, write_index, write_all_prompts
from api_client import generate_story_md
from cli import main, _resolve_chapters

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


def _make_txt_file(tmp_path: Path, system: str = "SYS", user: str = "USR") -> Path:
    sep = "=" * 60
    content = f"=== SYSTEM PROMPT ===\n\n{system}\n\n{sep}\n=== USER PROMPT ===\n\n{user}"
    p = tmp_path / "A1-1_absurdist-comedy.txt"
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# INDEX.md helpers
# ---------------------------------------------------------------------------

def _data_rows(output_dir: Path) -> list[str]:
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
# 2. parse_prompt_file
# ---------------------------------------------------------------------------

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

    def test_roundtrip_with_save_prompt_output(self, tmp_path):
        user_prompt = build_user_prompt(CHAPTER, GENRE, "A1/A2")
        save_prompt(user_prompt, CHAPTER, GENRE, tmp_path)
        txt_files = list(tmp_path.glob("*.txt"))
        assert len(txt_files) == 1
        sys_p, user_p = parse_prompt_file(txt_files[0])
        assert "A1-1" in user_p
        assert "Portuguese and Play" in sys_p


# ---------------------------------------------------------------------------
# 3. save_prompt
# ---------------------------------------------------------------------------

class TestSavePrompt:
    def _txt_path(self, tmp_path):
        safe_id = CHAPTER["id"].replace("/", "-")
        safe_genre = GENRE["name"].lower().replace(" / ", "-").replace(" ", "-")
        return tmp_path / f"{safe_id}_{safe_genre}.txt"

    def test_creates_txt_file(self, tmp_path):
        save_prompt("USER PROMPT", CHAPTER, GENRE, tmp_path)
        assert self._txt_path(tmp_path).exists()

    def test_returns_txt_filepath(self, tmp_path):
        assert save_prompt("USER PROMPT", CHAPTER, GENRE, tmp_path) == self._txt_path(tmp_path)

    def test_contains_system_prompt_header(self, tmp_path):
        save_prompt("USER PROMPT", CHAPTER, GENRE, tmp_path)
        assert "=== SYSTEM PROMPT ===" in self._txt_path(tmp_path).read_text(encoding="utf-8")

    def test_contains_system_prompt_body(self, tmp_path):
        save_prompt("USER PROMPT", CHAPTER, GENRE, tmp_path)
        assert "Portuguese and Play" in self._txt_path(tmp_path).read_text(encoding="utf-8")

    def test_contains_user_prompt_header(self, tmp_path):
        save_prompt("USER PROMPT", CHAPTER, GENRE, tmp_path)
        assert "=== USER PROMPT ===" in self._txt_path(tmp_path).read_text(encoding="utf-8")

    def test_user_prompt_content_follows_header(self, tmp_path):
        save_prompt("MY PROMPT CONTENT", CHAPTER, GENRE, tmp_path)
        text = self._txt_path(tmp_path).read_text(encoding="utf-8")
        pos = text.index("=== USER PROMPT ===")
        assert "MY PROMPT CONTENT" in text[pos:]

    def test_filename_sanitises_slash_in_chapter_id(self, tmp_path):
        chapter = dict(CHAPTER, id="B1/extra")
        save_prompt("USER PROMPT", chapter, GENRE, tmp_path)
        names = [f.name for f in tmp_path.iterdir()]
        assert all("/" not in n for n in names)
        assert any("B1-extra" in n for n in names)

    def test_filename_sanitises_slash_in_genre_name(self, tmp_path):
        genre = {"name": "Noir / Crime Thriller", "description": "desc"}
        save_prompt("USER PROMPT", CHAPTER, genre, tmp_path)
        assert any("noir-crime-thriller" in f.name for f in tmp_path.iterdir())


# ---------------------------------------------------------------------------
# 4. save_story
# ---------------------------------------------------------------------------

class TestSaveStory:
    def _md_path(self, tmp_path):
        safe_id = CHAPTER["id"].replace("/", "-")
        safe_genre = GENRE["name"].lower().replace(" / ", "-").replace(" ", "-")
        return tmp_path / f"{safe_id}_{safe_genre}.md"

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
        close = text.index("---\n", 4)
        assert "CONTENT" in text[close:]

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
# 5. generate_story_md (api_client)
# ---------------------------------------------------------------------------

class TestGenerateStoryMd:
    def test_calls_api_with_parsed_system_prompt(self, tmp_path):
        txt = _make_txt_file(tmp_path, system="Custom system prompt.", user="Write something.")
        client = _make_mock_client("RESULT")
        generate_story_md(client, txt)
        assert client.messages.create.call_args.kwargs["system"] == "Custom system prompt."

    def test_calls_api_with_parsed_user_prompt(self, tmp_path):
        txt = _make_txt_file(tmp_path, user="Write something specific.")
        client = _make_mock_client("RESULT")
        generate_story_md(client, txt)
        messages = client.messages.create.call_args.kwargs["messages"]
        assert "Write something specific." in messages[0]["content"]

    def test_returns_api_response(self, tmp_path):
        txt = _make_txt_file(tmp_path, user="Write something.")
        assert generate_story_md(_make_mock_client("STORY TEXT"), txt) == "STORY TEXT"

    def test_uses_correct_model(self, tmp_path):
        txt = _make_txt_file(tmp_path, user="Write something.")
        client = _make_mock_client()
        generate_story_md(client, txt)
        assert client.messages.create.call_args.kwargs["model"] == "claude-sonnet-4-6"

    def test_uses_correct_max_tokens(self, tmp_path):
        txt = _make_txt_file(tmp_path, user="Write something.")
        client = _make_mock_client()
        generate_story_md(client, txt)
        assert client.messages.create.call_args.kwargs["max_tokens"] == 3000

    def test_prints_generating_and_checkmark(self, tmp_path, capsys):
        txt = _make_txt_file(tmp_path, user="Write something.")
        generate_story_md(_make_mock_client(), txt)
        out = capsys.readouterr().out
        assert "Generating" in out
        assert "✓" in out


# ---------------------------------------------------------------------------
# 6. _resolve_chapters
# ---------------------------------------------------------------------------

class TestResolveChapters:
    def test_both_returns_all_chapters(self):
        result = _resolve_chapters("both")
        assert len(result) == len(A1A2_CHAPTERS) + len(B1_CHAPTERS)

    def test_a1a2_returns_correct_count(self):
        assert len(_resolve_chapters("a1a2")) == len(A1A2_CHAPTERS)

    def test_b1_returns_correct_count(self):
        assert len(_resolve_chapters("b1")) == len(B1_CHAPTERS)

    def test_chapter_filter_returns_single(self):
        result = _resolve_chapters("both", "A1-1")
        assert len(result) == 1
        assert result[0][1]["id"] == "A1-1"

    def test_invalid_chapter_returns_empty(self):
        assert _resolve_chapters("both", "X99-99") == []

    def test_genres_cycle_in_order(self):
        result = _resolve_chapters("a1a2")
        for i, (level, ch, genre) in enumerate(result):
            assert genre["name"] == GENRES[i % len(GENRES)]["name"]

    def test_genres_wrap_around(self):
        result = _resolve_chapters("both")
        assert result[len(GENRES)][2]["name"] == GENRES[0]["name"]


# ---------------------------------------------------------------------------
# 7. CLI — generate_story_prompts
# ---------------------------------------------------------------------------

class TestCmdGenerateStoryPrompts:
    def test_creates_txt_files(self, tmp_path, capsys):
        with patch("sys.argv", ["cli.py", "generate_story_prompts",
                                "--book", "a1a2", "--prompts-dir", str(tmp_path)]):
            main()
        capsys.readouterr()
        assert len(list(tmp_path.glob("*.txt"))) == len(A1A2_CHAPTERS)

    def test_single_chapter_creates_one_file(self, tmp_path, capsys):
        with patch("sys.argv", ["cli.py", "generate_story_prompts",
                                "--chapter", "A1-1", "--prompts-dir", str(tmp_path)]):
            main()
        capsys.readouterr()
        assert len(list(tmp_path.glob("*.txt"))) == 1

    def test_invalid_chapter_prints_not_found(self, tmp_path, capsys):
        with patch("sys.argv", ["cli.py", "generate_story_prompts",
                                "--chapter", "X99-99", "--prompts-dir", str(tmp_path)]):
            main()
        out = capsys.readouterr().out
        assert "not found" in out.lower() or "X99-99" in out

    def test_creates_index_md(self, tmp_path, capsys):
        with patch("sys.argv", ["cli.py", "generate_story_prompts",
                                "--book", "a1a2", "--prompts-dir", str(tmp_path)]):
            main()
        capsys.readouterr()
        assert (tmp_path / "INDEX.md").exists()

    def test_index_links_use_txt_extension(self, tmp_path, capsys):
        with patch("sys.argv", ["cli.py", "generate_story_prompts",
                                "--book", "a1a2", "--prompts-dir", str(tmp_path)]):
            main()
        capsys.readouterr()
        for row in _data_rows(tmp_path):
            assert ".txt)" in row

    def test_creates_all_prompts_md(self, tmp_path, capsys):
        with patch("sys.argv", ["cli.py", "generate_story_prompts",
                                "--book", "a1a2", "--prompts-dir", str(tmp_path)]):
            main()
        capsys.readouterr()
        assert (tmp_path / "ALL_PROMPTS.md").exists()

    def test_all_prompts_md_contains_system_prompt(self, tmp_path, capsys):
        with patch("sys.argv", ["cli.py", "generate_story_prompts",
                                "--book", "a1a2", "--prompts-dir", str(tmp_path)]):
            main()
        capsys.readouterr()
        text = (tmp_path / "ALL_PROMPTS.md").read_text(encoding="utf-8")
        assert "## System Prompt" in text
        assert "Portuguese and Play" in text

    def test_inspire_text_baked_into_prompt_file(self, tmp_path, capsys):
        with patch("sys.argv", ["cli.py", "generate_story_prompts",
                                "--chapter", "A1-1", "--prompts-dir", str(tmp_path),
                                "--inspire", "Uma tempestade de papel."]):
            main()
        capsys.readouterr()
        txt_files = list(tmp_path.glob("*.txt"))
        assert len(txt_files) == 1
        assert "Uma tempestade de papel." in txt_files[0].read_text(encoding="utf-8")

    def test_inspire_file_reads_and_bakes_into_prompt(self, tmp_path, capsys):
        inspire_file = tmp_path / "inspiration.txt"
        inspire_file.write_text("Uma praia em tempestade.", encoding="utf-8")
        with patch("sys.argv", ["cli.py", "generate_story_prompts",
                                "--chapter", "A1-1", "--prompts-dir", str(tmp_path),
                                "--inspire-file", str(inspire_file)]):
            main()
        capsys.readouterr()
        txt_files = [f for f in tmp_path.glob("*.txt") if f.name != inspire_file.name]
        assert any("Uma praia em tempestade." in f.read_text(encoding="utf-8") for f in txt_files)

    def test_inspire_file_not_found_prints_warning(self, tmp_path, capsys):
        with patch("sys.argv", ["cli.py", "generate_story_prompts",
                                "--chapter", "A1-1", "--prompts-dir", str(tmp_path),
                                "--inspire-file", "/nonexistent/inspiration.txt"]):
            main()
        out = capsys.readouterr().out
        assert "not found" in out.lower() or "⚠" in out


# ---------------------------------------------------------------------------
# 8. CLI — generate_story_md
# ---------------------------------------------------------------------------

class TestCmdGenerateStoryMd:
    def _make_prompts(self, prompts_dir, chapters_with_genres):
        """Pre-populate prompt .txt files for the given chapters."""
        prompts_dir.mkdir(parents=True, exist_ok=True)
        for level, chapter, genre in chapters_with_genres:
            user_prompt = build_user_prompt(chapter, genre, level)
            save_prompt(user_prompt, chapter, genre, prompts_dir)

    def test_creates_md_file_for_each_chapter(self, tmp_path, capsys):
        prompts_dir = tmp_path / "stories"
        output_dir = tmp_path / "outputs"
        chapters = _resolve_chapters("a1a2")[:2]
        self._make_prompts(prompts_dir, chapters)
        with patch("cli.anthropic") as mock_cli_a, \
             patch("sys.argv", ["cli.py", "generate_story_md",
                                "--book", "a1a2", "--chapter", chapters[0][1]["id"],
                                "--prompts-dir", str(prompts_dir),
                                "--output", str(output_dir)]):
            mock_cli_a.Anthropic.return_value = _make_mock_client("STORY")
            main()
        capsys.readouterr()
        assert len(list(output_dir.glob("*.md"))) >= 1

    def test_warns_when_prompt_file_missing(self, tmp_path, capsys):
        prompts_dir = tmp_path / "stories"
        prompts_dir.mkdir()
        output_dir = tmp_path / "outputs"
        with patch("cli.anthropic") as mock_anthropic, \
             patch("sys.argv", ["cli.py", "generate_story_md",
                                "--chapter", "A1-1",
                                "--prompts-dir", str(prompts_dir),
                                "--output", str(output_dir)]):
            mock_anthropic.Anthropic.return_value = _make_mock_client()
            main()
        out = capsys.readouterr().out
        assert "⚠" in out or "not found" in out.lower() or "generate_story_prompts" in out

    def test_creates_index_md(self, tmp_path, capsys):
        prompts_dir = tmp_path / "stories"
        output_dir = tmp_path / "outputs"
        chapters = _resolve_chapters("both", "A1-1")
        self._make_prompts(prompts_dir, chapters)
        with patch("cli.anthropic") as mock_anthropic, \
             patch("sys.argv", ["cli.py", "generate_story_md",
                                "--chapter", "A1-1",
                                "--prompts-dir", str(prompts_dir),
                                "--output", str(output_dir)]):
            mock_anthropic.Anthropic.return_value = _make_mock_client("STORY")
            main()
        capsys.readouterr()
        assert (output_dir / "INDEX.md").exists()

    def test_index_links_use_md_extension(self, tmp_path, capsys):
        prompts_dir = tmp_path / "stories"
        output_dir = tmp_path / "outputs"
        chapters = _resolve_chapters("both", "A1-1")
        self._make_prompts(prompts_dir, chapters)
        with patch("cli.anthropic") as mock_anthropic, \
             patch("sys.argv", ["cli.py", "generate_story_md",
                                "--chapter", "A1-1",
                                "--prompts-dir", str(prompts_dir),
                                "--output", str(output_dir)]):
            mock_anthropic.Anthropic.return_value = _make_mock_client("STORY")
            main()
        capsys.readouterr()
        for row in _data_rows(output_dir):
            assert ".md)" in row

    def test_sleeps_between_chapters_not_after_last(self, tmp_path, capsys):
        prompts_dir = tmp_path / "stories"
        output_dir = tmp_path / "outputs"
        chapters = _resolve_chapters("a1a2")
        self._make_prompts(prompts_dir, chapters)
        with patch("cli.anthropic") as mock_anthropic, \
             patch("cli.time.sleep") as mock_sleep, \
             patch("sys.argv", ["cli.py", "generate_story_md",
                                "--book", "a1a2",
                                "--prompts-dir", str(prompts_dir),
                                "--output", str(output_dir)]):
            mock_anthropic.Anthropic.return_value = _make_mock_client()
            main()
        capsys.readouterr()
        assert mock_sleep.call_count == len(A1A2_CHAPTERS) - 1

    def test_respects_delay_argument(self, tmp_path, capsys):
        prompts_dir = tmp_path / "stories"
        output_dir = tmp_path / "outputs"
        chapters = _resolve_chapters("a1a2")
        self._make_prompts(prompts_dir, chapters)
        with patch("cli.anthropic") as mock_anthropic, \
             patch("cli.time.sleep") as mock_sleep, \
             patch("sys.argv", ["cli.py", "generate_story_md",
                                "--book", "a1a2", "--delay", "0.5",
                                "--prompts-dir", str(prompts_dir),
                                "--output", str(output_dir)]):
            mock_anthropic.Anthropic.return_value = _make_mock_client()
            main()
        capsys.readouterr()
        for c in mock_sleep.call_args_list:
            assert c.args[0] == 0.5

    def test_invalid_chapter_prints_not_found(self, tmp_path, capsys):
        with patch("sys.argv", ["cli.py", "generate_story_md",
                                "--chapter", "X99-99",
                                "--prompts-dir", str(tmp_path),
                                "--output", str(tmp_path)]):
            main()
        out = capsys.readouterr().out
        assert "not found" in out.lower() or "X99-99" in out
