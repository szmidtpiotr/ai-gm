# AI-GM — Raport Napraw: BUG-02 i BUG-03

**Źródło weryfikacji:** Sesja testowa LogDEBUG MCP, tury 37–46, kampania id=1099  
**Środowisko testowe:** PROD (`aigm-prod.studio-colorbox.com`)  
**Data weryfikacji:** 2026-05-25  
**Repo:** `szmidtpiotr/ai-gm`  

---

## Kontekst

Zgodnie z plikiem `v2_development_fix.md` następujące bugi zostały oznaczone jako **DONE**:
- BUG-01 ✅ — potwierdzone działanie w testach (hook `remove_item` działa)
- BUG-07 ✅ — potwierdzone działanie w testach (brak `[LOCATION_BLOCKED]` w narracji)

Następujące bugi oznaczone jako **DONE** w dokumentacji **NIE działają** na środowisku PROD:
- **BUG-02** — zegar gry wciąż zamrożony
- **BUG-03** — NPC wciąż nie zapisywani do bazy (częściowo działa w kontekście LLM)

---

## BUG-02 — Zegar gry zamrożony ❌

### Dowód z testu

Po 7 nowych turach narracyjnych i podróżnej (tury 37–43), zegar pokazuje nadal:
```
Czas gry: Dzień 1, 09:00
```
Oczekiwane zachowanie według dokumentacji: +15 min/tura narracyjna, +60 min/tura podróżna.
Po 7 turach powinno być minimum: `Dzień 1, 11:45`.

### Co według dokumentacji zostało zrobione (DONE)

```
clock_service dostał wsparcie dla minut (session_flags.ingame_minutes, 0–59).
Nowy clock_config_service trzyma konfigurację w game_config_meta
(defaults: narrative=15min, combat=5min, travel=60min).
Funkcja create_turn_log w turns.py po każdym zapisie tury wywołuje
advance_clock z wartością zależną od route.
```

### Prawdopodobna przyczyna niedziałania

Możliwe scenariusze:
1. Fix wdrożony tylko na **DEV**, nie zdeployowany na **PROD**
2. Migracja `game_config_meta` nie wykonana na PROD DB
3. `advance_clock` jest wywoływany ale `session_flags.ingame_minutes` nie jest persystowane poprawnie
4. Frontend nie odświeża pola `game_time` po turze (cache)

### Kroki diagnostyczne

```bash
# 1. Sprawdź czy clock_config_service.py istnieje na PROD
docker exec ai-gm-prod-backend-1 ls backend/app/services/ | grep clock

# 2. Sprawdź czy game_config_meta istnieje w DB
docker exec ai-gm-prod-backend-1 sqlite3 data/ai_gm.db \
  "SELECT * FROM game_config_meta LIMIT 5;"

# 3. Sprawdź czy kolumna ingame_minutes istnieje w session_flags
docker exec ai-gm-prod-backend-1 sqlite3 data/ai_gm.db \
  "PRAGMA table_info(session_flags);"

# 4. Sprawdź logi po wykonaniu tury
docker logs ai-gm-prod-backend-1 --tail=50 | grep -i clock

# 5. Sprawdź endpoint konfiguracji zegara
curl -s http://localhost:8000/api/admin/clock-config
```

### Fix — co dokładnie sprawdzić/naprawić

**Jeśli fix nie jest na PROD:**
```bash
cd /home/piotrszmidt/ai-gm
git log --oneline -10  # sprawdź czy commit z clock_service jest w main
./scripts/promote_and_deploy_prod.sh "fix: deploy clock_service to prod"
```

**Jeśli migracja nie wykonana:**
```bash
# Wykonaj migrację ręcznie na PROD DB
docker exec ai-gm-prod-backend-1 python -c \
  "from backend.app.services.clock_config_service import init_defaults; init_defaults()"
```

**Jeśli advance_clock nie jest wywoływany:**  
Sprawdź `backend/app/api/turns.py` funkcję `create_turn_log` — czy zawiera wywołanie:
```python
await advance_clock(campaign_id, route=route)
```
Jeśli nie ma — dodaj po linii zapisu tury do DB.

### Test weryfikacyjny po naprawie

```
1. Wejdź na https://aigm-prod.studio-colorbox.com/
2. Sprawdź zegar w nagłówku — powinien pokazywać czas z minutami
3. Zagraj turę narracyjną → zegar powinien przeskoczyć o +15 min
4. Zagraj turę podróżną ("idę do lasu") → zegar powinien przeskoczyć o +60 min
5. GET http://localhost:8000/api/admin/clock-config
   → oczekiwany wynik: {"narrative_min": 15, "combat_min": 5, "travel_min": 60}
6. docker exec ai-gm-prod-backend-1 pytest backend/tests/test_bug02_clock_minutes.py -v
```

---

## BUG-03 — NPC nie zapisywani do bazy ❌ (częściowo)

### Dowód z testu

Eldric rozmawiał z **Martą** (tury 37–38) i **Papą Iwanem** (tury 41–42).  
Podsumowanie AI MG poprawnie wymienia NPC:
```
"NPC tła aktywni: karczmarka Marta, Eldran, Papa Iwan…"
```
Ale pole `Znani NPC` w campaign summary:
```
Znani NPC: brak
```

**Wniosek:** LLM ma NPC w kontekście (system prompt działa), ale **hook parsujący `npc_met` z odpowiedzi MG i zapisujący do tabeli `campaign_known_npcs` nie działa** lub tabela nie istnieje na PROD.

### Co według dokumentacji zostało zrobione (DONE)

```
Nowa tabela campaign_known_npcs (FK do npcs, z polami notes, relation_status,
first_met_location, first_met_turn).
Serwis npc_memory_service.py z funkcjami record_npc_met / update_npc_relation.
Hook w create_turn_log parsuje pola npc_met i npc_update z odpowiedzi MG.
context_injector dołącza ostatnich 10 poznanych NPC do system promptu.
Nowa zakładka "👥 Znani NPC" w admin panel.
Nowy endpoint GET /api/admin/campaigns/{id}/known-npcs.
```

### Prawdopodobna przyczyna niedziałania

1. Tabela `campaign_known_npcs` nie istnieje na PROD (migracja nie wykonana)
2. `npc_memory_service.py` nie zdeployowany na PROD
3. Hook w `create_turn_log` nie parsuje pola `npc_met` — MG może nie emitować tego pola
4. MG emituje NPC w podsumowaniu tekstowym, ale nie w strukturalnym polu JSON `npc_met`

### Kroki diagnostyczne

```bash
# 1. Sprawdź czy tabela campaign_known_npcs istnieje
docker exec ai-gm-prod-backend-1 sqlite3 data/ai_gm.db \
  ".tables" | grep npc

# 2. Sprawdź strukturę tabeli (jeśli istnieje)
docker exec ai-gm-prod-backend-1 sqlite3 data/ai_gm.db \
  "PRAGMA table_info(campaign_known_npcs);"

# 3. Sprawdź czy npc_memory_service istnieje
docker exec ai-gm-prod-backend-1 ls backend/app/services/ | grep npc

# 4. Sprawdź czy endpoint known-npcs odpowiada
curl -s http://localhost:8000/api/admin/campaigns/1099/known-npcs

# 5. Sprawdź ostatnią odpowiedź MG w surowym JSON — czy zawiera pole npc_met
docker exec ai-gm-prod-backend-1 sqlite3 data/ai_gm.db \
  "SELECT gm_response_raw FROM turn_logs WHERE campaign_id=1099 ORDER BY id DESC LIMIT 3;"
```

### Fix — co dokładnie sprawdzić/naprawić

**Jeśli tabela nie istnieje — wykonaj migrację:**
```bash
docker exec ai-gm-prod-backend-1 python -c \
  "from backend.app.migrations_admin import run_npc_memory_migration; run_npc_memory_migration()"
```
Lub ręcznie:
```sql
CREATE TABLE IF NOT EXISTS campaign_known_npcs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  campaign_id INTEGER NOT NULL,
  npc_id INTEGER,
  name TEXT NOT NULL,
  role TEXT,
  notes TEXT,
  relation_status TEXT DEFAULT 'neutral',
  first_met_location TEXT,
  first_met_turn INTEGER,
  last_seen_turn INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
);
```

**Jeśli MG nie emituje `npc_met` w JSON:**  
Sprawdź `backend/prompts/system_prompt.txt` — czy zawiera sekcję z instrukcją emitowania `npc_met`. Jeśli nie, dodaj:
```
Gdy gracz spotyka lub rozmawia z nową postacią po raz pierwszy, dodaj do odpowiedzi JSON:
"npc_met": {"name": "Imię", "role": "rola postaci", "location": "nazwa lokacji"}
```

**Jeśli hook nie parsuje `npc_met`:**  
W `backend/app/api/turns.py`, funkcja `create_turn_log`, sprawdź czy istnieje:
```python
if gm_json.get("npc_met"):
    await npc_memory_service.record_npc_met(
        campaign_id=campaign_id,
        npc_data=gm_json["npc_met"],
        turn=turn_number,
        location=current_location
    )
```

### Test weryfikacyjny po naprawie

```
1. Sprawdź endpoint: GET /api/admin/campaigns/1099/known-npcs
   → powinien zwrócić listę (może być pusta dla starych tur)
2. Zagraj nową turę gdzie gracz rozmawia z nową postacią po raz pierwszy
3. Sprawdź ponownie endpoint — nowy NPC powinien się pojawić
4. W panelu admina otwórz kampanię → zakładka "👥 Znani NPC"
5. Zagraj turę gdzie pomagasz NPC ("pomagam mu") — status powinien zmienić się na "friendly"
6. docker exec ai-gm-prod-backend-1 pytest backend/tests/test_bug03_npc_memory.py -v
```

---

## Podsumowanie Akcji

| Priorytet | Akcja | Gdzie |
|---|---|---|
| 1 | Sprawdź czy fix BUG-02 i BUG-03 jest w branchu `main` | `git log --oneline -15` |
| 2 | Sprawdź czy tabela `campaign_known_npcs` i `game_config_meta` istnieją na PROD DB | SQLite diagnostics |
| 3 | Jeśli brak — wykonaj migracje na PROD | `migrations_admin.py` |
| 4 | Jeśli migracje OK — sprawdź logi backendu po turze pod kątem błędów | `docker logs` |
| 5 | Uruchom testy automatyczne | `pytest test_bug02_*` i `test_bug03_*` |

---

## Co Działa (nie ruszać)

- **BUG-01** `remove_item` hook — ✅ działa na PROD, potwierdzono w turze 38
- **BUG-07** `LOCATION_BLOCKED` ukryty — ✅ działa na PROD, potwierdzono w turach 37–43
- **Jakość narracji MG** — wysoka, Papa Iwan to przykład dobrego NPC z charakterem
- **Zmiana lokacji** — `location_intent` działa, nowa lokacja `Zagajnik przy ruinach` utworzona poprawnie

---

*Raport z weryfikacji automatycznej sesji testowej LogDEBUG MCP, kampania id=1099, 2026-05-25.*
