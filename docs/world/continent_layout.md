# Kontynent — bounding-boxy krain (axial coords)

> Źródło prawdy dla układu kontynentu i offsetów per-kraina.
> Wygenerowane przez `scripts/generate_region_map.py` (FAZA RM, RM5).

## Model

Jeden ciągły kontynent na absolutnych koordynatach axial `(q, r)`.
Każda kraina to 50×50 siatka hexów eksportowana z **lokalnych offset-coords** do **absolutnych axial**:

```
q_absolutny = local_col + q_offset
r_absolutny = (local_row - (local_col - local_col%2)//2) + r_offset
```

Krainy **nie nakładają się** (test: `backend/tests/test_continent_no_overlap.py`).

## Wzór bloków (JEDNO źródło prawdy) — #1542

Kontynent to siatka **bloków** `(col, row)`; każda kraina zajmuje jeden blok.
Offsety krain NIE są hardkodowane w wielu miejscach — liczy je jeden moduł
`scripts/region_blocks.py` (`REGION_BLOCKS` + `block_offsets()`):

```
q_off = 50 · col
r_off = 75 · row − 25 · col
```

Składnik `−25·col` kompensuje **shear** renderera flat-top (`screen_y ∝ r + q/2`):
dla całego wiersza bloków `screen_y_shift = r_off + q_off/2 = 75·row` jest **stałe**,
niezależne od kolumny — dlatego pas `row=0` (Koronne Niziny · Kresy · Czarnobór)
leży **na równi z Kresami**. Bloki krain: KN `(-1,0)` · Kresy `(0,0)` · Czarnobór `(1,0)`
· Siwe Granie `(0,-1)` · Wybrzeże Łez `(-1,1)` · Martwe Pustkowia `(1,1)`.

Korzystają z tego: `scripts/generate_region_map.py` (buduje `REGION_OFFSETS`)
oraz strażnik `backend/tests/test_1542_region_blocks.py` (pilnuje wzoru, kolizji
i wyrównania pasa row=0). Zmiana układu = edycja `region_blocks.py` + tej tabeli.

## Bounding-boxy (absolutne axial)

| Kraina | key | status | q_min | q_max | r_min | r_max | q_offset | r_offset |
|--------|-----|--------|-------|-------|-------|-------|----------|----------|
| Koronne Niziny | `koronne_niziny` | coming | -50 | -1 | 1 | 74 | -50 | 25 |
| **Kresy** | `kresy` | **live** | 0 | 49 | -24 | 49 | 0 | 0 |
| Czarnobór | `czarnobor` | coming | 50 | 99 | -49 | 24 | 50 | -25 |
| **Siwe Granie** | `siwe_granie` | **live** (RM7 pilot) | 0 | 49 | -99 | -26 | 0 | -75 |
| Wybrzeże Łez | `wybrzeze_lez` | coming | -50 | -1 | 76 | 149 | -50 | 100 |
| Martwe Pustkowia | `martwe_pustkowia` | coming | 50 | 99 | 26 | 99 | 50 | 50 |

> **Uwaga (CB-4, 2026-07-24):** dwie korekty układu, by krainy **dolegały** i były **na równi** z Kresami:
> 1. **q = ±50** (nie ±55): sąsiednie krainy stykają się bez luki (q49 Kresów ↔ q50 Czarnoboru = sąsiedzi axial). ±55 dawał 5-kolumnową czarną pustkę.
> 2. **r skompensowany o shear**: renderer flat-top daje `screen-y = r + q/2`, więc kraina o q≠0 dryfuje pionowo o q/2 (Czarnobór q+50 spadał o pół wysokości). Kompensacja `r_offset = base − q_offset/2` (E: −25, W: +25) ustawia je **na równi** z Kresami. Siwe Granie (q=0) nie wymaga korekty.
>
> Czarnobór (seedowany) już przesunięty (q50-99, r_off −25). Krainy `coming` dostaną te offsety przy generacji. **Trakt Kresy↔Czarnobór**: łączy się mostkiem drogowym na kolumnie granicznej q50 (r−6..13), Kresy(49,13) → sieć Czarnoboru → Ostęp Graniczny.

## Układ geograficzny (schemat)

```
         q: -50..-1          q: 0..49         q: 50..99
         ─────────────────────────────────────────────────
r:-99..-26 │                 SIWE GRANIE                  │
           │    (góry, śnieg — ojczyzna krasnoludów)     │
           ─────────────────────────────────────────────────
r:-24..49  │ KORONNE  │       KRESY         │  CZARNOBÓR  │
           │ NIZINY   │  (pogranicze, wsie) │ (las, bagno)│
           │(stolica, │                     │             │
           │ trakty)  │                     │             │
           ─────────────────────────────────────────────────
r:51..124  │WYBRZEŻE  │      [morze]        │  MARTWE     │
           │ ŁEZ      │                     │  PUSTKOWIA  │
           │(wybrzeże,│                     │  (ruiny,    │
           │ piraci)  │                     │   pustkowie)│
           ─────────────────────────────────────────────────
```

## Sąsiedztwa (granice stykające się lub bliskie)

| Kraina A | Krawędź | Kraina B | Teaser label |
|----------|---------|----------|--------------|
| Kresy | N | Siwe Granie | "ku Siwym Graniom" |
| Kresy | E | Czarnobór | "ku Czarnoborowi" |
| Kresy | W | Koronne Niziny | "ku Koronnym Nizinom" |
| Siwe Granie | S | Kresy | "ku Kresom" |
| Czarnobór | W | Kresy | "ku Kresom" |
| Czarnobór | S | Martwe Pustkowia | "ku Martwym Pustkowiu" |
| Koronne Niziny | E | Kresy | "ku Kresom" |
| Koronne Niziny | S | Wybrzeże Łez | "ku Wybrzeżu Łez" |
| Wybrzeże Łez | N | Koronne Niziny | "ku Koronnym Nizinom" |
| Martwe Pustkowia | N | Czarnobór | "ku Czarnoborowi" |
| Martwe Pustkowia | W | Kresy | "ku Kresom" |

## Pliki per-kraina

```
data/regions/
  region_kresy.json            ← live, ~2500 heksów
  region_siwe_granie.json      ← live,   ~2500 heksów  (RM7 — odblokowano)
  region_czarnobor.json        ← coming, ~2500 heksów
  region_koronne_niziny.json   ← coming, ~2500 heksów
  region_wybrzeze_lez.json     ← coming, ~2500 heksów
  region_martwe_pustkowia.json ← coming, ~2500 heksów
```

## Jak dodać nową krainę

Patrz runbook `docs/runbooks/add_new_region.md` (tworzony w RM7).
Krótko: generuj → akceptacja PNG → commit pliku → seed `--region <key>` → flip status.
