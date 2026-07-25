# Mapa 2.0 (#1543) — jak wrócić do starej mapy

Piotr potwierdził wariant **D** (tło biomów, renderer PixiJS). To jest siatka
bezpieczeństwa na wypadek gdyby nowy system nie zadziałał. Trzy niezależne
warstwy — możesz cofnąć samą grafikę mapy **albo** dane, osobno.

## Co jest zabezpieczone (stan z 2026-07-25)

| Warstwa | Backup | Gdzie |
|---|---|---|
| **Dane hexów** (cała mapa świata) | pełny zrzut bazy | `backups/ai_gm_20260725_094638.db` na `.61` |
| **Dane hexów** (kanon w git) | seedy krain | `docs/world/world_map_seed.json` + `data/regions/region_*.json` (w git, nietknięte) |
| **Kod starej mapy** (SVG) | git tag | `backup/map-svg-pre-mapa20-20260725` (commit `8161e105`) |

Stan w chwili backupu: `world_hexes` map_level=0 = **7540 hexów** (czarnobor 2500,
kresy 2493, siwe_granie 2546, koronne 1).

## Powrót — 3 scenariusze

### 1. Nowa mapa brzydko wygląda / muli, chcę starą grafikę (dane OK)
Nowy renderer PixiJS jest **za przełącznikiem** — stara mapa SVG zostaje w kodzie
jako fallback. Najpierw spróbuj flagi (admin → Mapa → przełącznik „silnik mapy",
dodany w M-2c). Jeśli flaga nie wystarczy, cofnij sam plik renderera:
```bash
# na .61, w /home/piotrszmidt/ai-gm
sudo -u piotrszmidt git checkout backup/map-svg-pre-mapa20-20260725 -- frontend/admin/sections/map.js
sudo -u piotrszmidt git commit -m "revert: stara mapa SVG"
sudo -u piotrszmidt git push origin develop
```
Dane hexów zostają nietknięte (nowy renderer nic w nich nie zmienia).

### 2. Coś namieszało w danych mapy — przywróć bazę
```bash
# na .61
./scripts/restore.sh ai_gm_20260725_094638.db   # auto-backupuje obecną najpierw
```

### 3. Reseed krain z kanonu (git = prawda)
```bash
# na .61 — odtwarza world_hexes z committowanego seeda
python3 scripts/seed_world_map.py --force
```

## Zasada projektowa M-2c (dlatego revert jest tani)
- Nowy renderer = **osobny moduł**, montowany przez przełącznik. Stary SVG **nie
  jest kasowany**, zostaje domyślny dopóki D nie przejdzie testów.
- Mapa 2.0 to **wyłącznie warstwa prezentacji** — zero zmian w danych hexów
  (q, r, teren, lokacje). Dlatego żaden backup danych nie jest tak naprawdę
  potrzebny do cofnięcia grafiki; robimy go tylko na wszelki wypadek.
