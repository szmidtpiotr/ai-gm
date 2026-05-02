<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-29 -->

# PROMPT 11 — Fix opening scene `action=create` not persisted to DB

> **Branch:** `phase-8d-location-integrity` | Working tree: czysty  
> **Plik:** `docs/Phase_8D_Location_Integrity/11_prompt_fix4.md`

---

## Cel

Naprawić przypadek, w którym GM podczas **opening scene / startu kampanii** zwraca
`location_intent` z `action=create`, ale lokalizacja **nie trafia do `game_locations`**
jako AI-generated pending location.

Przykład z kampanii `1057`:

```json
{
  "action": "create",
  "target_label": "Rozmokła droga przy rogatkach wioski",
  "parent_key": "start",
  "description": "Błotnisty trakt, mgła, zniszczony wóz, postacie przy drodze, odgłosy ze starego płotu."
}
```

Celem jest zapewnienie, że:
- `action=create` z odpowiedzi GM w opening scene działa i jest persisted,
- lokalizacja zapisuje się do `game_locations` z `ai_generated=1`, `approved=0`,
- pojawia się w admin panelu jako pending do zatwierdzenia,
- `game_sessions.current_location_id` jest ustawiane na nową lokalizację,
- mamy czytelne logi do debugowania.

---

## Diagnoza (potwierdzona odpowiedziami blokującymi)

| # | Fakt | Źródło |
|---|---|---|
| 1 | Router: `backend/app/api/characters.py`, funkcja `create_character` (linia ~882+) | Odpowiedź Cursora |
| 2 | Opening scene wywołuje tylko `generate_chat(...)` — brak `parse_location_intent` i `_process_location_intent` | Odpowiedź Cursora |
| 3 | `_process_location_intent()` nie jest w ogóle wywoływany w tym flow | Odpowiedź Cursora |
| 4 | `action=create` blokowane gdy `location_auto_create_enabled=0` | Odpowiedź Cursora |
| 5 | `skip_post_process=True` dotyczy tylko `turns.py` — nie ma wpływu na opening scene | Odpowiedź Cursora |
| 6 | Opening scene = **non-stream** (jednorazowy `generate_chat`, brak SSE) | Odpowiedź Cursora |
| 7 | Testy opening scene: `backend/tests/test_phase8e_starter_items.py` (linie 185–249) | Odpowiedź Cursora |

---

## Implementacja (REV 2)

### Krok 1 — Wyodrębnij helper `extract_and_process_location_intent()`

W `turns.py` lub dedykowanym module serwisowym wyodrębnij logikę parsowania
`location_intent` do funkcji wielokrotnego użytku:

```python
def extract_and_process_location_intent(
    raw_gm_response: str,
    campaign_id: int,
    session_id: int,
    db: sqlite3.Connection,
    source: str = "turns"  # "turns" | "opening_scene"
) -> None:
    """Parsuje location_intent z odpowiedzi GM i zapisuje do DB."""
    ...
```

> Jeśli refactor `turns.py` jest zbyt ryzykowny — skopiuj minimum logiki inline
> do `create_character`, ale zostaw `# TODO: unify with turns.py` z linkiem do linii.

### Krok 2 — Podepnij hook w `characters.py` po zapisie `campaign_turns`

W funkcji `create_character`, **po** linii zapisu `opening_message` do `campaign_turns`
(linia ~1058–1077):

```python
# Location integrity hook — opening scene
try:
    if flags.get("location_integrity_enabled"):
        extract_and_process_location_intent(
            raw_gm_response=opening_message,
            campaign_id=campaign_id,
            session_id=session_id,
            db=db,
            source="opening_scene"
        )
except Exception as e:
    logger.warning("location_hook_opening_scene_failed", error=str(e))
```

> `try/except` jest obowiązkowy — hook nie może crashować tworzenia postaci.

### Krok 3 — Ścieżka `action=create` dla opening scene (bypass `auto_create` flag)

Opening scene to **start kampanii**, nie ruch gracza. Lokalizacja musi być persisted
niezależnie od flagi `location_auto_create_enabled`.

W helperze / walidatorze, **przed** sprawdzeniem flagi `auto_create`, dodaj gałąź:

```python
if intent.action == "create" and source == "opening_scene":
    # Zawsze twórz — pierwsza lokalizacja kampanii, nie ruch gracza
    new_location_id = _create_new_location(
        campaign_id=campaign_id,
        label=intent.target_label,
        description=intent.description,
        parent_key=intent.parent_key or "start",
        ai_generated=True,
        approved=False,  # pending — admin zatwierdza
        db=db
    )
    logger.info("location_create_opening_scene_persisted",
                campaign_id=campaign_id,
                label=intent.target_label,
                location_id=new_location_id)
    return new_location_id
```

### Krok 4 — Zaktualizuj `game_sessions.current_location_id`

Po zapisaniu lokalizacji do `game_locations`:

```python
db.execute(
    "UPDATE game_sessions SET current_location_id = ? WHERE campaign_id = ?",
    (new_location_id, campaign_id)
)
db.commit()
```

### Krok 5 — Logi

| Event | Kiedy |
|---|---|
| `location_hook_opening_scene_start` | wejście do hooka |
| `location_create_opening_scene_persisted` | lokalizacja zapisana (+ `campaign_id`, `label`, `location_id`) |
| `location_hook_opening_scene_skipped` | brak `location_intent` lub flaga `location_integrity_enabled=0` |
| `location_hook_opening_scene_failed` | wyjątek — łapany, **nie** reraise |

### Krok 6 — Test regresyjny

W `backend/tests/test_phase8e_starter_items.py` lub nowym pliku
`test_phase8d_opening_location.py`:

```python
def test_opening_scene_creates_location(client, db):
    """Opening scene z location_intent.action=create persists do game_locations."""
    mock_response = json.dumps({
        "narrative": "Mgła ściele się nad drogą...",
        "location_intent": {
            "action": "create",
            "target_label": "Rozmokła droga przy rogatkach wioski",
            "parent_key": "start",
            "description": "Błotnisty trakt, mgła, zniszczony wóz."
        }
    })

    with patch("backend.app.api.characters.generate_chat", return_value=mock_response):
        resp = client.post("/api/campaigns/1/characters", json={...})
    assert resp.status_code == 200

    # Lokalizacja persisted
    row = db.execute(
        "SELECT id, ai_generated, approved FROM game_locations "
        "WHERE label = 'Rozmokła droga przy rogatkach wioski' AND campaign_id = 1"
    ).fetchone()
    assert row is not None
    assert row["ai_generated"] == 1
    assert row["approved"] == 0

    # current_location_id ustawione
    session = db.execute(
        "SELECT current_location_id FROM game_sessions WHERE campaign_id = 1"
    ).fetchone()
    assert session["current_location_id"] == row["id"]
```

---

## Czego NIE ruszać

- `docker-compose.yml` prod
- `data/ai_gm.db`
- istniejącej logiki hooka w `turns.py` — tylko wyodrębnij, nie zmieniaj zachowania
- flagi `location_auto_create_enabled` dla zwykłych tur — opening scene to osobna ścieżka

---

## Weryfikacja manualna na DEV (Cursor wykonuje po implementacji)

```bash
# Rebuild DEV
cd /home/piotrszmidt/ai-gm
docker compose -f docker-compose.dev.yml up -d --build --remove-orphans
curl -sf http://localhost:8100/api/healthz && echo "DEV OK"

# 1. Lokalizacja w DB
sqlite3 data/ai_gm.db \
  "SELECT id, label, ai_generated, approved FROM game_locations ORDER BY id DESC LIMIT 5;"

# 2. Pending w adminie
curl -s http://localhost:8100/api/admin/locations/pending | python3 -m json.tool

# 3. current_location_id ustawione
sqlite3 data/ai_gm.db \
  "SELECT campaign_id, current_location_id FROM game_sessions ORDER BY id DESC LIMIT 3;"
```

**Oczekiwane wyniki:**
- `game_locations`: nowy rekord `ai_generated=1`, `approved=0`, `label` = tekst z opening scene
- `/api/admin/locations/pending`: ta lokalizacja widoczna
- `game_sessions.current_location_id`: ustawione na ID nowej lokalizacji
- Logi Loki: event `location_create_opening_scene_persisted`

---

## Odpowiedzi Cursora (REV 1)

- **1.** Router: `backend/app/api/characters.py` → funkcja `create_character` (linia ~882+)
- **2.** Opening scene nie korzysta z parsera z `turns.py`; tylko `generate_chat(...)` w `create_character`
- **3.** `_process_location_intent()` nie jest wywoływany; podpiąć przy zapisie `opening_message` / `campaign_turns`
- **4.** `validate_move()` używa `location_auto_create_enabled`; przy `0` blokuje `action=create`
- **5.** `skip_post_process=True` tylko w `turns.py` / stream — nie dotyczy `/characters`
- **6.** Opening scene = non-stream (jednorazowy `generate_chat` → insert do `campaign_turns`)
- **7.** Testy: `backend/tests/test_phase8e_starter_items.py` (linie 185–249)
- **8.** Branch: `phase-8d-location-integrity`
- **9.** Working tree: czysty
- **10.** Brak możliwości ręcznego sprawdzenia na DEV — wymaga uruchomienia opening scene i weryfikacji `game_locations` / `admin/locations/pending`

---

## Co zostało zrobione *(uzupełnia Cursor)*

- Dodano `persist_ai_generated_location()` w `backend/app/services/location_validator.py`, który zapisuje `location_intent.action='create'` jako `game_locations` (`ai_generated=1`, `approved=0`), loguje `create_ok` i obsługuje `parent_key`.
- W `backend/app/api/characters.py` opening scene parsuje odpowiedź GM przez `parse_location_intent()` i przy `action=create` wywołuje helper, dzięki czemu każdy proces tworzenia postaci zapisuje pending lokalizację, niezależnie od flagi `location_auto_create_enabled`.
- Schema testowa `backend/tests/test_phase8e_starter_items.py` uzupełniono o tabelę `game_locations` oraz nowy test `test_opening_scene_creates_pending_location`, który symuluje `generate_chat` zwracające `location_intent` i weryfikuje `ai_generated=1`, `approved=0`.

## Notatki po implementacji *(uzupełnia Perplexity)*

- Testy: `docker exec ai-gm-dev-backend-1 python3 -m pytest tests/test_phase8e_starter_items.py -q` → **7 passed, 1 warning**. Zmiany poszły przez auto-create non-stream, więc `location_auto_create_enabled` może pozostać domyślnie włączona lub wyłączona bez blokowania opening scene.

---

## Notatki po implementacji *(uzupełnia Perplexity)*

*(Perplexity uzupełni po raporcie Cursora)*
