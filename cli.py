#!/usr/bin/env python3
"""
Portuguese and Play — CLI entry point.

Three commands:
  generate_story_prompts  Build .txt prompt files from curriculum data (run once, then edit freely)
  generate_story_md       Read .txt prompt files, call the API, save .md story files
  generate_story_pdf      Convert .md story files to .pdf (no API call)
"""

import anthropic
import argparse
import time
from pathlib import Path

from curriculum import A1A2_CHAPTERS, B1_CHAPTERS, GENRES
from prompts import build_user_prompt
from output import (
    save_prompt,
    save_story,
    build_pdfs_from_dir,
    write_index,
    write_all_prompts,
)
from api_client import generate_story_md


def _resolve_chapters(book: str = "both", chapter_id: str = None) -> list:
    """Return a list of (level, chapter, genre) tuples filtered by book and chapter_id."""
    all_chapters = []
    if book in ("a1a2", "both"):
        all_chapters += [("A1/A2", ch) for ch in A1A2_CHAPTERS]
    if book in ("b1", "both"):
        all_chapters += [("B1", ch) for ch in B1_CHAPTERS]
    if chapter_id:
        all_chapters = [(level, ch) for level, ch in all_chapters if ch["id"] == chapter_id]
    return [
        (level, ch, GENRES[i % len(GENRES)])
        for i, (level, ch) in enumerate(all_chapters)
    ]


def cmd_generate_story_prompts(args):
    """Build prompt .txt files from curriculum data. Run once per chapter, then edit freely."""
    chapters_with_genres = _resolve_chapters(args.book, args.chapter)
    if not chapters_with_genres:
        print(f"Chapter '{args.chapter}' not found.")
        return

    inspiration = ""
    if args.inspire_file:
        p = Path(args.inspire_file)
        if not p.exists():
            print(f"⚠️  --inspire-file not found: {p}")
        else:
            inspiration = p.read_text(encoding="utf-8")
    elif args.inspire:
        inspiration = args.inspire

    if inspiration and not args.chapter:
        print("⚠️  --inspire works best with --chapter (will be applied to all chapters)")

    prompts_dir = Path(args.prompts_dir)
    prompts_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n🇵🇹 Portuguese and Play — generate_story_prompts")
    print(f"   Chapters: {len(chapters_with_genres)}")
    print(f"   Output:   {prompts_dir.resolve()}\n")

    generated = []
    for level, chapter, genre in chapters_with_genres:
        user_prompt = build_user_prompt(chapter, genre, level, inspiration)
        filepath = save_prompt(user_prompt, chapter, genre, prompts_dir)
        print(f"  Saved: {chapter['id']} — {chapter['title']} [{genre['name']}]")
        generated.append(filepath)

    write_all_prompts(chapters_with_genres, prompts_dir, inspiration)
    write_index(chapters_with_genres, prompts_dir, ext="txt")

    print(f"\n{'='*50}")
    print(f"✅ {len(generated)} prompts → {prompts_dir.resolve()}")


def cmd_generate_story_md(args):
    """Read .txt prompt files and call the API to generate .md story files."""
    chapters_with_genres = _resolve_chapters(args.book, args.chapter)
    if not chapters_with_genres:
        print(f"Chapter '{args.chapter}' not found.")
        return

    prompts_dir = Path(args.prompts_dir)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n🇵🇹 Portuguese and Play — generate_story_md")
    print(f"   Chapters: {len(chapters_with_genres)}")
    print(f"   Prompts:  {prompts_dir.resolve()}")
    print(f"   Output:   {output_dir.resolve()}\n")

    client = anthropic.Anthropic()
    generated = []
    errors = []

    for i, (level, chapter, genre) in enumerate(chapters_with_genres):
        safe_id = chapter["id"].replace("/", "-")
        safe_genre = genre["name"].lower().replace(" / ", "-").replace(" ", "-")
        txt_path = prompts_dir / f"{safe_id}_{safe_genre}.txt"

        if not txt_path.exists():
            print(f"  ⚠️  Prompt not found: {txt_path} — run generate_story_prompts first")
            errors.append((chapter["id"], "prompt file not found"))
            continue

        try:
            content = generate_story_md(client, txt_path)
            filepath = save_story(content, chapter, genre, output_dir)
            generated.append(filepath)

            if i < len(chapters_with_genres) - 1:
                time.sleep(args.delay)
        except Exception as e:
            print(f" ✗ ERROR: {e}")
            errors.append((chapter["id"], str(e)))

    write_index(chapters_with_genres, output_dir, ext="md")

    print(f"\n{'='*50}")
    print(f"✅ {len(generated)} stories → {output_dir.resolve()}")
    if errors:
        print(f"❌ Errors: {len(errors)}")
        for ch_id, err in errors:
            print(f"   {ch_id}: {err}")


def cmd_generate_story_pdf(args):
    """Convert .md story files to .pdf. No API call required."""
    output_dir = Path(args.output)
    print(f"\n🇵🇹 Portuguese and Play — generate_story_pdf")
    print(f"   Output: {output_dir.resolve()}\n")
    build_pdfs_from_dir(output_dir, chapter_id=args.chapter)


def main():
    parser = argparse.ArgumentParser(description="Portuguese and Play story generator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # generate_story_prompts
    p1 = subparsers.add_parser(
        "generate_story_prompts",
        help="Build prompt .txt files from curriculum data — run once per chapter, then edit freely",
    )
    p1.add_argument("--book", choices=["a1a2", "b1", "both"], default="both")
    p1.add_argument("--chapter", help="Single chapter ID (e.g. A1-1)")
    p1.add_argument("--inspire", metavar="TEXT", help="Optional plot seed or inspiration for the story")
    p1.add_argument("--inspire-file", metavar="FILE", help="Read story inspiration from a file")
    p1.add_argument("--prompts-dir", default="./stories", help="Where to save .txt files (default: ./stories)")

    # generate_story_md
    p2 = subparsers.add_parser(
        "generate_story_md",
        help="Generate story .md files from .txt prompt files — calls the Anthropic API",
    )
    p2.add_argument("--book", choices=["a1a2", "b1", "both"], default="both")
    p2.add_argument("--chapter", help="Single chapter ID (e.g. A1-1)")
    p2.add_argument("--prompts-dir", default="./stories", help="Where to read .txt files from (default: ./stories)")
    p2.add_argument("--output", default="./outputs", help="Where to save .md files (default: ./outputs)")
    p2.add_argument("--delay", type=float, default=2.0, help="Seconds between API calls (default: 2.0)")

    # generate_story_pdf
    p3 = subparsers.add_parser(
        "generate_story_pdf",
        help="Generate .pdf files from story .md files — no API call required",
    )
    p3.add_argument("--chapter", help="Single chapter ID (e.g. A1-1)")
    p3.add_argument("--output", default="./outputs", help="Where to read .md and save .pdf files (default: ./outputs)")

    args = parser.parse_args()

    if args.command == "generate_story_prompts":
        cmd_generate_story_prompts(args)
    elif args.command == "generate_story_md":
        cmd_generate_story_md(args)
    elif args.command == "generate_story_pdf":
        cmd_generate_story_pdf(args)


if __name__ == "__main__":
    main()
