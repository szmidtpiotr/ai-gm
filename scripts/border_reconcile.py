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
import argparse, json, subprocess, sys, math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── RODZINY TERENU ───────────────────────────────────────────────────────────
# Każdy hex_type → rodzina. Nowe typy krain (czarny_las, lodowiec, sol…) wpięte.
FAMILY = {
    # słona woda (morze) — osobna rodzina: sól MOŻE schodzić prosto w morze (#1549)
    "sea": "SEA", "morze": "SEA", "ocean": "SEA",
    # słodka woda (jezioro/rzeka) — sól/martwa ziemia NIE stykają się z nią wprost
    "lake": "WATER", "river": "WATER", "water": "WATER", "brod": "WATER",
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
    frozenset({"MOUNTAIN", "WATER"}),   # śnieżne góry ↔ jezioro/rzeka  (przykład Piotra)
    frozenset({"MOUNTAIN", "SEA"}),     # góry NIGDY obok morza (#1549)
    frozenset({"MOUNTAIN", "WASTE"}),   # góry ↔ martwa jałowizna
    frozenset({"MOUNTAIN", "OPEN"}),    # urwisko: szczyt ↔ równina bez pogórza
    frozenset({"WASTE", "WATER"}),      # sól/martwa ziemia ↔ SŁODKA woda (sól↔MORZE dozwolone, #1549)
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
             "WETLAND": 2, "FOREST_x": 2, "OPEN": 1, "COAST": 1,
             "WATER": 0, "SEA": 0, "STRUCT": 99}

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


# ── FEATHERING: organiczne, faliste wcięcia na granicy (#1545, prośba Piotra) ─
# Region-ownership (siatka) zostaje prosty; falujemy TYLKO typ terenu w pasie
# przygranicznym, tak by palce lasu/bagna schodziły w heath sąsiada i odwrotnie —
# granica przestaje być prostą poziomą linią.
REPAINT_FAM = {"FOREST", "WETLAND", "OPEN"}  # co wolno przemalować (nie woda/waste/struct)

def _hash01(a: int, b: int, seed: int) -> float:
    """Deterministyczny hash (a,b,seed) → [0,1). Bez random (odtwarzalne, resume-safe)."""
    x = (a * 73856093) ^ (b * 19349663) ^ (seed * 83492791)
    x &= 0xFFFFFFFF
    x = ((x ^ (x >> 13)) * 1274126177) & 0xFFFFFFFF
    x ^= (x >> 16)
    return x / 0xFFFFFFFF

def _vnoise1(t: float, seed: int) -> float:
    """Gładki szum 1D (value noise, smoothstep) w [-1,1]."""
    i = math.floor(t); f = t - i
    a = _hash01(i, 0, seed); b = _hash01(i + 1, 0, seed)
    u = f * f * (3 - 2 * f)
    return 2.0 * (a + (b - a) * u) - 1.0

def _edge_lines(G: dict, other: dict, south: bool):
    """Dla każdej kolumny q: r krawędzi stykającej się z drugą krainą."""
    from collections import defaultdict
    cols = defaultdict(list)
    for (q, r) in G:
        cols[q].append(r)
    edge = {}
    for q, rs in cols.items():
        edge[q] = max(rs) if south else min(rs)
    return edge

def feather(A: dict, B: dict, region_a: str, region_b: str, *,
            seed=2026, band=5, amp1=3.0, period1=7.0, amp2=1.2, period2=2.7,
            island_p=0.06):
    """Zwróć zmiany [(region,q,r,old,new)] falujące styk A(płn)↔B(płd).

    A = kraina północna (mniejsze r), B = południowa. Dla każdej kolumny liczymy
    linię styku i falę wave(q); hex po stronie A z r<wave dostaje teren A (las/
    bagno), z r>=wave → teren B (heath); symetrycznie po stronie B. Dodatkowo
    rzadkie „wyspy" (island_p) tworzą oderwane płaty = fraktalna krawędź."""
    a_edge = _edge_lines(A, B, south=True)    # dolna krawędź A
    b_edge = _edge_lines(B, A, south=False)   # górna krawędź B
    cols = set(a_edge) & set(b_edge)
    seam = {q: (a_edge[q] + b_edge[q]) / 2.0 for q in cols}

    def a_terrain(q, r):
        return "swamp" if _hash01(q, r, seed + 3) < 0.5 else "forest"

    def want_a_side(q, r):
        s = seam[q]
        wave = s + amp1 * _vnoise1(q / period1, seed) + amp2 * _vnoise1(q / period2, seed + 7)
        wa = r < wave
        if _hash01(q, r, seed + 99) < island_p:   # wyspa: odwróć
            wa = not wa
        return wa

    changes = []
    for grid, region, is_A in ((A, region_a, True), (B, region_b, False)):
        edge = a_edge if is_A else b_edge
        for (q, r), h in grid.items():
            if q not in cols:
                continue
            depth = (edge[q] - r) if is_A else (r - edge[q])   # 0 = na krawędzi
            if depth < 0 or depth >= band:
                continue
            cur = h["hex_type"]; curfam = fam(cur)
            if protected(h) or curfam not in REPAINT_FAM:
                continue
            # Falujemy TYLKO na styku rodzin (heath ↔ las/bagno). Hex już będący po
            # „swojej" stronie zostaje — nie mieszamy lasu z bagnem bez potrzeby,
            # żeby nie przepisywać zatwierdzonego terenu Czarnoboru w kółko.
            if want_a_side(q, r):
                if curfam in ("FOREST", "WETLAND"):
                    continue                      # już las/bagno — zostaw
                new = a_terrain(q, r)             # heath → palec lasu/bagna
            else:
                if curfam == "OPEN":
                    continue                      # już heath — zostaw
                new = "heath"                     # las/bagno → palec wrzosu
            if new != cur:
                changes.append((region, q, r, cur, new))
                h["hex_type"] = new
    return changes


# ── FEATHERING BRZEGOWY: pionowy styk ląd↔morze (#1545 + #1549) ───────────────
# Odpowiednik feather() dla granicy PIONOWEJ (morze mniejsze q ↔ ląd większe q).
# Faluje linię brzegową: zatoki morza wcinają się w ląd, mierzeje/cyple lądu
# wchodzą w morze, cienki pas `coast` = plaża. Region-ownership zostaje prosty —
# przemalowujemy TYLKO typ terenu w pasie brzegowym. sól↔morze wprost (dozwolone).
COAST_REPAINT = {"SEA", "COAST", "OPEN", "WASTE", "FOREST", "WETLAND"}

def _edge_cols(G: dict, east: bool) -> dict:
    """Dla każdego wiersza r: q krawędzi (east=True → min q lądu, else max q morza)."""
    from collections import defaultdict
    rows = defaultdict(list)
    for (q, r) in G:
        rows[r].append(q)
    return {r: (min(qs) if east else max(qs)) for r, qs in rows.items()}

def feather_coast(A: dict, B: dict, region_a: str, region_b: str, *,
                  seed=2026, band=4, amp1=2.5, period1=6.0,
                  amp2=1.0, period2=2.9, shore=1.2):
    """Zwróć zmiany [(region,q,r,old,new)] falujące pionowy styk A(zachód/morze)
    ↔ B(wschód/ląd). Dla każdego wiersza r liczymy linię brzegu i falę wave(r):
    hex po stronie morza z q<wave zostaje morzem, wypchnięty na stronę lądu →
    coast (mierzeja); hex lądu z q<wave → morze (zatoka), tuż przy linii → coast
    (plaża). Chronione (POI/trakt/osady) nietknięte."""
    a_edge = _edge_cols(A, east=False)   # wschodnia krawędź morza: max q
    b_edge = _edge_cols(B, east=True)    # zachodnia krawędź lądu:  min q
    rows = set(a_edge) & set(b_edge)
    seam = {r: (a_edge[r] + b_edge[r]) / 2.0 for r in rows}

    def wave(r):
        return (seam[r] + amp1 * _vnoise1(r / period1, seed)
                        + amp2 * _vnoise1(r / period2, seed + 7))

    changes = []
    for grid, region, is_A in ((A, region_a, True), (B, region_b, False)):
        edge = a_edge if is_A else b_edge
        for (q, r), h in grid.items():
            if r not in rows:
                continue
            depth = (edge[r] - q) if is_A else (q - edge[r])   # 0 = na krawędzi
            if depth < 0 or depth >= band:
                continue
            cur = h["hex_type"]; curfam = fam(cur)
            if protected(h) or curfam not in COAST_REPAINT or cur == "ruins":
                continue                       # ruiny = landmark terenu, nie zatapiać
            w = wave(r); sea_side = q < w; dist = abs(q - w)
            if is_A:                       # hex morza
                if not sea_side:           # wypchnięty na ląd → mierzeja/plaża
                    new = "coast"
                elif dist < shore:         # tuż przy linii → plaża
                    new = "coast"
                else:
                    new = cur              # zostaje morze
            else:                          # hex lądu
                if sea_side:               # zalany → zatoka morska
                    new = "morze"
                elif dist < shore:         # tuż przy linii → plaża
                    new = "coast"
                else:
                    new = cur
            if new != cur:
                changes.append((region, q, r, cur, new))
                h["hex_type"] = new
    return changes


def render_border_v(A: dict, B: dict, region_a: str, region_b: str,
                    out_path: str, context=12, scale=14):
    """PNG pionowego pasa brzegowego (styk ląd↔morze)."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from reseed_region_terrain import save_png
    a_edge = _edge_cols(A, east=False)
    b_edge = _edge_cols(B, east=True)
    rows = set(a_edge) & set(b_edge)
    win = {}
    for (q, r), h in A.items():
        if r in rows and 0 <= a_edge[r] - q <= context:
            win[(q, r)] = h
    for (q, r), h in B.items():
        if r in rows and 0 <= q - b_edge[r] <= context:
            win[(q, r)] = h
    save_png(win, f"{region_a} / {region_b}", "styk ląd↔morze (pas brzegowy)",
             Path(out_path), S=scale)
    return len(win)


def render_border(A: dict, B: dict, region_a: str, region_b: str,
                  out_path: str, context=12, scale=14):
    """Zapisz PNG pasa przygranicznego (obie krainy) kolorami hex_type."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from reseed_region_terrain import save_png  # renderer gry (flat-top axial)
    a_edge = _edge_lines(A, B, south=True)
    b_edge = _edge_lines(B, A, south=False)
    cols = set(a_edge) & set(b_edge)
    win = {}
    for (q, r), h in A.items():
        if q in cols and 0 <= a_edge[q] - r <= context:
            win[(q, r)] = h
    for (q, r), h in B.items():
        if q in cols and 0 <= r - b_edge[q] <= context:
            win[(q, r)] = h
    save_png(win, f"{region_a} / {region_b}", "styk terenu (pas graniczny)",
             Path(out_path), S=scale)
    return len(win)


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
    ap.add_argument("--apply", action="store_true", help="zapisz do DB (backup najpierw)")
    ap.add_argument("--feather", action="store_true",
                    help="organiczne faliste wcięcia terenu na granicy poziomej (interdigitacja)")
    ap.add_argument("--coast", action="store_true",
                    help="feathering brzegowy: pionowy styk ląd↔morze (zatoki + mierzeje + plaża)")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--band", type=int, default=5, help="głębokość pasa feather (hexy/stronę)")
    ap.add_argument("--amp", type=float, default=3.0, help="amplituda fali (rzędy)")
    ap.add_argument("--png", default=None, help="prefix ścieżki: zapisz PNG przed/po feather")
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

    if a.coast:
        # A musi być krainą zachodnią (mniejsze q = strona morza). Zamień jeśli trzeba.
        qa = sum(h["q"] for h in A.values()) / max(len(A), 1)
        qb = sum(h["q"] for h in B.values()) / max(len(B), 1)
        (An, Bn, an, bn) = (A, B, a.a, a.b) if qa <= qb else (B, A, a.b, a.a)
        if a.png:
            n = render_border_v(An, Bn, an, bn, f"{a.png}_before.png")
            print(f"🖼  PNG przed: {a.png}_before.png ({n} hexów pasa)")
        fch = feather_coast(An, Bn, an, bn, seed=a.seed, band=a.band, amp1=a.amp)
        rch = reconcile(An, Bn, an, bn)          # domknij ewentualne twarde skoki
        changes = fch + rch
        from collections import Counter
        print(f"═══ COAST-FEATHER {an}(zach/morze) ↔ {bn}(wsch/ląd)  seed={a.seed} band={a.band} amp={a.amp} ═══")
        print(f"zmiany terenu: {len(fch)} (brzeg) + {len(rch)} (reconcile domykający) = {len(changes)}")
        per = Counter((c[0], c[3] + '→' + c[4]) for c in changes)
        for (reg, tr), n in per.most_common(20):
            print(f"  {reg:18} {tr:22} ×{n}")
        _, harsh_after = analyze(An, Bn)
        print(f"twarde skoki po coast-feather+reconcile: {len(harsh_after)}")
        if a.png:
            n = render_border_v(An, Bn, an, bn, f"{a.png}_after.png")
            print(f"🖼  PNG po: {a.png}_after.png ({n} hexów pasa)")
        if a.apply:
            print("\n📦 backup DB…"); subprocess.run(["./scripts/backup.sh"], cwd=str(ROOT))
            apply_changes(changes, a.container, a.db)
            print(f"✅ zastosowano {len(changes)} zmian. Snapshot obu krain + commit.")
        else:
            print("\n(dry-run — nic nie zapisano. Dodaj --apply.)")
        return

    if a.feather:
        # A musi być krainą północną (mniejsze r). Zamień jeśli trzeba.
        ra = sum(h["r"] for h in A.values()) / max(len(A), 1)
        rb = sum(h["r"] for h in B.values()) / max(len(B), 1)
        (An, Bn, an, bn) = (A, B, a.a, a.b) if ra <= rb else (B, A, a.b, a.a)
        if a.png:
            n = render_border(An, Bn, an, bn, f"{a.png}_before.png")
            print(f"🖼  PNG przed: {a.png}_before.png ({n} hexów pasa)")
        fch = feather(An, Bn, an, bn, seed=a.seed, band=a.band, amp1=a.amp)
        # feather mógł wstawić las obok waste/wody sąsiada — domknij reconcile.
        rch = reconcile(An, Bn, an, bn)
        changes = fch + rch
        from collections import Counter
        print(f"═══ FEATHER {an}(płn) ↔ {bn}(płd)  seed={a.seed} band={a.band} amp={a.amp} ═══")
        print(f"zmiany terenu: {len(fch)} (feather) + {len(rch)} (reconcile domykający) = {len(changes)}")
        per = Counter((c[0], c[3] + '→' + c[4]) for c in changes)
        for (reg, tr), n in per.most_common(20):
            print(f"  {reg:16} {tr:22} ×{n}")
        _, harsh_after = analyze(An, Bn)
        print(f"twarde skoki po feather+reconcile: {len(harsh_after)}")
        if a.png:
            n = render_border(An, Bn, an, bn, f"{a.png}_after.png")
            print(f"🖼  PNG po: {a.png}_after.png ({n} hexów pasa)")
        if a.apply:
            print("\n📦 backup DB…"); subprocess.run(["./scripts/backup.sh"], cwd=str(ROOT))
            apply_changes(changes, a.container, a.db)
            print(f"✅ zastosowano {len(changes)} zmian. Snapshot obu krain + commit.")
        else:
            print("\n(dry-run — nic nie zapisano. Dodaj --apply.)")
        return

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
