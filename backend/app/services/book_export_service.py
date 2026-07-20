"""G20 (#547) — eksport kampanii do powieści fabularnej (prototyp).

Z historii kampanii (tury z `campaign_turns`) buduje powieść po polsku:
materiał dzielony na rozdziały (~N tur), każdy rozdział nowelizowany lokalnym
modelem (Bielik 11B / Ollama na .170), wynik składany w plik Markdown.

W pełni offline — przeznaczone do uruchomienia z CLI (robota nocna, szybkość
bez znaczenia, zgodnie z zasadą CZĘŚCI AG). Bez UI gracza (to dopiero FAZA G).

Rdzeń jest deterministyczny i testowalny (fetch / chunk / prompt / assemble);
sam `novelize_chapter` to cienki klient HTTP do Ollama, mockowalny w testach.

Użycie:
    python -m app.services.book_export_service <campaign_id> \
        [--per 6] [--max-chapters N] [--model NAZWA] [--out plik.md]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import sys
import urllib.request
from typing import List, Optional
from app.core.db_runtime import resolve_db_path

DB_PATH = resolve_db_path()

# Bielik 11B (wariant Q6_K — lepsze dialogi; offline więc szybkość nieistotna).
# Zapasowo: gemma4:12b / qwen3.6 — patrz issue #547.
DEFAULT_MODEL = "SpeakLeash/bielik-11b-v2.3-instruct-imatrix:Q6_K"
OLLAMA_HOST = os.getenv("BOOK_OLLAMA_HOST", "http://192.168.1.170:11434")
DEFAULT_TURNS_PER_CHAPTER = 6  # wartość startowa do dostrojenia (Numbers Policy)


# ── DB ────────────────────────────────────────────────────────────────────────

def _open_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_campaign_history(campaign_id: int, conn: Optional[sqlite3.Connection] = None) -> dict:
    """Pobiera tytuł kampanii i wszystkie jej tury, posortowane po turn_number."""
    own = conn is None
    conn = conn or _open_db()
    try:
        title_row = conn.execute(
            "SELECT title FROM campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
        title = title_row["title"] if title_row else f"Kampania {campaign_id}"
        rows = conn.execute(
            "SELECT turn_number, route, user_text, assistant_text "
            "FROM campaign_turns WHERE campaign_id = ? "
            "ORDER BY turn_number ASC, id ASC",
            (campaign_id,),
        ).fetchall()
        turns = [
            {
                "turn_number": r["turn_number"],
                "route": r["route"],
                "user_text": r["user_text"] or "",
                "assistant_text": r["assistant_text"] or "",
            }
            for r in rows
        ]
        return {"campaign_id": campaign_id, "title": title, "turns": turns}
    finally:
        if own:
            conn.close()


# ── Podział na rozdziały ────────────────────────────────────────────────────────

def chunk_into_chapters(turns: List[dict], turns_per_chapter: int = DEFAULT_TURNS_PER_CHAPTER) -> List[List[dict]]:
    """Dzieli listę tur na rozdziały po `turns_per_chapter`, zachowując kolejność."""
    if not turns:
        return []
    per = max(1, int(turns_per_chapter))
    return [turns[i : i + per] for i in range(0, len(turns), per)]


# ── Prompt nowelizacji ──────────────────────────────────────────────────────────

_SYSTEM_RULES = (
    "Jesteś polskim pisarzem fantasy. Przepisujesz zapis sesji RPG na rozdział "
    "powieści. UWAGA: materiał źródłowy jest pisany w DRUGIEJ osobie ('wchodzisz', "
    "'widzisz') — TWOIM ZADANIEM jest przełożyć go na TRZECIĄ osobę. ZASADY (bezwzględne):\n"
    "1. Pisz po POLSKU, prozą literacką, w TRZECIEJ osobie czasu przeszłego "
    "('bohater wszedł', 'zobaczył'). NIGDY nie pisz 'ty' ani 'ocknąłeś się' — "
    "zawsze 'on/bohater'.\n"
    "2. Używaj DIALOGÓW (myślniki dialogowe), opisów i wewnętrznych myśli bohatera.\n"
    "3. Trzymaj STAŁY styl między rozdziałami (spójny ton, narrator wszechwiedzący).\n"
    "4. Opisuj WYŁĄCZNIE zdarzenia obecne w materiale źródłowym — NIE WYMYŚLAJ "
    "nowych postaci, miejsc, przedmiotów ani zwrotów akcji. NIE DODAWAJ wydarzeń, "
    "których nie ma w zapisie. Wolno literacko rozwinąć opis, nie fakty.\n"
    "5. Zwróć WYŁĄCZNIE tekst rozdziału (bez nagłówków, komentarzy, listy faktów)."
)


def _format_source_turns(chapter_turns: List[dict]) -> str:
    parts = []
    for t in chapter_turns:
        if t.get("user_text"):
            parts.append(f"[Gracz] {t['user_text']}")
        if t.get("assistant_text"):
            parts.append(f"[Mistrz Gry] {t['assistant_text']}")
    return "\n\n".join(parts)


def build_chapter_prompt(
    chapter_turns: List[dict],
    chapter_index: int,
    total_chapters: int,
    prev_summary: Optional[str] = None,
) -> str:
    """Buduje pełny prompt dla jednego rozdziału (kontrakt: PL, 3. osoba, dialogi,
    zakaz halucynacji, materiał źródłowy w treści)."""
    header = (
        f"{_SYSTEM_RULES}\n\n"
        f"To rozdział {chapter_index + 1} z {total_chapters}.\n"
    )
    if prev_summary:
        header += (
            "\nKONTEKST POPRZEDNIEGO ROZDZIAŁU (dla ciągłości, NIE powtarzaj go):\n"
            f"{prev_summary}\n"
        )
    source = _format_source_turns(chapter_turns)
    return (
        f"{header}\n"
        "MATERIAŁ ŹRÓDŁOWY (zapis sesji — przepisz na prozę, nic nie dodawaj):\n"
        f"-----\n{source}\n-----\n\n"
        "Napisz teraz ten rozdział powieści po polsku:"
    )


# ── Klient Ollama (mockowalny) ───────────────────────────────────────────────────

def novelize_chapter(
    prompt: str,
    model: str = DEFAULT_MODEL,
    host: str = OLLAMA_HOST,
    timeout: int = 600,
) -> str:
    """Wysyła prompt do Ollama (/api/generate) i zwraca tekst rozdziału."""
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.7},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{host.rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.load(resp)
    return (body.get("response") or "").strip()


# ── Składanie Markdown ────────────────────────────────────────────────────────

def assemble_book_markdown(title: str, chapter_texts: List[str]) -> str:
    """Składa plik: # tytuł, potem ## Rozdział N + treść, w kolejności."""
    out = [f"# {title}", ""]
    for i, text in enumerate(chapter_texts, start=1):
        out.append(f"## Rozdział {i}")
        out.append("")
        out.append(text.strip())
        out.append("")
    return "\n".join(out).rstrip() + "\n"


# ── Orkiestrator ──────────────────────────────────────────────────────────────

def export_campaign_book(
    campaign_id: int,
    turns_per_chapter: int = DEFAULT_TURNS_PER_CHAPTER,
    max_chapters: Optional[int] = None,
    model: str = DEFAULT_MODEL,
    host: str = OLLAMA_HOST,
) -> str:
    """Pełny przebieg: DB → rozdziały → nowelizacja → Markdown. Zwraca treść pliku."""
    data = fetch_campaign_history(campaign_id)
    chapters = chunk_into_chapters(data["turns"], turns_per_chapter)
    if max_chapters is not None:
        chapters = chapters[:max_chapters]
    total = len(chapters)

    chapter_texts: List[str] = []
    prev_summary: Optional[str] = None
    for idx, chapter_turns in enumerate(chapters):
        prompt = build_chapter_prompt(chapter_turns, idx, total, prev_summary)
        text = novelize_chapter(prompt, model=model, host=host)
        chapter_texts.append(text)
        # streszczenie = pierwszy akapit, jako kontekst ciągłości dla następnego
        prev_summary = text.split("\n\n", 1)[0][:600] if text else None

    book_title = f"{data['title']} — kronika"
    return assemble_book_markdown(book_title, chapter_texts)


# ── CLI ─────────────────────────────────────────────────────────────────────────

def _main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Eksport kampanii do powieści (G20 #547).")
    ap.add_argument("campaign_id", type=int)
    ap.add_argument("--per", type=int, default=DEFAULT_TURNS_PER_CHAPTER, help="tur na rozdział")
    ap.add_argument("--max-chapters", type=int, default=None, help="limit rozdziałów (pilot)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--host", default=OLLAMA_HOST)
    ap.add_argument("--out", default=None, help="ścieżka pliku .md (domyślnie stdout)")
    args = ap.parse_args(argv)

    md = export_campaign_book(
        args.campaign_id,
        turns_per_chapter=args.per,
        max_chapters=args.max_chapters,
        model=args.model,
        host=args.host,
    )
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"Zapisano: {args.out} ({len(md)} znaków)", file=sys.stderr)
    else:
        sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
