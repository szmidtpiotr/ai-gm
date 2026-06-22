#!/usr/bin/env python3
"""W6 (#907) — generator ludzkiego changelogu dla wizytówki.

Czyta CHANGELOG.md (format: `## vX.Y.Z — YYYY-MM-DD — opis`, sekcje `### Added/...`,
bullety) i produkuje frontend/showcase/data/changelog.json z wpisami „po ludzku":
żargon, numery issue (#NNN), kody zadań (G16, W7) i markdown są oczyszczone.

Uruchom:  python3 scripts/gen_showcase_changelog.py
Re-run przy każdym releasie. Humanizacja jest heurystyczna — kuracja ręczna:
wpisy z `"hidden": true` w pliku data/changelog.curate.json są pomijane,
a `"override"` podmienia tytuł/highlighty danej wersji.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "CHANGELOG.md"
OUT = ROOT / "frontend/showcase/data/changelog.json"
CURATE = ROOT / "frontend/showcase/data/changelog.curate.json"

MONTHS = {1:"styczeń",2:"luty",3:"marzec",4:"kwiecień",5:"maj",6:"czerwiec",
          7:"lipiec",8:"sierpień",9:"wrzesień",10:"październik",11:"listopad",12:"grudzień"}

VER_RE = re.compile(r"^##\s+v?([\d.]+)\s+[—-]\s+(\d{4}-\d{2}-\d{2})\s*[—-]?\s*(.*)$")
BULLET_RE = re.compile(r"^\s*[-*]\s+(.*)$")

def human_date(iso: str) -> str:
    y, m, _ = iso.split("-")
    return f"{MONTHS.get(int(m), m)} {y}"

def clean(text: str) -> str:
    t = text
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)             # **bold**
    t = re.sub(r"`(.+?)`", r"\1", t)                    # `code`
    t = re.sub(r"#\d+", "", t)                          # issue refs (też zakresy #791–#813)
    t = re.sub(r"^\s*[A-Z]\d+[a-z]?\s*[:.)]\s*", "", t) # wiodący kod zadania "G16: " / "W7) "
    t = re.sub(r"\b[A-Z]\d+[a-z]?\b", "", t)            # inline kody zadań (G16, B14, W7)
    t = re.sub(r"\([^A-Za-z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]*\)", "", t)  # nawiasy bez treści: (–+ , )
    t = re.sub(r"[–—\-+,/]{2,}", " ", t)               # zlepki interpunkcji po wycięciu
    t = re.sub(r"\s+([,.)])", r"\1", t)                 # spacja przed interpunkcją
    t = re.sub(r"\(\s+", "(", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" -–—:·,+/")
    return t.strip()

def parse():
    if not SRC.exists():
        print(f"BŁĄD: brak {SRC}", file=sys.stderr); sys.exit(1)
    lines = SRC.read_text(encoding="utf-8").splitlines()
    entries, cur = [], None
    for ln in lines:
        m = VER_RE.match(ln)
        if m:
            if cur: entries.append(cur)
            ver, date, desc = m.group(1), m.group(2), clean(m.group(3))
            cur = {"version": f"v{ver}", "date": date, "when": human_date(date),
                   "title": desc or f"Aktualizacja v{ver}", "highlights": []}
            continue
        if cur is None: continue
        b = BULLET_RE.match(ln)
        if b:
            txt = clean(b.group(1))
            # pomiń puste, nagłówki sekcji w bullecie, zbyt długie zlepki
            if txt and len(txt) > 3 and len(cur["highlights"]) < 4:
                cur["highlights"].append(txt[:160])
    if cur: entries.append(cur)
    return entries

def apply_curation(entries):
    if not CURATE.exists():
        return entries
    try:
        cur = json.loads(CURATE.read_text(encoding="utf-8"))
    except Exception:
        return entries
    hidden = set(cur.get("hidden", []))
    overrides = cur.get("override", {})
    out = []
    for e in entries:
        if e["version"] in hidden:
            continue
        if e["version"] in overrides:
            e.update(overrides[e["version"]])
        out.append(e)
    return out

def main():
    entries = apply_curation(parse())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"generated_from": "CHANGELOG.md", "entries": entries},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {len(entries)} wpisów → {OUT.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
