#!/usr/bin/env python3
"""region_blocks.py — JEDNO źródło prawdy dla układu bloków kontynentu (#1542, M-30).

Kontynent to siatka BLOKÓW (kolumna, wiersz). Każda kraina zajmuje jeden blok
50×50 heksów. Absolutny offset axial krainy liczy się z pozycji jej bloku:

    q_off = 50 * col
    r_off = 50 * row - 25 * col

Skąd „- 25 * col"?  Renderer mapy (flat-top, `frontend/admin/sections/map.js`
`_wbHexToPixel`) daje `screen_y ∝ (r + q/2)`. Kraina o q≠0 dryfuje więc pionowo
o q/2. Składnik `-25*col` kompensuje ten SHEAR: dla całego wiersza bloków
(to samo `row`) przesunięcie ekranowe `screen_y_shift = r_off + q_off/2 = 50*row`
jest STAŁE — niezależne od kolumny. Dzięki temu pas `row=0` (Koronne Niziny ·
Kresy · Czarnobór) leży na jednym poziomie na ekranie, „na równi z Kresami".

Skąd „50 * row" (a nie 75)?  Blok ma na ekranie wysokość 50 (screen_y ∈ [0, ~49]).
Krok wiersza = wysokość bloku, więc sąsiednie rzędy N-S (np. Czarnobór row=0 ↔
Martwe Pustkowia row=1) STYKAJĄ SIĘ krawędź-w-krawędź, bez pustego pasa (#1494
korekta: 75 zostawiał lukę 25 rzędów; Piotr — „krainy POWINNY się stykać").
Patrz `docs/world/continent_layout.md` (nota CB-4) i issue #1489/#1490/#1542.

Ten moduł jest importowany przez:
  * `scripts/generate_region_map.py` — buduje z niego `REGION_OFFSETS`,
  * `backend/tests/test_1542_region_blocks.py` — waliduje wzór i dane krain.

NIE zmieniaj wartości bez aktualizacji `continent_layout.md` (commit = zgoda
Piotra na układ mapy świata).
"""
from __future__ import annotations

# Rozmiar bloku krainy (lokalna siatka offset-coords, identycznie w generatorze).
W = H = 50

# ── UKŁAD BLOKÓW: kraina → (col, row) ────────────────────────────────────────
# col rośnie na wschód (E), row rośnie na południe (S). Kresy = origin (0, 0).
REGION_BLOCKS: dict[str, tuple[int, int]] = {
    "koronne_niziny":   (-1,  0),   # W  od Kresów
    "kresy":            ( 0,  0),   # origin (live)
    "czarnobor":        ( 1,  0),   # E  od Kresów
    "siwe_granie":      ( 0, -1),   # N  od Kresów (live)
    "wybrzeze_lez":     (-1,  1),   # SW
    "martwe_pustkowia": ( 1,  1),   # SE
}


def block_offsets(col: int, row: int) -> tuple[int, int]:
    """Absolutny offset axial (q_off, r_off) dla bloku (col, row).

    q_off = 50*col ; r_off = 50*row - 25*col  (blok wys. 50 → rzędy N-S stykają się).
    """
    return (50 * col, 50 * row - 25 * col)


def region_offsets(region_key: str) -> tuple[int, int]:
    """Offset (q_off, r_off) krainy wg jej bloku w REGION_BLOCKS."""
    return block_offsets(*REGION_BLOCKS[region_key])


def screen_y_shift(q_off: int, r_off: int) -> float:
    """Pionowe przesunięcie krainy na ekranie renderera (flat-top).

    screen_y ∝ (r + q/2) ⇒ przesunięcie krainy = r_off + q_off/2.
    Dla wzoru bloków redukuje się do 50*row (niezależne od kolumny) — to
    właśnie ta niezmienniczość ustawia pas row=0 „na równi z Kresami".
    Krok 50·row = wysokość bloku na ekranie ⇒ sąsiednie rzędy N-S stykają się.
    """
    return r_off + q_off / 2.0


# Wygodna, gotowa mapa kraina → (q_off, r_off) — używana przez generator.
REGION_OFFSETS: dict[str, tuple[int, int]] = {
    key: block_offsets(*block) for key, block in REGION_BLOCKS.items()
}


if __name__ == "__main__":  # pragma: no cover — szybki podgląd układu
    print("kraina             blok(col,row)  q_off  r_off  screen_y_shift")
    for k, b in REGION_BLOCKS.items():
        qo, ro = block_offsets(*b)
        print(f"{k:18} {str(b):>10}   {qo:>5}  {ro:>5}   {screen_y_shift(qo, ro):>6.1f}")
