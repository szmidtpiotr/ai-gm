# Runbook: Jak dodać nową krainę (DLC)

> Wzorzec sprawdzony na Siwe Granie (RM7, 2026-06-29). Dla kolejnych krain (Czarnobór,
> Koronne Niziny, Wybrzeże Łez, Martwe Pustkowia) powtarzaj ten schemat.

Kontekst: każda kraina to osobny plik-seed `data/regions/region_<key>.json`. Dodanie krainy
= dorzucenie pliku + flip statusu `coming`→`live`. Kanon = pliki w git (commit = zgoda Piotra).

---

## Krok 1 — Wygeneruj mapę krainy

```bash
# Na maszynie Claude (.19) lub hoście DEV (.61):
python3 scripts/generate_region_map.py --region <key>
```

Skrypt tworzy:
- `data/regions/region_<key>.json` — heksy z biomami per profil krainy (tab. w RM5)
- `temp-img/region_<key>.png` — podgląd do akceptacji wizualnej

**Profil biomów** per kraina → `docs/FAZA_RM_MAPA_KRAIN.md` sekcja 2, kolumna `biome-profil`.

**Lore-kotwice** (ważne lokalizacje) → `docs/world/LORE_v1_KANON.md` sekcja 3.
Upewnij się, że heksy przy tych koordynatach mają `label` zgodny z lore (Kopalnia Czarnego
Hutmana, Klasztor Iskry itp.). Edytuj JSON ręcznie lub doregeneruj z parametrami.

**Koordynaty absolutne** → `docs/world/continent_layout.md` (offsets per kraina).
Heksy MUSZĄ leżeć w bounding-boxie danej krainy — brak nakładania z innymi.

---

## Krok 2 — Akceptacja wizualna Piotra

Pokaż `temp-img/region_<key>.png` Piotrowi. Czekaj na OK przed dalszymi krokami.

---

## Krok 3 — Commit pliku (kanon)

```bash
git add data/regions/region_<key>.json
git commit -m "feat: region_<key>.json — mapa krainy <Nazwa> (RM5/DLC)"
```

Dopiero commit czyni plik kanonem. Przed commitem = szkic, po = zatwierdzone.

---

## Krok 4 — Podepnij lokacje krasnoludzkie / krain (game_locations)

Sprawdź `game_locations WHERE region='<key>'`. Lokacje muszą mieć:
- `region = '<key>'`
- `world_hex_q, world_hex_r` wskazujące na heks W TEJ KRAINIE (nie Kresach!)
- `placement = 'placed'` (nie floating)

Popraw błędne koordynaty SQL-em (wzór z RM7):
```sql
UPDATE game_locations
SET world_hex_q=<q>, world_hex_r=<r>, placement='placed'
WHERE key='<loc_key>';
```

Wartości q/r z `data/regions/region_<key>.json` — hex z `label` pasującym do lokacji.

---

## Krok 5 — Seed heksów do world_hexes

```bash
# Na hoście DEV (.61):
python3 scripts/seed_world_map.py --region <key>
```

Weryfikacja:
```bash
docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db \
  "SELECT count(*) FROM world_hexes WHERE region='<key>' AND map_level=0"
# Wynik: ~2500
```

Jeśli już są heksy i chcesz nadpisać: `--force`.

---

## Krok 6 — Flip statusu na `live`

**W pliku JSON** (`data/regions/region_<key>.json`):
```json
"status": "live"
```

**W `scripts/snapshot_world_map.py`** (REGION_META, ok. linia 28):
```python
"<key>": {"label": "<Nazwa>", "status": "live", "w": 50, "h": 50},
```

**W bazie danych DB**:
```bash
docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db \
  "UPDATE world_regions SET status='live' WHERE key='<key>'"
```

**W `docs/world/continent_layout.md`** — tabela bounding-boxów, kolumna `status`.

---

## Krok 7 — Weryfikacja

```bash
# Heksy istnieją
docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db \
  "SELECT count(*) FROM world_hexes WHERE region='<key>' AND map_level=0"
# → >0

# Status live
docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db \
  "SELECT key,status FROM world_regions WHERE key='<key>'"
# → <key>|live

# Lokacje na właściwych heksach
docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db \
  "SELECT key,world_hex_q,world_hex_r FROM game_locations WHERE region='<key>' AND placement='placed'"
# → lokacje z q,r w bounding-boxie krainy (nie null, nie Kresy)
```

Admin map: otwórz `/admin/#map` → wybierz krainę z dropdownu → powinna być widoczna
(nie szara mgła). Kampania w sąsiedniej krainie może teraz przekroczyć granicę.

---

## Krok 8 — Snapshot + commit

```bash
# Na hoście DEV (.61):
python3 scripts/snapshot_world_map.py --region <key>
# Weryfikuje round-trip (DB → plik)

# Commit wszystkich zmian
git add data/regions/region_<key>.json
git add docs/world/continent_layout.md
git add scripts/snapshot_world_map.py
git commit -m "feat(#<issue>): DLC <Nazwa> live — seed+flip+lokacje"
```

---

## Checklist szybki

```
[ ] generate_region_map.py --region <key>  → JSON + PNG
[ ] Piotr akceptuje PNG
[ ] Commit region_<key>.json (kanon)
[ ] game_locations z region=<key> mają właściwe world_hex_q/r
[ ] seed_world_map.py --region <key>  → world_hexes
[ ] region_siwe_granie.json status='live'
[ ] snapshot_world_map.py REGION_META status='live'
[ ] DB: UPDATE world_regions SET status='live' WHERE key='<key>'
[ ] continent_layout.md → tabela + lista plików
[ ] Weryfikacja SQL (count + status + lokacje)
[ ] Admin map /admin/#map pokazuje krainę
[ ] Snapshot + commit
```

---

## Znane ograniczenia (stan 2026-06-29)

**Gap koordynatów na granicy Kresy↔Siwe Granie:** Kresy mają r min=-24, Siwe Granie r max=-26.
Heksy nie są fizycznie sąsiednie w grafie heksów (brakuje r=-25). Podróż hex-po-hexie nie przekroczy
granicy automatycznie. Teaser-label "ku Siwym Graniom"/"ku Kresom" to narracyjny marker — nie
fizyczne przejście. Osobne issue dla mechaniki teleportu/granicy.
