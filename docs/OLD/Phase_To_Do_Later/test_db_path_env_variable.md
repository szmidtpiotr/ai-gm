# ToDo: `AI_TEST_DB_PATH` — testowanie backendu poza kontenerem Docker

> **Priorytet:** niski (nie blokuje)
> **Odkryte przy:** Phase 8D LOC-4 (PROMPT 15), 2026-04-29
> **Kontekst:** merge Phase 8D → `develop`

---

## Problem

Kod backendu ma sztywno `DB_PATH = "/data/ai_gm.db"` (m.in. `admin_auth` i inne moduły).
Na hoście `.61` katalog `/data` nie istnieje bez `sudo`, więc `pytest` poza kontenerem kończy się na:

```
sqlite3.OperationalError: unable to open database file
```

Obecnie właściwy sposób testowania backendu:

```bash
docker compose -f docker-compose.dev.yml exec -T backend python3 -m pytest tests/ -v
```

---

## Proponowane rozwiązanie

Dodanie zmiennej środowiskowej `AI_TEST_DB_PATH` (lub ogólniej `DB_PATH` z enva) do konfiguracji backendu:

```python
# backend/app/config.py lub db.py
import os
DB_PATH = os.environ.get("DB_PATH", "/data/ai_gm.db")
```

Przy testach hostowych wystarczy wtedy:

```bash
export DB_PATH="/home/piotrszmidt/ai-gm/data-dev/ai_gm.db"
pytest backend/tests/ -v
```

Alternatywa: symlink `/data` → `~/ai-gm/data-dev` (wymaga `sudo` lub zmiany uprawnień katalogu `/data`).

---

## Zakres zmiany

- `backend/app/config.py` lub odpowiednik — `DB_PATH` z `os.environ.get()`
- Ewentualnie: `pytest.ini` / `conftest.py` z `@pytest.fixture` ustawiającym `DB_PATH` dla testów
- Bez zmian w `docker-compose.yml` (kontenery nadal używają `/data`)

---

## Nie blokuje

Testy w kontenerze DEV działają poprawnie. Zmiana jest wygodnictwem dla lokalnego developmentu bez Dockera.
