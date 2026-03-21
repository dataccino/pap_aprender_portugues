#!/usr/bin/env python3
"""
Portuguese and Play — Story Generator
Generates bilingual (PT/EN) stories for each chapter of your textbooks,
cycling through literary genres, with grammar notes in markdown.

Usage:
    python generate_stories.py                  # generate all chapters
    python generate_stories.py --book a1a2      # just book 1
    python generate_stories.py --book b1        # just book 2
    python generate_stories.py --chapter "A1-1" # single chapter
    python generate_stories.py --dry-run        # print prompts without calling API
"""

import anthropic
import argparse
import json
import os
import re
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# CURRICULUM DATA
# Extracted from your textbook indexes (images 1–4)
# ---------------------------------------------------------------------------

A1A2_CHAPTERS = [
    {
        "id": "A1-1",
        "title": "Identificação e Dados Pessoais",
        "grammar": [
            "Pronomes pessoais, interrogativos, reflexivos (1.ª/3.ª pessoa do singular)",
            "Verbos ser, ter, morar em, chamar-se — Presente do Indicativo",
        ],
        "objectives": ["Identificar-se a si e ao outro"],
    },
    {
        "id": "A1-2",
        "title": "Descrição de Objetos e Pessoas",
        "grammar": [
            "Verbos ter, ser/estar + adjetivo, verbos regulares em -er e -ir — Presente do Indicativo",
            "Nomes/adjetivos: concordância em género e número",
        ],
        "objectives": ["Caracterizar-se a si e ao outro"],
    },
    {
        "id": "A1-3",
        "title": "Breves Fórmulas Sociais",
        "grammar": ["Pronomes reflexivos"],
        "objectives": [
            "Cumprimentar / despedir-se de alguém",
            "Apresentar-se / apresentar alguém",
            "Agradecer",
        ],
    },
    {
        "id": "A1-4",
        "title": "Atividades do Quotidiano",
        "grammar": [
            "Verbos irregulares — Presente do Indicativo",
            "Costumar + Infinitivo",
            "Preposições de tempo (a, de, em) e movimento (a, para, por, de)",
            "Ir de (transporte não específico) / Ir em (transporte específico)",
        ],
        "objectives": ["Saber pedir / dar informações", "Descrever sequências de ações"],
    },
    {
        "id": "A1-5",
        "title": "Relações Familiares e Habitação",
        "grammar": [
            "Estar a + Infinitivo / Presente",
            "Pronomes possessivos",
            "Adjetivos — graus",
        ],
        "objectives": ["Descrever a família", "Descrever a casa"],
    },
    {
        "id": "A2-6",
        "title": "Compra e Venda",
        "grammar": [
            "Pretérito Imperfeito (cortesia — 1.ª pessoa singular/plural)",
            "Presente do Indicativo (verbos com alternância vocálica: vestir, preferir, etc.)",
            "Pronomes demonstrativos",
            "Advérbios de lugar",
        ],
        "objectives": ["Fazer um pedido", "Aceitar / rejeitar", "Perguntar o preço", "Pagar"],
    },
    {
        "id": "A2-7",
        "title": "Localização de Objetos e Pessoas",
        "grammar": [
            "Estar em + locuções prepositivas",
            "Verbos virar, ir/seguir, atravessar — Presente do Indicativo",
            "Preposições e locuções prepositivas de espaço e movimento",
        ],
        "objectives": [
            "Pedir / dar informações sobre localização de objetos no espaço",
            "Pedir / dar informações sobre localização geográfica e direções",
        ],
    },
    {
        "id": "A2-8",
        "title": "Desporto e Tempos Livres",
        "grammar": [
            "Gostar de / não gostar de / detestar / adorar — Presente do Indicativo",
            "Ir + Infinitivo (futuro próximo)",
            "Expressões de tempo futuro",
            "Preposições com + pronome pessoal",
        ],
        "objectives": [
            "Falar de gostos e preferências",
            "Exprimir futuro próximo",
            "Falar do tempo",
            "Fazer / aceitar / recusar convites",
        ],
    },
    {
        "id": "A2-9",
        "title": "Saúde e Corpo",
        "grammar": [
            "Estar com + nome (febre, dores de cabeça, etc.)",
            "Ter que / de + Infinitivo",
            "Dever + Infinitivo",
        ],
        "objectives": [
            "Falar sobre o corpo e estado físico",
            "Saber ir ao médico / farmácia",
            "Compreender instruções simples no médico",
        ],
    },
    {
        "id": "A2-10",
        "title": "Serviços de Utilidade Pública",
        "grammar": [
            "Verbos — Imperfeito do Indicativo (expressão de cortesia)",
            "Poder + Infinitivo",
        ],
        "objectives": [
            "Preencher impressos simples",
            "Compreender instruções e avisos simples",
        ],
    },
    {
        "id": "A2-11",
        "title": "Relatar Acontecimentos Pontuais no Passado",
        "grammar": [
            "Pretérito Perfeito Simples do Indicativo (regulares e irregulares: ser, ir, ter, estar)",
            "Alterações gráficas nos verbos",
            "Expressões de tempo no passado: há / desde",
        ],
        "objectives": [
            "Descrever uma sequência de ações no passado",
            "Ter noção de passado pontual",
        ],
    },
    {
        "id": "A2-12",
        "title": "Contactos Sociais e Formas de Tratamento",
        "grammar": [
            "Pretérito Perfeito Simples — verbos irregulares terminados em -air",
            "Pronomes pessoais: tu / você / o senhor / a senhora",
        ],
        "objectives": [
            "Dominar as formas de tratamento em português",
            "Escrever um postal / deixar mensagens orais e breves",
            "Escrever um convite",
        ],
    },
    {
        "id": "A2-13",
        "title": "Reclamar e Fazer Reclamações sobre Comida e Alojamento",
        "grammar": [
            "Pretérito Imperfeito do Indicativo",
            "Exprimir desejo (querer / desejar + Infinitivo / nome)",
        ],
        "objectives": ["Fazer uma reclamação simples sobre um serviço", "Exprimir desejo"],
    },
    {
        "id": "A2-14",
        "title": "Memórias no Passado",
        "grammar": [
            "Pretérito Imperfeito do Indicativo (regulares e irregulares)",
            "Expressões de tempo: antigamente, dantes, noutros tempos",
            "Pronomes indefinidos",
        ],
        "objectives": [
            "Relatar ações habituais no passado",
            "Falar de memórias passadas",
            "Falar de horas e idade no passado",
        ],
    },
]

B1_CHAPTERS = [
    {
        "id": "B1-0",
        "title": "Revisões (A2)",
        "grammar": [
            "Pretérito Perfeito Simples / Presente do Indicativo (revisão)",
            "Preposições de tempo e movimento",
            "Pronomes possessivos e demonstrativos",
        ],
        "objectives": ["Relembrar aspetos gramaticais associados ao nível A2"],
    },
    {
        "id": "B1-1",
        "title": "Falar de Atividades do Quotidiano no Passado",
        "grammar": [
            "Pretérito Imperfeito: idade/horas/aspeto durativo e frequentativo",
            "Costumar + Infinitivo",
            "Imperfeito vs. Presente do Indicativo",
        ],
        "objectives": ["Relatar ações habituais no passado e comparar com o presente"],
    },
    {
        "id": "B1-2",
        "title": "Exprimir Desejos e Fazer Planos",
        "grammar": [
            "Pretérito Imperfeito: querer / desejar / gostar de / preferir / apetecer",
            "Advérbios de lugar, tempo, modo, negação, afirmação, quantidade",
            "Colocação dos advérbios na frase",
        ],
        "objectives": ["Exprimir desejos", "Fazer planos", "Fazer reservas", "Fazer pedidos"],
    },
    {
        "id": "B1-3",
        "title": "Falar de Tempos Livres no Passado",
        "grammar": [
            "Pretérito Imperfeito: enquanto / quando (estar a + infinitivo)",
            "Imperfeito vs. Pretérito Perfeito Simples",
            "Fazer descrições no passado",
        ],
        "objectives": [
            "Relatar ações simultâneas e durativas no passado",
            "Distinguir ações prolongadas vs. pontuais no passado",
        ],
    },
    {
        "id": "B1-4",
        "title": "Relatos Formais de Ocorrências",
        "grammar": [
            "Pretérito Mais-que-Perfeito Composto do Indicativo",
            "Particípios passados (regulares e irregulares)",
            "Pronomes clíticos: complemento direto e sua colocação na frase",
        ],
        "objectives": ["Relatar acontecimentos aos bombeiros / polícia / serviços de saúde"],
    },
    {
        "id": "B1-5",
        "title": "Relações Sociais — Escrever Cartas, Notas e Bilhetes",
        "grammar": [
            "Pretérito Perfeito Composto do Indicativo",
            "Pronomes clíticos: complemento indireto e sua colocação na frase",
        ],
        "objectives": [
            "Relatar ações durativas com realização não terminada",
            "Escrever cartas / notas / bilhetes",
            "Fazer pedidos",
        ],
    },
    {
        "id": "B1-6",
        "title": "Relatar Factos",
        "grammar": [
            "Discurso direto / Discurso indireto",
            "Pronomes clíticos: regras de colocação com tempos compostos",
        ],
        "objectives": ["Relatar factos usando o discurso indireto"],
    },
    {
        "id": "B1-7",
        "title": "Relações Sociais",
        "grammar": ["Verbos — Modo Imperativo (regulares e irregulares)"],
        "objectives": [
            "Compreender textos publicitários / informativos / médicos",
            "Dar conselhos / fazer sugestões",
            "Dar ordens / fazer pedidos",
        ],
    },
    {
        "id": "B1-8",
        "title": "Atualidades",
        "grammar": [
            "Voz ativa / Voz passiva (transformação de frases)",
            "Passiva com ser e estar",
            "Partícula apassivante -se",
            "Particípios passados duplos",
        ],
        "objectives": [
            "Compreender notícias simples da imprensa escrita",
            "Relatar factos do quotidiano / notícias",
        ],
    },
    {
        "id": "B1-9",
        "title": "Relações Sociais — Vida Privada e Tempos Livres",
        "grammar": [
            "Futuro Imperfeito do Indicativo (regulares e verbos em -zer)",
            "Haver de + Infinitivo / Ter de + Infinitivo",
            "Verbos — Modo Condicional",
            "Discurso Indireto com futuro imperfeito → modo condicional",
        ],
        "objectives": [
            "Relatar acontecimentos futuros",
            "Exprimir intenção e obrigação em relação a um acontecimento futuro",
            "Expressar desejos de difícil realização",
            "Relatar em linguagem formal no discurso indireto",
        ],
    },
    {
        "id": "B1-10",
        "title": "Viagens e Deslocações",
        "grammar": [
            "Infinitivo pessoal / Infinitivo impessoal",
            "Expressões impessoais (ser / achar + adjetivo)",
            "Preposições e locuções prepositivas",
            "Interrogativas com pronome interrogativo e preposição",
        ],
        "objectives": [
            "Relatar sequências de ações",
            "Pedir informações sobre rotas e destinos turísticos",
        ],
    },
    {
        "id": "B1-11",
        "title": "Trabalho e Profissões",
        "grammar": [
            "Pronomes indefinidos",
            "Conjugação perifrástica: começar a / estar a / andar a / deixar de / acabar de",
            "Pronomes clíticos: contração do complemento direto com complemento indireto",
        ],
        "objectives": [
            "Pedir / dar informações sobre assuntos de rotina relacionados com trabalho ou estudo",
            "Elaborar um currículo profissional",
            "Responder a um anúncio de emprego",
            "Escrever uma carta formal",
        ],
    },
    {
        "id": "B1-12",
        "title": "Argumentar e Negociar Propostas",
        "grammar": [
            "Verbos com regência de preposição",
            "Verbos específicos: apanhar / agarrar / pegar / pegar-se / tomar",
        ],
        "objectives": ["Fazer propostas e contrapropostas", "Argumentar"],
    },
]

# ---------------------------------------------------------------------------
# GENRES — cycling order
# ---------------------------------------------------------------------------

GENRES = [
    {
        "name": "Absurdist Comedy",
        "description": (
            "Kafka-meets-Machado de Assis absurdism. Logic is internally consistent but "
            "the premise is completely ridiculous. Deadpan delivery. Bureaucracy, existential "
            "mundanity, or surreal social situations. No winking at the audience."
        ),
    },
    {
        "name": "Rom-com",
        "description": (
            "Warm, witty romantic comedy. Misunderstandings, meet-cutes, near-misses. "
            "Characters are charming and slightly ridiculous. Happy or hopeful ending. "
            "Set in Lisbon or another Portuguese-speaking city."
        ),
    },
    {
        "name": "Magical Realism",
        "description": (
            "In the tradition of Saramago or Clarice Lispector. The magical element is "
            "treated as perfectly ordinary. Lyrical prose. The supernatural illuminates "
            "something true about everyday life."
        ),
    },
    {
        "name": "Noir / Crime Thriller",
        "description": (
            "Hardboiled, atmospheric, morally ambiguous. Rain, secrets, unreliable characters. "
            "The language is clipped and precise. Set in a Portuguese-speaking city. "
            "Could be a mystery, a heist, or a simple case gone wrong. "
            "Find the comedy in the detective's wounded pride, the criminal's petty grievances, "
            "or the sheer bureaucratic indignity of Portuguese crime."
        ),
    },
    {
        "name": "Telenovela Drama",
        "description": (
            "Maximum emotional intensity. Secret identities, betrayal, long-lost relatives, "
            "passionate declarations. Melodrama played completely straight. Every scene is "
            "a revelation or a confrontation. "
            "The comedy lives in the excess itself — a declaration so overwrought it tips into "
            "the sublime, a revelation so improbable the characters accept it without blinking. "
            "Play it straight; let the reader do the laughing."
        ),
    },
    {
        "name": "Fairy Tale / Fábula",
        "description": (
            "Classic fairy tale structure with a Portuguese or Lusophone folkloric flavour. "
            "Clear moral lesson. Archetypal characters (the clever fisherman, the vain queen, "
            "the honest cobbler). Language is simple and rhythmic."
        ),
    },
    {
        "name": "Horror / Suspense",
        "description": (
            "Atmospheric dread. Something is wrong, but we're not sure what. "
            "Could be supernatural or psychological. Restraint over gore. "
            "The horror emerges through language and detail, not explicit description. "
            "Include one beat of dark comedy — the mundane detail that makes the uncanny worse, "
            "a character's wildly inappropriate reaction, or the absurdity of being terrified "
            "by something that is also, undeniably, a little bit silly."
        ),
    },
    {
        "name": "Epistolary",
        "description": (
            "Told entirely through letters, text messages, diary entries, social media posts, "
            "or voice notes. The format IS the story. The gaps between messages matter as much "
            "as what is said. Characters reveal themselves through how they write. "
            "Mine the comedy of tone — the person who is far too formal in a WhatsApp, "
            "the diary entry that catastrophises something tiny, the passive-aggressive postscript."
        ),
    },
]

# ---------------------------------------------------------------------------
# PROMPT TEMPLATE
# ---------------------------------------------------------------------------

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

Output format — STRICT MARKDOWN:

# [Story Title in Portuguese]
### *[Subtitle/genre tag in italics]*

---

## 🇵🇹 Versão Portuguesa

[Full story in European Portuguese, ~300-400 words]

---

## 🇬🇧 English Version

[Full story in English, same ~300-400 words — faithful translation, not a simplified version]

---

## 🔀 Line by Line

Render the story sentence by sentence, English first then Portuguese beneath it.
Use this exact format for every sentence — no blank lines within a pair, one blank line between pairs:

*[English sentence.]*
[Frase em português.]

*[Next English sentence.]*
[Próxima frase em português.]

Every sentence from the story must appear here. Do not skip, summarise, or merge sentences.
Dialogue lines count as individual sentences.

---

## 📚 Grammar Notes

**Target structures used in this story:**

For each grammar point, write ONE bullet with:
- The structure name in bold
- One direct example sentence pulled from the story (quote it exactly)
- A one-line explanation of the rule

Example format:
- **Estar a + Infinitivo**: *"Ela estava a ler o jornal"* — used for an action in progress at a specific moment in the past

---

## 🎭 Genre Notes

One short paragraph (3-5 sentences) explaining which genre conventions you used and why, 
so the teacher (Astrid) can brief participants before reading."""

def build_user_prompt(chapter: dict, genre: dict, book_level: str, inspiration: str = "") -> str:
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

# ---------------------------------------------------------------------------
# GENERATION
# ---------------------------------------------------------------------------

def generate_story(client, chapter: dict, genre: dict, book_level: str, dry_run: bool = False, prompts_only: bool = False, inspiration: str = "") -> str:
    user_prompt = build_user_prompt(chapter, genre, book_level, inspiration)

    if dry_run or prompts_only:
        if dry_run:
            print(f"\n{'='*60}")
            print(f"DRY RUN: {chapter['id']} — {chapter['title']} [{genre['name']}]")
            print(f"{'='*60}")
            print(user_prompt)
        return user_prompt  # return the raw prompt instead of a story

    print(f"  Generating {chapter['id']} — {chapter['title']} [{genre['name']}]...", end="", flush=True)

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    content = message.content[0].text
    print(" ✓")
    return content


def save_story(content: str, chapter: dict, genre: dict, output_dir: Path, prompts_only: bool = False):
    safe_id = chapter["id"].replace("/", "-")
    safe_genre = genre["name"].lower().replace(" / ", "-").replace(" ", "-")

    if prompts_only:
        filename = f"{safe_id}_{safe_genre}.txt"
        filepath = output_dir / filename
        sep = "=" * 60
        header = f"=== SYSTEM PROMPT ===\n\n{SYSTEM_PROMPT}\n\n{sep}\n=== USER PROMPT ===\n\n"
        filepath.write_text(header + content, encoding="utf-8")
        return filepath

    filename = f"{safe_id}_{safe_genre}.md"
    filepath = output_dir / filename
    ch_id = chapter["id"]
    ch_title = chapter["title"]
    g_name = genre["name"]
    grammar_json = json.dumps(chapter["grammar"])
    obj_json = json.dumps(chapter["objectives"])
    frontmatter = f"---\nchapter: {ch_id}\ntitle: {ch_title}\ngenre: {g_name}\ngrammar: {grammar_json}\nobjectives: {obj_json}\n---\n\n"
    filepath.write_text(frontmatter + content, encoding="utf-8")
    return filepath


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Portuguese and Play story generator")
    parser.add_argument("--book", choices=["a1a2", "b1", "both"], default="both")
    parser.add_argument("--chapter", help="Generate a single chapter by ID (e.g. A1-1)")
    parser.add_argument("--dry-run", action="store_true", help="Print prompts to terminal, no API calls")
    parser.add_argument("--prompts-only", action="store_true", help="Save prompts as .txt files — no API calls")
    parser.add_argument("--output", default="./stories", help="Output directory (default: ./stories)")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds between API calls")
    parser.add_argument("--inspire", metavar="TEXT",
                        help="Optional story inspiration (plot seed, characters, setting). "
                             "Only meaningful with --chapter. Enclose in quotes.")
    parser.add_argument("--inspire-file", metavar="FILE",
                        help="Read story inspiration from a text file. "
                             "Only meaningful with --chapter.")
    args = parser.parse_args()

    prompts_only = args.prompts_only

    # Load inspiration text (inline string or file)
    inspiration = ""
    if getattr(args, "inspire_file", None):
        inspire_path = Path(args.inspire_file)
        if not inspire_path.exists():
            print(f"⚠️  --inspire-file not found: {inspire_path}")
        else:
            inspiration = inspire_path.read_text(encoding="utf-8")
    elif getattr(args, "inspire", None):
        inspiration = args.inspire

    if inspiration and not args.chapter:
        print("⚠️  --inspire / --inspire-file work best with --chapter (inspiration will be applied to all chapters)")

    all_chapters = []
    if args.book in ("a1a2", "both"):
        all_chapters += [("A1/A2", ch) for ch in A1A2_CHAPTERS]
    if args.book in ("b1", "both"):
        all_chapters += [("B1", ch) for ch in B1_CHAPTERS]

    if args.chapter:
        all_chapters = [(level, ch) for level, ch in all_chapters if ch["id"] == args.chapter]
        if not all_chapters:
            print(f"Chapter '{args.chapter}' not found.")
            return

    chapters_with_genres = [
        (level, ch, GENRES[i % len(GENRES)])
        for i, (level, ch) in enumerate(all_chapters)
    ]

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    client = None if (args.dry_run or prompts_only) else anthropic.Anthropic()

    mode = "prompts-only (no API)" if prompts_only else ("dry-run" if args.dry_run else "API generation")
    print(f"\n🇵🇹 Portuguese and Play — Story Generator")
    print(f"   Mode:     {mode}")
    print(f"   Chapters: {len(chapters_with_genres)}")
    print(f"   Output:   {output_dir.resolve()}\n")

    generated = []
    errors = []

    for i, (level, chapter, genre) in enumerate(chapters_with_genres):
        try:
            content = generate_story(client, chapter, genre, level, args.dry_run, prompts_only, inspiration)
            if prompts_only:
                print(f"  Saved: {chapter['id']} — {chapter['title']} [{genre['name']}]")
            filepath = save_story(content, chapter, genre, output_dir, prompts_only)
            generated.append(filepath)

            if not args.dry_run and not prompts_only and i < len(chapters_with_genres) - 1:
                time.sleep(args.delay)

        except Exception as e:
            print(f" ✗ ERROR: {e}")
            errors.append((chapter["id"], str(e)))

    if prompts_only:
        all_prompts_path = output_dir / "ALL_PROMPTS.md"
        with open(all_prompts_path, "w", encoding="utf-8") as f:
            f.write("# Portuguese and Play — All Prompts\n\n")
            f.write(f"_{len(generated)} prompts. Paste each into Claude or your preferred LLM._\n\n---\n\n")
            f.write(f"## System Prompt (use for ALL chapters)\n\n```\n{SYSTEM_PROMPT}\n```\n\n---\n\n")
            for level, ch, genre in chapters_with_genres:
                f.write(f"## {ch['id']} — {ch['title']} [{genre['name']}]\n\n```\n")
                f.write(build_user_prompt(ch, genre, level, inspiration))
                f.write("```\n\n---\n\n")
        print(f"\n📄 All prompts combined → {all_prompts_path}")

    print(f"\n" + "="*50)
    label = "prompts" if prompts_only else "stories"
    print(f"✅ {len(generated)} {label} → {output_dir.resolve()}")
    if errors:
        print(f"❌ Errors: {len(errors)}")
        for ch_id, err in errors:
            print(f"   {ch_id}: {err}")

    ext = "txt" if prompts_only else "md"
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
    print(f"📋 Index → {index_path}")


if __name__ == "__main__":
    main()