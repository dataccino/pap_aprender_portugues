# Portuguese and Play — Story Generator

A CLI tool that generates bilingual (PT/EN) short stories for each chapter of your A1/A2 and B1 European Portuguese textbooks. Each story targets the chapter's grammar structures, is written in a specific literary genre, and outputs structured markdown with a bilingual sentence-by-sentence layout, grammar notes, vocabulary tables, and verb conjugation tables. Stories can also be exported to PDF.

---

## Setup

**Requirements:** Python 3.8+

**Install dependencies:**

```bash
pip install -r requirements.txt
```

**Set your API key** (only needed for `generate_story_md` — not required for the other commands):

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

Add that line to your `~/.zshrc` or `~/.bashrc` to avoid setting it every session.

---

## Workflow

The tool works in three explicit steps. Run them in order the first time; after that you can re-run any step independently.

### Step 1 — Generate prompt files (run once, then edit freely)

```bash
python3 cli.py generate_story_prompts
python3 cli.py generate_story_prompts --chapter A1-1   # single chapter
python3 cli.py generate_story_prompts --book a1a2      # one book only
```

Saves a `.txt` file per chapter to `./stories/`. Each file contains the system prompt and the user prompt. **Edit these files freely** — the next step always reads from them, so your edits are preserved.

### Step 2 — Generate story markdown

There are two ways to do this — choose whichever suits the session:

#### Option A: Via the Anthropic API (unattended)

```bash
python3 cli.py generate_story_md
python3 cli.py generate_story_md --chapter A1-1
python3 cli.py generate_story_md --book b1
```

Reads `.txt` files from `./stories/`, calls the Claude API, and saves `.md` story files to `./outputs/`. Requires `ANTHROPIC_API_KEY`. Warns if a prompt file is missing (run Step 1 first).

#### Option B: Via Claude Code CLI (interactive, no API key needed)

If you have [Claude Code](https://claude.ai/code) installed, you can ask Claude to generate stories directly in your terminal without calling the API yourself. Claude reads the `.txt` prompt files, generates the story, and writes the `.md` file — no API key or script invocation required.

**Generate a single story:**
> "Please generate the story for A1-1 using the prompt in `stories/A1-1_absurdist-comedy.txt` and save it to `outputs/`"

**Generate multiple stories:**
> "Please generate stories for all A1/A2 chapters using the prompt files in `stories/` and save them to `outputs/`"

**After editing a prompt:**
> "I've edited `stories/B1-3_magical-realism.txt` — please regenerate the story and save it to `outputs/`"

Claude reads the prompt file directly, generates the content, and writes the `.md` file using the same format as the API path. You can then run `generate_story_pdf` as normal to produce the PDF.

### Step 3 — Generate PDFs (no API call)

```bash
python3 cli.py generate_story_pdf
python3 cli.py generate_story_pdf --chapter A1-1
```

Converts `.md` files in `./outputs/` to `.pdf`. No API key required.

---

## All Options

### `generate_story_prompts`

| Flag | Description |
|------|-------------|
| `--book a1a2\|b1\|both` | Which book(s) to generate prompts for — default: `both` |
| `--chapter ID` | Single chapter, e.g. `--chapter A1-1` |
| `--inspire "TEXT"` | Optional plot seed baked into the prompt |
| `--inspire-file FILE` | Read inspiration from a file instead |
| `--prompts-dir DIR` | Where to save `.txt` files — default: `./stories` |

### `generate_story_md`

| Flag | Description |
|------|-------------|
| `--book a1a2\|b1\|both` | Which book(s) to generate — default: `both` |
| `--chapter ID` | Single chapter |
| `--prompts-dir DIR` | Where to read `.txt` files from — default: `./stories` |
| `--output DIR` | Where to save `.md` files — default: `./outputs` |
| `--delay SECONDS` | Pause between API calls — default: `2.0` |

### `generate_story_pdf`

| Flag | Description |
|------|-------------|
| `--chapter ID` | Single chapter |
| `--output DIR` | Where to read `.md` and save `.pdf` files — default: `./outputs` |

---

## Adding Story Inspiration

Use `--inspire` to give a story a plot seed, character idea, or setting. It gets baked directly into the `.txt` prompt file.

**Inline:**
```bash
python3 cli.py generate_story_prompts --chapter A1-1 \
  --inspire "A woman tries to introduce herself at a party but keeps being interrupted by a fado singer."
```

**From a file** (better for longer plot notes):
```bash
python3 cli.py generate_story_prompts --chapter B1-5 --inspire-file my_plot.txt
```

> **Note:** If you use `--inspire` without `--chapter`, the same inspiration is applied to every chapter. The script will warn you when this happens.

---

## Chapter IDs

**A1/A2 (Book 1)**

| ID | Title |
|----|-------|
| `A1-1` | Identificação e Dados Pessoais |
| `A1-2` | Descrição de Objetos e Pessoas |
| `A1-3` | Breves Fórmulas Sociais |
| `A1-4` | Atividades do Quotidiano |
| `A1-5` | Relações Familiares e Habitação |
| `A2-6` | Compra e Venda |
| `A2-7` | Localização de Objetos e Pessoas |
| `A2-8` | Desporto e Tempos Livres |
| `A2-9` | Saúde e Corpo |
| `A2-10` | Serviços de Utilidade Pública |
| `A2-11` | Relatar Acontecimentos Pontuais no Passado |
| `A2-12` | Contactos Sociais e Formas de Tratamento |
| `A2-13` | Reclamar e Fazer Reclamações sobre Comida e Alojamento |
| `A2-14` | Memórias no Passado |

**B1 (Book 2)**

| ID | Title |
|----|-------|
| `B1-0` | Revisões (A2) |
| `B1-1` | Falar de Atividades do Quotidiano no Passado |
| `B1-2` | Exprimir Desejos e Fazer Planos |
| `B1-3` | Falar de Tempos Livres no Passado |
| `B1-4` | Relatos Formais de Ocorrências |
| `B1-5` | Relações Sociais — Escrever Cartas, Notas e Bilhetes |
| `B1-6` | Relatar Factos |
| `B1-7` | Relações Sociais |
| `B1-8` | Atualidades |
| `B1-9` | Relações Sociais — Vida Privada e Tempos Livres |
| `B1-10` | Viagens e Deslocações |
| `B1-11` | Trabalho e Profissões |
| `B1-12` | Argumentar e Negociar Propostas |

---

## Literary Genres

Genres cycle across chapters in this order, repeating as needed:

1. Absurdist Comedy
2. Rom-com
3. Magical Realism
4. Noir / Crime Thriller
5. Telenovela Drama
6. Fairy Tale / Fábula
7. Horror / Suspense
8. Epistolary (letters, texts, diary entries)

---

## Story Output Format

Each generated story produces a `.md` file (and optionally a `.pdf`). The content contains:

- **Bilingual Story** — every sentence as an EN/PT pair, English first then Portuguese beneath
- **Grammar Notes** — each target grammar structure with an example sentence pulled directly from the story
- **Vocabulary** — key nouns/phrases table, plus a full conjugation table (Present / Past / Future × 6 persons) for each key verb

---

## Module Structure

The project is split into focused modules:

| Module | Responsibility | Key functions |
|--------|---------------|---------------|
| `curriculum.py` | All static textbook data | `A1A2_CHAPTERS`, `B1_CHAPTERS`, `GENRES` — chapter definitions, grammar targets, objectives, and genre cycling order |
| `prompts.py` | Prompt building and parsing | `SYSTEM_PROMPT` — the constant sent to Claude on every call; `build_user_prompt()` — assembles the user prompt from chapter/genre/inspiration data; `parse_prompt_file()` — reads a `.txt` file back into `(system_prompt, user_prompt)` |
| `api_client.py` | Anthropic API calls | `generate_story_md()` — reads a `.txt` prompt file, calls the Claude API, and returns the story content as a string |
| `output.py` | All file I/O for writing | `save_prompt()` — writes a prompt to a `.txt` file in `stories/`; `save_story()` — writes story content to a `.md` file with YAML frontmatter; `build_pdf()` — converts markdown to PDF via weasyprint; `build_pdfs_from_dir()` — batch PDF generation from a directory; `write_index()` — writes `INDEX.md`; `write_all_prompts()` — writes `ALL_PROMPTS.md` |
| `cli.py` | CLI entry point | `main()` — parses subcommands and routes to `cmd_generate_story_prompts()`, `cmd_generate_story_md()`, or `cmd_generate_story_pdf()` |

---

## Output Files

After a full run, `./stories/` and `./outputs/` will contain:

```
stories/
├── INDEX.md
├── ALL_PROMPTS.md
├── A1-1_absurdist-comedy.txt      ← edit these freely
├── A1-2_rom-com.txt
├── ...
└── B1-12_noir-crime-thriller.txt

outputs/
├── INDEX.md
├── A1-1_absurdist-comedy.md
├── A1-1_absurdist-comedy.pdf
├── A1-2_rom-com.md
├── A1-2_rom-com.pdf
├── ...
├── B1-12_noir-crime-thriller.md
└── B1-12_noir-crime-thriller.pdf
```
