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

## Bounding-boxy (absolutne axial)

| Kraina | key | status | q_min | q_max | r_min | r_max | q_offset | r_offset |
|--------|-----|--------|-------|-------|-------|-------|----------|----------|
| Koronne Niziny | `koronne_niziny` | coming | -55 | -6 | -24 | 49 | -55 | 0 |
| **Kresy** | `kresy` | **live** | 0 | 49 | -24 | 49 | 0 | 0 |
| Czarnobór | `czarnobor` | coming | 55 | 104 | -24 | 49 | 55 | 0 |
| Siwe Granie | `siwe_granie` | coming (pilot RM7) | 0 | 49 | -99 | -26 | 0 | -75 |
| Wybrzeże Łez | `wybrzeze_lez` | coming | -55 | -6 | 51 | 124 | -55 | 75 |
| Martwe Pustkowia | `martwe_pustkowia` | coming | 55 | 104 | 51 | 124 | 55 | 75 |

## Układ geograficzny (schemat)

```
         q: -55..-6          q: 0..49         q: 55..104
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
  region_siwe_granie.json      ← coming, ~2500 heksów
  region_czarnobor.json        ← coming, ~2500 heksów
  region_koronne_niziny.json   ← coming, ~2500 heksów
  region_wybrzeze_lez.json     ← coming, ~2500 heksów
  region_martwe_pustkowia.json ← coming, ~2500 heksów
```

## Jak dodać nową krainę

Patrz runbook `docs/runbooks/add_new_region.md` (tworzony w RM7).
Krótko: generuj → akceptacja PNG → commit pliku → seed `--region <key>` → flip status.
