#!/usr/bin/env python3
"""border_reconcile.py — płynne przejścia terenu na granicach krain (#1545).

Wymaganie Piotra: na styku dwóch krain teren ma przechodzić PŁYNNIE — żadnych
twardych skoków „śnieżne góry → nagle jezioro/morze". Krawędź to strefa
przejściowa, nie ściana.

MODEL
-----
Każdy hex_type należy do RODZINY terenu. Część par rodzin to TWARDE SKOKI
(FORBIDDEN) — nie wolno, by stykały się bezpośrednio przez krawędź axial.
Reconcile wstawia MOSTEK: retypuje hex po stronie „bardziej wrogiej" na typ
rodziny pośredniej, aż żadna para graniczna nie łamie zakazu.

CHRONIONE (nigdy nie retypowane): road/bridge/osady, hexy z location_key (POI),
oraz — opcjonalnie — hexy z label (teasery/kotwice) zostają, zmienia się tylko
teren pod spodem gdy trzeba (label/location_key zachowane).

UŻYCIE (na hoście DEV .61)
--------------------------
    python3 scripts/border_reconcile.py --a czarnobor --b martwe_pustkowia
        → ANALIZA (dry-run): pary graniczne, wykryte twarde skoki. Nic nie pisze.
    python3 scripts/border_reconcile.py --a czarnobor --b martwe_pustkowia --apply
        → backup DB + wstaw mostki (tylko jeśli są twarde skoki). Idempotentne.
    python3 scripts/border_reconcile.py --self-test
        → syntetyczny styk góry↔morze: dowód, że mostkowanie działa.

Pilot: czarnobor ↔ martwe_pustkowia. Gdy zadziała — te same rodziny/zakazy
stosują się do każdej innej pary krain (uruchom z innym --a/--b).
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── RODZINY TERENU ───────────────────────────────────────────────────────────
# Każdy hex_type → rodzina. Nowe typy krain (czarny_las, lodowiec, sol…) wpięte.
FAMILY = {
    # woda
    "sea": "WATER", "lake": "WATER", "river": "WATER", "water": "WATER",
    "brod": "WATER", "ocean": "WATER",
    "coast": "COAST",
    # otwarte / trawiaste
    "plains": "OPEN", "heath": "OPEN", "step": "OPEN", "tundra": "OPEN",
    "grassland": "OPEN",
    # mokradła (amfibia — OK i z wodą, i z lasem)
    "swamp": "WETLAND", "trzesawisko": "WETLAND", "bagno": "WETLAND",
    # las
    "forest": "FOREST", "czarny_las": "FOREST", "las_iglasty": "FOREST",
    "jungle": "FOREST",
    # wzgórza / przełęcze (mostek góry↔nizina)
    "hills": "HILL", "grania": "HILL", "przelecz": "HILL", "foothills": "HILL",
    # góry wysokie
    "mountain": "MOUNTAIN", "snow": "MOUNTAIN", "lodowiec": "MOUNTAIN",
    "glacier": "MOUNTAIN", "peak": "MOUNTAIN",
    # jałowizna / martwe (rodzina „waste")
    "sol": "WASTE", "martwa_ziemia": "WASTE", "ruins": "WASTE", "siarka": "WASTE",
}
# Typy strukturalne — nigdy nie retypowane (chronione z automatu).
STRUCT = {"road", "bridge", "city", "town", "village"}

def fam(hex_type: str) -> str:
    if hex_type in STRUCT:
        return "STRUCT"
    return FAMILY.get(hex_type, "OPEN")  # nieznany → OPEN (bezpieczny neutralny)

# ── ZAKAZY: pary rodzin, które NIE mogą się stykać (twardy skok) ──────────────
# symetryczne
FORBIDDEN = {
    frozenset({"MOUNTAIN", "WATER"}),   # śnieżne góry ↔ jezioro/morze  (przykład Piotra)
    frozenset({"MOUNTAIN", "WASTE"}),   # góry ↔ martwa jałowizna
    frozenset({"MOUNTAIN", "OPEN"}),    # urwisko: szczyt ↔ równina bez pogórza
    frozenset({"WASTE", "WATER"}),      # sól/martwa ziemia ↔ woda
    frozenset({"FOREST", "WASTE"}),     # gęsty las ↔ nagła martwa ziemia (heath mostkuje)
}
def is_harsh(a: str, b: str) -> bool:
    return frozenset({a, b}) in FORBIDDEN

# ── MOSTKI: dla wrogiej rodziny → typ o krok bliżej neutralnej ────────────────
# Retypujemy hex „twardszej" strony na przedstawiciela rodziny mostkującej.
BRIDGE_STEP = {          # rodzina → (typ mostka, nowa rodzina po retypie)
    "MOUNTAIN": ("hills", "HILL"),      # góra → pogórze
    "HILL":     ("heath", "OPEN"),      # pogórze → wrzos
    "WASTE":    ("heath", "OPEN"),      # martwa ziemia → wrzos
    "FOREST":   ("heath", "OPEN"),      # las → wrzos
}
# „Twardość" — którą stronę retypować (wyższa = bardziej wroga, ustępuje pierwsza).
HOSTILITY = {"MOUNTAIN": 5, "WASTE": 4, "HILL": 3, "FOREST": 3,
             "WETLAND": 2, "FOREST_x": 2, "OPEN": 1, "COAST": 1, "WATER": 0,
             "STRUCT": 99}

NB = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]


def dexec(sql: str, container="ai-gm-dev-backend-1", db="/data/ai_gm.db", piped=False):
    cmd = ["docker", "exec"] + (["-i"] if piped else []) + [container, "sqlite3"]
    if not piped:
        cmd += [db, sql]
    else:
        cmd += [db]
    return subprocess.run(cmd, input=(sql if piped else None), text=True, capture_output=True)


def load_region(region: str, container: str, db: str) -> dict:
    out = subprocess.run(
        ["docker", "exec", container, "sqlite3", "-json", db,
         f"SELECT q,r,hex_type,location_key,label FROM world_hexes "
         f"WHERE map_level=0 AND region='{region}';"],
        text=True, capture_output=True)
    if out.returncode:
        print("BŁĄD DB:", out.stderr, file=sys.stderr); sys.exit(1)
    rows = json.loads(out.stdout or "[]")
    return {(h["q"], h["r"]): h for h in rows}


def protected(h: dict) -> bool:
    return h["hex_type"] in STRUCT or bool(h.get("location_key"))


def border_pairs(A: dict, B: dict):
    """Zwróć pary (hexA, hexB) będące sąsiadami axial na styku dwóch krain."""
    for (q, r), ha in A.items():
        for dq, dr in NB:
            hb = B.get((q + dq, r + dr))
            if hb is not None:
                yield ha, hb


def analyze(A: dict, B: dict):
    from collections import Counter
    pairs = Counter(); harsh = []
    for ha, hb in border_pairs(A, B):
        fa, fb = fam(ha["hex_type"]), fam(hb["hex_type"])
        pairs[(ha["hex_type"], hb["hex_type"])] += 1
        if is_harsh(fa, fb):
            harsh.append((ha, hb, fa, fb))
    return pairs, harsh


def reconcile(A: dict, B: dict, region_a: str, region_b: str, max_rings=3):
    """Zwróć listę zmian [(region,q,r,old,new)] domykających twarde skoki.

    Retypuje hex twardszej (i niechronionej) strony na typ mostkujący. Powtarza
    aż brak twardych skoków lub limit rings. Deterministyczne (bez losowości)."""
    changes = []
    owner = {id(A): region_a, id(B): region_b}
    for _ in range(max_rings):
        _, harsh = analyze(A, B)
        if not harsh:
            break
        # posortuj deterministycznie
        harsh.sort(key=lambda t: (t[0]["q"], t[0]["r"], t[1]["q"], t[1]["r"]))
        touched = False
        for ha, hb, fa, fb in harsh:
            # wybierz stronę do ustąpienia: wyższa hostility, niechroniona, mostkowalna
            cand = sorted([(ha, fa, A), (hb, fb, B)],
                          key=lambda x: -HOSTILITY.get(x[1], 1))
            for hex_, f, grid in cand:
                if protected(hex_) or f not in BRIDGE_STEP:
                    continue
                new_type, _ = BRIDGE_STEP[f]
                if hex_["hex_type"] == new_type:
                    continue
                old = hex_["hex_type"]
                changes.append((owner[id(grid)], hex_["q"], hex_["r"], old, new_type))
                hex_["hex_type"] = new_type
                touched = True
                break
        if not touched:
            break
    return changes


def apply_changes(changes, container, db):
    if not changes:
        return
    sql = "BEGIN;\n" + "\n".join(
        f"UPDATE world_hexes SET hex_type='{nt}' WHERE map_level=0 AND region='{reg}' "
        f"AND q={q} AND r={r};" for reg, q, r, _, nt in changes) + "\nCOMMIT;"
    res = dexec(sql, container, db, piped=True)
    if res.returncode:
        print("BŁĄD zapisu:", res.stderr, file=sys.stderr); sys.exit(1)


def self_test():
    """Syntetyczny styk: pas gór (A) styka się z pasem jeziora (B). Reconcile
    ma wstawić pogórze/wrzos tak, że znika twardy skok MOUNTAIN↔WATER."""
    A = {(0, 0): {"q": 0, "r": 0, "hex_type": "snow", "location_key": None, "label": None},
         (1, 0): {"q": 1, "r": 0, "hex_type": "mountain", "location_key": None, "label": None}}
    B = {(0, 1): {"q": 0, "r": 1, "hex_type": "lake", "location_key": None, "label": None},
         (1, 1): {"q": 1, "r": 1, "hex_type": "river", "location_key": None, "label": None}}
    _, harsh0 = analyze(A, B)
    ch = reconcile(A, B, "gory", "woda")
    _, harsh1 = analyze(A, B)
    print(f"SELF-TEST góry↔woda: twarde skoki przed={len(harsh0)} → po={len(harsh1)}; "
          f"zmiany={[(c[3]+'→'+c[4]) for c in ch]}")
    assert harsh0 and not harsh1, "reconcile NIE domknął twardego skoku!"
    print("SELF-TEST OK ✅")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a"); ap.add_argument("--b")
    ap.add_argument("--apply", action="store_true", help="wstaw mostki do DB (backup najpierw)")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--container", default="ai-gm-dev-backend-1")
    ap.add_argument("--db", default="/data/ai_gm.db")
    a = ap.parse_args()

    if a.self_test:
        self_test(); return
    if not (a.a and a.b):
        ap.error("podaj --a <kraina> --b <kraina> albo --self-test")

    A = load_region(a.a, a.container, a.db)
    B = load_region(a.b, a.container, a.db)
    pairs, harsh = analyze(A, B)
    total = sum(pairs.values())
    print(f"═══ Granica {a.a} ↔ {a.b} ═══")
    print(f"par granicznych (axial): {total}")
    print("styki hex_type (rodzina):")
    for (ta, tb), c in pairs.most_common():
        flag = "  ⛔ TWARDY SKOK" if is_harsh(fam(ta), fam(tb)) else ""
        print(f"  {ta:14}({fam(ta):8}) ↔ {tb:14}({fam(tb):8}) ×{c}{flag}")
    print(f"\nTWARDE SKOKI do naprawy: {len(harsh)}")
    if not harsh:
        print("✅ Granica już płynna — żadnego twardego skoku, brak zmian.")
        return

    changes = reconcile(A, B, a.a, a.b)
    print(f"MOSTKI (retyp): {len(changes)}")
    for reg, q, r, old, nt in changes[:40]:
        print(f"  {reg} ({q},{r}) {old} → {nt}")
    if a.apply:
        print("\n📦 backup DB…")
        subprocess.run(["./scripts/backup.sh"], cwd=str(ROOT))
        apply_changes(changes, a.container, a.db)
        _, harsh_after = analyze(load_region(a.a, a.container, a.db),
                                 load_region(a.b, a.container, a.db))
        print(f"✅ zastosowano. Twarde skoki po: {len(harsh_after)}. "
              f"Snapshot obie krainy i zacommituj.")
    else:
        print("\n(dry-run — nic nie zapisano. Dodaj --apply by wstawić mostki.)")


if __name__ == "__main__":
    main()
