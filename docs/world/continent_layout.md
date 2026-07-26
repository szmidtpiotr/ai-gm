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
r_off = 50 · row − 25 · col
```

Składnik `−25·col` kompensuje **shear** renderera flat-top (`screen_y ∝ r + q/2`):
dla całego wiersza bloków `screen_y_shift = r_off + q_off/2 = 50·row` jest **stałe**,
niezależne od kolumny — dlatego pas `row=0` (Koronne Niziny · Kresy · Czarnobór)
leży **na równi z Kresami**. Bloki krain: KN `(-1,0)` · Kresy `(0,0)` · Czarnobór `(1,0)`
· Siwe Granie `(0,-1)` · Wybrzeże Łez `(-1,1)` · Martwe Pustkowia `(1,1)`.

**Krok wiersza = 50 (nie 75).** Blok ma na ekranie wysokość 50 (`screen_y ∈ [0, ~49]`),
więc krok `50·row` sprawia, że sąsiednie rzędy N-S **stykają się krawędź-w-krawędź**
(Czarnobór row=0 ↔ Martwe Pustkowia row=1 = ~50 sąsiadów axial, jak Kresy↔Czarnobór).
Poprzednie `75·row` zostawiało pusty pas 25 rzędów między rzędami — korekta MP-3+ (#1494,
Piotr: „krainy POWINNY się stykać"). E-W stykały się zawsze (wspólna kolumna q49/q50).

Korzystają z tego: `scripts/generate_region_map.py` (buduje `REGION_OFFSETS`)
oraz strażnik `backend/tests/test_1542_region_blocks.py` (pilnuje wzoru, kolizji
i wyrównania pasa row=0). Zmiana układu = edycja `region_blocks.py` + tej tabeli.

## Bounding-boxy (absolutne axial)

| Kraina | key | status | q_min | q_max | r_min | r_max | q_offset | r_offset |
|--------|-----|--------|-------|-------|-------|-------|----------|----------|
| Koronne Niziny | `koronne_niziny` | coming | -50 | -1 | 1 | 74 | -50 | 25 |
| **Kresy** | `kresy` | **live** | 0 | 49 | -24 | 49 | 0 | 0 |
| Czarnobór | `czarnobor` | coming | 50 | 99 | -49 | 24 | 50 | -25 |
| **Siwe Granie** | `siwe_granie` | **live** (RM7 pilot) | 0 | 49 | -75 | -2 | 0 | -50 † |
| Wybrzeże Łez | `wybrzeze_lez` | coming | -50 | -1 | 51 | 124 | -50 | 75 |
| Martwe Pustkowia | `martwe_pustkowia` | **seeded** | 50 | 99 | 1 | 74 | 50 | 25 |

> † **Siwe Granie** jest live (seedowane sprzed wzoru #1542) — jej faktyczne heksy
> siedzą na legacy-offsecie (bounds r −75..−2), nie na `r_off=−50` z wzoru. Stykają
> się z Kresami, więc nie ruszamy danych; wzór dotyczy krain regenerowanych.
> **Martwe Pustkowia** — jedyna kraina `coming` już wsiana do żywej DB (MP-3, #1494),
> na kanonicznym offsecie `(50, 25)`; styka się z Czarnoborem (50 sąsiadów).

> **Uwaga (CB-4, 2026-07-24):** dwie korekty układu, by krainy **dolegały** i były **na równi** z Kresami:
> 1. **q = ±50** (nie ±55): sąsiednie krainy stykają się bez luki (q49 Kresów ↔ q50 Czarnoboru = sąsiedzi axial). ±55 dawał 5-kolumnową czarną pustkę.
> 2. **r skompensowany o shear**: renderer flat-top daje `screen-y = r + q/2`, więc kraina o q≠0 dryfuje pionowo o q/2 (Czarnobór q+50 spadał o pół wysokości). Kompensacja `r_offset = base − q_offset/2` (E: −25, W: +25) ustawia je **na równi** z Kresami. Siwe Granie (q=0) nie wymaga korekty.
>
> Czarnobór (seedowany) już przesunięty (q50-99, r_off −25). Krainy `coming` dostaną te offsety przy generacji. **Trakt Kresy↔Czarnobór**: łączy się mostkiem drogowym na kolumnie granicznej q50 (r−6..13), Kresy(49,13) → sieć Czarnoboru → Ostęp Graniczny.

> **Uwaga (MP-3+, 2026-07-26):** **korekta 3 — krok wiersza 75→50.** Rzędy N-S rozstawione
> co 75 zostawiały pusty pas 25 heksów (Czarnobór↔Martwe Pustkowia „wisiały" osobno). Blok
> ma wysokość ekranową 50, więc krok `50·row` skleja rzędy krawędź-w-krawędź. Zmienione:
> `region_blocks.py` (75→50), ta tabela (Wybrzeże r_off 100→75, MP 50→25, Siwe Granie −75→−50),
> `test_1542`. Martwe Pustkowia przesunięte o Δr=−25 i przeseedowane (#1494). Czarnobór/Kresy
> (row=0) bez zmian.

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
row=1 ↓    │WYBRZEŻE  │      [morze]        │  MARTWE     │
(styka się │ ŁEZ      │                     │  PUSTKOWIA  │
z row=0,   │(wybrzeże,│                     │  (ruiny,    │
patrz      │ piraci)  │                     │   pustkowie)│
tabela)    ─────────────────────────────────────────────────
```

> Kolumna `q:0..49` w row=1 to `[morze]` (brak krainy) — Wybrzeże i Pustkowia nie graniczą
> ze sobą lądem. Rzędy row=0 ↔ row=1 stykają się pionowo (krok 50). Bounding-box r-band
> zależy od kolumny (shear), więc dokładne `r_min/r_max` bierz z tabeli, nie z tego schematu.

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

## Płynne przejścia terenu na granicach (border blending) — DO ZROBIENIA przy pełnej mapie

> Wymaganie Piotra (2026-07-26): gdy zejdzie się cała mapa 6 krain, **teren na styku
> dwóch krain ma przechodzić płynnie** — podobne rodzaje terenu po obu stronach granicy,
> nie skok „śnieżne góry → nagle jezioro/morze". Krawędź to strefa przejściowa, nie ściana.

Zasada rodzin terenu na granicy (para krain A|B):
- **Dobierz rodzinę mostkującą.** Góry↔równiny → pas pogórza/wzgórz. Las↔pustkowie →
  wrzosowiska/martwa ziemia. Ląd↔morze → wybrzeże/plaża/klify, nie urwisko w wodę.
- **Zakaz twardych skoków** na stykających się heksach: śnieg/mountain **nie** sąsiaduje
  bezpośrednio z sea/lake; sol/martwa_ziemia **nie** sąsiaduje z water/river.
- **Symetria.** Oba brzegi granicy dostają komplementarny bufor (~2–3 heksy w głąb każdej krainy).

Realizacja (osobny task, faza pełnej mapy — NIE w seedach pojedynczych krain):
1. `generate_region_map.py` — gradient terenu krainy „ciągnięty" ku offsetowi sąsiada
   (biasuj klasyfikator na krawędzi w stronę rodziny mostkującej sąsiada).
2. Pass **border-reconcile** po zseedowaniu obu sąsiadów: skanuj pary axial-sąsiadów
   z różnych krain, wykryj zakazane skoki, wstaw pas przejściowy (deterministycznie).
3. Guard w `test_1542`/nowym teście: żaden styk międzykrainowy nie łamie tabeli zakazów.

Status: **zaplanowane** (issue śledzący w fali map). Obecnie stykają się tylko
Czarnobór↔Martwe Pustkowia (MP `coming`, Czarnobór jeszcze nie wsiany) — pełny blending
ma sens dopiero gdy oba brzegi są w DB.

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
