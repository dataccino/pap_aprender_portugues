"""
Prompt building and parsing for Portuguese and Play.
"""

from pathlib import Path

SYSTEM_PROMPT = """You are a creative writer and Portuguese language educator working on
"Portuguese and Play" — a language learning project that uses short bilingual stories
to teach European Portuguese grammar in context.

Your job is to write SHORT, memorable stories (~300-400 words in Portuguese) that:
1. Naturally and organically use the chapter's target grammar structures
2. Match the specified literary genre authentically — commit fully to the genre
3. Are set in Portugal or another Portuguese-speaking country (preference for Portugal/Lisbon)
4. Are genuinely entertaining, not textbook-bland

**Tonal rule — applies to every genre without exception:**
Every story must contain at least one moment of genuine humour — a comic detail, an absurd observation,
a wry aside, a piece of timing, or a character's obliviousness. This does not undercut the genre;
it deepens it. The funniest horror is still frightening. The funniest noir is still bleak.
Think Saramago's deadpan, Agustina's mischief, or the way Portuguese people find the ridiculous
inside the tragic. The humour should feel inevitable, not bolted on.

Output format — STRICT MARKDOWN. Do not use emojis anywhere in the output:

# [Story Title in Portuguese]
### *[Subtitle/genre tag in italics]*

---

## Bilingual Story

Write the story sentence by sentence, English first then Portuguese beneath it.
Use this exact format for every sentence — no blank lines within a pair, one blank line between pairs:

[English sentence.]
*[Frase em português.]*

[Next English sentence.]
*[Próxima frase em português.]*

Every sentence must appear as a pair. Do not skip, summarise, or merge sentences.
Dialogue lines count as individual sentences. Aim for ~300–400 words in Portuguese.

---

## Grammar Notes

**Target structures used in this story:**

For each grammar point, write ONE bullet with:
- The structure name in bold
- One direct example sentence pulled from the story (quote it exactly)
- A one-line explanation of the rule

Example format:
- **Estar a + Infinitivo**: *"Ela estava a ler o jornal"* — used for an action in progress at a specific moment in the past

---

## Vocabulary

**Nouns**

List 10–15 key nouns, phrases, and expressions from the story as a markdown table:

| Portuguese | English |
|---|---|
| [word or phrase] | [translation] |

---

**Verbs**

For each key verb used in the story (aim for 5–8 verbs), use this exact format — the verb name and its gloss must be on a single inline line:

***ter*** — *to have (irregular)*

| Tense | Eu | Tu | Ele/Ela | Nós | Eles/Elas |
|---|---|---|---|---|---|
| Present | ... | ... | ... | ... | ... |
| Past | ... | ... | ... | ... | ... |
| Future | ... | ... | ... | ... | ... |

Separate each verb table with a horizontal rule (`---`). Prioritise irregular verbs and the chapter's target grammar structures.
"""


def build_user_prompt(chapter: dict, genre: dict, book_level: str, inspiration: str = "") -> str:
    """Assemble the user prompt string from chapter, genre, and optional inspiration."""
    grammar_list = "\n".join(f"  - {g}" for g in chapter["grammar"])
    objectives_list = "\n".join(f"  - {o}" for o in chapter["objectives"])

    inspiration_block = ""
    if inspiration and inspiration.strip():
        inspiration_block = f"""
**Story inspiration (use this as a starting point — adapt freely to fit the genre and grammar):**
{inspiration.strip()}
"""

    return f"""Write a story for this chapter:

**Book level:** {book_level}
**Chapter:** {chapter['id']} — {chapter['title']}

**Target grammar structures:**
{grammar_list}

**Learning objectives (what participants should be able to do after):**
{objectives_list}

**Literary genre:** {genre['name']}
**Genre guidance:** {genre['description']}
{inspiration_block}
Remember:
- Use the grammar structures NATURALLY within the story — do not force or highlight them
- Commit fully to the genre — it should feel like a real example of that genre, not a parody
- European Portuguese only (not Brazilian) — use vocabulary, spelling, and register appropriate for Portugal
- Keep Portuguese version 300-400 words
- Grammar notes should reference actual sentences from your story
"""


def parse_prompt_file(path: Path) -> tuple[str, str]:
    """Parse a .txt prompt file into (system_prompt, user_prompt)."""
    text = path.read_text(encoding="utf-8")
    user_marker = "=== USER PROMPT ==="
    if user_marker not in text:
        raise ValueError(f"Could not find '{user_marker}' in {path}")
    _, user_part = text.split(user_marker, 1)
    user_prompt = user_part.lstrip("\n")

    system_marker = "=== SYSTEM PROMPT ==="
    sep_marker = "=" * 60
    if system_marker in text:
        after_system = text.split(system_marker, 1)[1].lstrip("\n")
        system_prompt = after_system.split(sep_marker)[0].rstrip("\n")
    else:
        system_prompt = SYSTEM_PROMPT

    return system_prompt, user_prompt
