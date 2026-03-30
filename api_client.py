"""
Anthropic API client for Portuguese and Play.
Reads a .txt prompt file and calls the Claude API to generate a story.
"""

from pathlib import Path

from prompts import parse_prompt_file


def generate_story_md(client, txt_path: Path) -> str:
    """Read a .txt prompt file, call the Claude API, and return the story content."""
    system_prompt, user_prompt = parse_prompt_file(txt_path)
    print(f"  Generating {txt_path.stem}...", end="", flush=True)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    content = message.content[0].text
    print(" ✓")
    return content
