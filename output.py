"""
File output for Portuguese and Play — saving prompts, stories, PDFs, and index files.
"""

import json
import re
from pathlib import Path

try:
    import markdown as _md_lib
    import weasyprint as _weasyprint
    _PDF_AVAILABLE = True
except ImportError:
    _PDF_AVAILABLE = False

from prompts import SYSTEM_PROMPT, build_user_prompt

_FONTS_DIR = Path(__file__).parent / "fonts"

CSS = f"""
* {{ box-sizing: border-box; margin: 0; padding: 0; }}

@font-face {{
    font-family: 'Inter';
    font-weight: 400;
    src: url('{_FONTS_DIR / "Inter-Regular.ttf"}') format('truetype');
}}

@font-face {{
    font-family: 'Inter';
    font-weight: 900;
    src: url('{_FONTS_DIR / "Inter-Black.ttf"}') format('truetype');
}}

@page {{
    size: A4;
    margin: 3cm;
}}

body {{
    font-family: 'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-weight: 400;
    font-size: 10.5pt;
    color: #2F4F4F;
    background: white;
    line-height: 1.65;
}}

h1 {{
    font-family: 'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-weight: 900;
    font-size: 22pt;
    color: #2F4F4F;
    text-align: center;
    margin-top: 1cm;
    margin-bottom: 0.3cm;
}}

h1 + h1 {{
    font-size: 13pt;
    color: #8B4513;
    font-style: normal;
    font-weight: 400;
    margin-top: 0;
    margin-bottom: 0.8cm;
}}

hr {{
    border: none;
    border-top: 1px solid #C8B89A;
    width: 80%;
    margin: 0 auto 1cm auto;
}}

p {{
    font-size: 10.5pt;
    color: #2F4F4F;
    text-align: justify;
    line-height: 1.7;
    margin-bottom: 0.1cm;
}}

p em {{
    font-style: italic;
    color: #5A6B5A;
}}

p em:only-child {{
    display: block;
    font-size: 9.5pt;
    padding-left: 0.8cm;
    line-height: 1.6;
    margin-bottom: 0.55cm;
    margin-top: 0.1cm;
}}

h2 {{
    font-family: 'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-weight: 900;
    font-size: 10pt;
    color: #8B4513;
    margin-top: 1.2cm;
    margin-bottom: 0.4cm;
    padding-top: 0.6cm;
    border-top: 0.5px solid #C8B89A;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}

p strong:only-child {{
    color: #2F4F4F;
    font-size: 9.5pt;
    margin-top: 0.5cm;
    margin-bottom: 0.2cm;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 0.5cm;
    font-size: 9.5pt;
}}

th, td {{
    padding: 4px 6px;
    border: 0.5px solid #C8B89A;
    color: #2F4F4F;
    text-align: left;
    vertical-align: top;
}}

tr:nth-child(odd)  {{ background-color: #F5F0E8; }}
tr:nth-child(even) {{ background-color: white; }}
"""

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="utf-8">
<style>{css}</style>
</head>
<body>
{body}
</body>
</html>"""


def build_pdf(content: str, output_path: str):
    """Convert markdown content to a PDF file."""
    if not _PDF_AVAILABLE:
        print("  ⚠ PDF skipped — install dependencies: pip install weasyprint markdown")
        return
    html_body = _md_lib.markdown(content, extensions=["tables"])
    full_html = HTML_TEMPLATE.format(css=CSS, body=html_body)
    _weasyprint.HTML(string=full_html).write_pdf(output_path)
    print(f"  ✓ PDF → {output_path}")


def build_pdfs_from_dir(output_dir: Path, chapter_id: str = None):
    """Build PDFs from all .md files in output_dir, optionally filtered by chapter_id."""
    if chapter_id:
        md_files = sorted(output_dir.glob(f"{chapter_id.replace('/', '-')}_*.md"))
    else:
        md_files = sorted(
            f for f in output_dir.glob("*.md")
            if f.name not in ("INDEX.md", "ALL_PROMPTS.md")
        )

    if not md_files:
        print("No markdown files found to convert.")
        return

    print(f"Building PDFs for {len(md_files)} file(s)...")
    for md_path in md_files:
        text = md_path.read_text(encoding="utf-8")
        content = re.sub(r"^---.*?---\n\n", "", text, flags=re.DOTALL)
        build_pdf(content, str(md_path.with_suffix(".pdf")))


def save_prompt(user_prompt: str, chapter: dict, genre: dict, prompts_dir: Path) -> Path:
    """Save a user prompt as a .txt file in prompts_dir."""
    safe_id = chapter["id"].replace("/", "-")
    safe_genre = genre["name"].lower().replace(" / ", "-").replace(" ", "-")
    filepath = prompts_dir / f"{safe_id}_{safe_genre}.txt"
    sep = "=" * 60
    header = f"=== SYSTEM PROMPT ===\n\n{SYSTEM_PROMPT}\n\n{sep}\n=== USER PROMPT ===\n\n"
    filepath.write_text(header + user_prompt, encoding="utf-8")
    return filepath


def save_story(content: str, chapter: dict, genre: dict, output_dir: Path) -> Path:
    """Save generated story content as a .md file with YAML frontmatter."""
    safe_id = chapter["id"].replace("/", "-")
    safe_genre = genre["name"].lower().replace(" / ", "-").replace(" ", "-")
    filepath = output_dir / f"{safe_id}_{safe_genre}.md"
    grammar_json = json.dumps(chapter["grammar"])
    obj_json = json.dumps(chapter["objectives"])
    frontmatter = (
        f"---\n"
        f"chapter: {chapter['id']}\n"
        f"title: {chapter['title']}\n"
        f"genre: {genre['name']}\n"
        f"grammar: {grammar_json}\n"
        f"objectives: {obj_json}\n"
        f"---\n\n"
    )
    filepath.write_text(frontmatter + content, encoding="utf-8")
    return filepath


def write_index(chapters_with_genres: list, output_dir: Path, ext: str = "md"):
    """Write an INDEX.md table of all chapters, genres, and filenames to output_dir."""
    index_path = output_dir / "INDEX.md"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("# Portuguese and Play — Index\n\n")
        f.write("| Chapter | Title | Genre | File |\n")
        f.write("|---------|-------|-------|------|\n")
        for level, ch, genre in chapters_with_genres:
            safe_id = ch["id"].replace("/", "-")
            safe_genre = genre["name"].lower().replace(" / ", "-").replace(" ", "-")
            fname = f"{safe_id}_{safe_genre}.{ext}"
            f.write(f"| {ch['id']} | {ch['title']} | {genre['name']} | [{fname}]({fname}) |\n")
    print(f"  Index → {index_path}")


def write_all_prompts(chapters_with_genres: list, prompts_dir: Path, inspiration: str = ""):
    """Write a single ALL_PROMPTS.md combining every chapter's prompt into one document."""
    all_prompts_path = prompts_dir / "ALL_PROMPTS.md"
    with open(all_prompts_path, "w", encoding="utf-8") as f:
        f.write("# Portuguese and Play — All Prompts\n\n")
        f.write(f"_{len(chapters_with_genres)} prompts. Paste each into Claude or your preferred LLM._\n\n---\n\n")
        f.write(f"## System Prompt (use for ALL chapters)\n\n```\n{SYSTEM_PROMPT}\n```\n\n---\n\n")
        for level, ch, genre in chapters_with_genres:
            f.write(f"## {ch['id']} — {ch['title']} [{genre['name']}]\n\n```\n")
            f.write(build_user_prompt(ch, genre, level, inspiration))
            f.write("```\n\n---\n\n")
    print(f"  All prompts → {all_prompts_path}")
