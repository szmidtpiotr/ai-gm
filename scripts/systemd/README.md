# Auto-commit kanonu mapy (#1551)

Rozwiązuje problem: po każdym „Pieczętuj kanon" w admin→Mapa Piotr nie musi już
prosić o commit — pliki `data/regions/region_*.json` są commitowane i pushowane
automatycznie.

## Jak działa

1. Endpoint `POST /api/admin/world/map/snapshot` (przycisk „🖋 Pieczętuj kanon")
   zapisuje `data/regions/region_*.json` z bieżącego `world_hexes`.
   Wymaga montażu `./data/regions:/data/regions:rw` w `docker-compose.dev.yml`
   (było `:ro` → HTTP 500, naprawione w #1551).
2. `aigm-canon-autocommit.path` (systemd) obserwuje `data/regions/`.
3. Zmiana → uruchamia `aigm-canon-autocommit.service` (jako `piotrszmidt`) →
   `scripts/autocommit_canon.sh`: batch (sleep 4) + `git add data/regions
   docs/world/world_map_seed.json` + commit + push (best-effort).
   Commituje WYŁĄCZNIE pliki kanonu; nic innego nie sweepuje. flock = pojedyncza
   instancja (snapshot „wszystkie krainy" = jeden commit).

## Instalacja na hoście DEV (.61)

```bash
sudo cp scripts/systemd/aigm-canon-autocommit.{path,service} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now aigm-canon-autocommit.path
```

Weryfikacja: `sudo journalctl -u aigm-canon-autocommit.service -f`, potem
kliknij „Pieczętuj kanon" — powinien pojawić się commit `auto-snapshot kanonu`.

## PROD

Na PROD kanon nie jest edytowany z UI (reseed z gita), więc watcher nie jest
instalowany. Gdyby kiedyś był potrzebny — ten sam mont `:rw` + te same unity.
