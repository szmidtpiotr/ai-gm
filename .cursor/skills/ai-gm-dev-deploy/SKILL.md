---
name: ai-gm-dev-deploy
description: >-
  Wdrożenie backendu AI-GM w środowisku dev na serwerze 192.168.1.61 (docker-compose.dev.yml),
  weryfikacja kodu T01–T06 w kontenerze, pytest oraz podgląd gm_plan_json / łuku fabularnego w SQLite.
---

# AI-GM — wdrożenie dev na `.61` i weryfikacja Phase 9B (T01–T06)

## Kiedy stosować

- Po merge/pushu na `develop`, gdy trzeba **odświeżyć obraz** `ai-gm-dev-backend` na serwerze.
- Gdy użytkownik pyta, czy **T05/T06 są wdrożone** albo chce **sprawdzić treść łuku** w planie MG.

## Zasada wykonania

Wszystkie komendy z tego skilla wykonuj **wyłącznie na serwerze `192.168.1.61` przez SSH**.
Nie uruchamiaj lokalnie Dockera, pytesta ani żadnych buildów dla tego projektu.
Lokalny katalog `/home/piotrszmidt/remote_mount/ai-gm` jest tylko **zmapowanym folderem roboczym** do edycji plików.

## Stałe

| Co | Wartość |
|----|---------|
| Host SSH | `piotrszmidt@192.168.1.61` |
| Lokalny mount roboczy | `/home/piotrszmidt/remote_mount/ai-gm` |
| Katalog repo na serwerze | `/home/piotrszmidt/ai-gm` |
| Compose dev | `docker compose -f docker-compose.dev.yml` |
| Kontener backend dev | `ai-gm-dev-backend-1` |
| Port API na hoście | **8100** |
| Port frontend dev na hoście | **3002** |
| SQLite w kontenerze (domyślny dev z compose) | `/data/ai_gm.db` (volume `./data-dev` na hoście) |

## Sekwencja wdrożenia backendu dev

Wykonaj na serwerze (SSH):

```bash
ssh piotrszmidt@192.168.1.61
cd /home/piotrszmidt/ai-gm
git fetch origin && git pull origin develop
docker compose -f docker-compose.dev.yml build backend --no-cache
docker compose -f docker-compose.dev.yml up -d backend
```

Poczekaj na **healthy** (`docker ps`). Opcjonalnie: `docker restart ai-gm-dev-backend-1` po samym pullu, jeśli kod jest montowany (rzadziej niż pełny build).

## Czego nie robić

- Nie wykonuj `docker compose up`, `docker build`, `pytest` ani `python ...` na lokalnej maszynie.
- Nie traktuj kontenerów lokalnych jako źródła prawdy dla stanu środowiska.
- Nie weryfikuj wdrożenia przez `localhost`; używaj domeny dev wskazanej poniżej.

## Weryfikacja obecności T01–T06 w obrazie

W kontenerze sprawdź pliki i sygnatury (ścieżka aplikacji: `/app/app/...`):

- **T06:** `app/services/gm_plan_schema.py` (`gm_plan_is_ready`, `merge_gm_plan_patch`), `app/api/campaigns.py` (merge PATCH).
- **T05:** `app/services/gm_plan_generation_service.py`, w `characters.py` — `generate_initial_gm_plan_with_retries`, w `turns.py` — `_require_gm_plan_before_narrative_llm`.
- **T02–T04:** `history_summary_service.py` — `SUMMARY_AUDIENCE_GM`, `PLAYER_SUMMARY_SYSTEM_APPEND`, `format_gm_plan_block`.
- **T01:** test `tests/test_history_summary_t01_dual_prompt.py`.

Testy (w kontenerze, `/app`):

```bash
docker exec -w /app ai-gm-dev-backend-1 python3 -m pytest \
  tests/test_history_summary_t01_dual_prompt.py \
  tests/test_history_summary_t02_audience.py \
  tests/test_history_summary_t03_player_only.py \
  tests/test_history_summary_t04_gm_context.py \
  tests/test_gm_plan_schema.py \
  tests/test_t05_gm_plan_generation.py -q
```

## Logi i sukces generacji planu (T05)

```bash
docker logs ai-gm-dev-backend-1 --since 30m 2>&1 | grep -E 'gm_plan_generation_ok|POST /api/campaigns/.*/characters'
```

Zdarzenie `gm_plan_generation_ok` przy `POST .../characters` oznacza zapisanie planu po LLM.

## Podgląd treści aktywnego łuku (JSON)

```bash
docker exec ai-gm-dev-backend-1 python3 -c "
import json, sqlite3
conn = sqlite3.connect('/data/ai_gm.db')
conn.row_factory = sqlite3.Row
r = conn.execute(
  '''SELECT id, title, gm_plan_json FROM campaigns ORDER BY id DESC LIMIT 1'''
).fetchone()
d = json.loads(r['gm_plan_json'] or '{}')
aid = d.get('active_arc_id')
arc = (d.get('arcs') or {}).get(aid or 'default', {})
print(json.dumps(arc, ensure_ascii=False, indent=2))
"
```

## Publiczna domena dev

`aigm-dev.studio-colorbox.com` — frontend zwykle za proxy do hosta `.61`; API musi wskazywać na ten sam backend dev co powyżej (np. proxy do `:8100`), inaczej UI i wersja API mogą się rozjeżdżać.

## Zasada środowiska

Domyślnie **nie** restartować produkcyjnego `ai-gm-backend-1` bez wyraźnej prośby — patrz `.cursor/rules/dev-environment.mdc`.
