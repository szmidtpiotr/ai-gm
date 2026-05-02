<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-29 -->

# PROMPT 9A-2 — Phase 9: NPC CRUD API + Admin UI

> **Workflow:** Perplexity generuje REV 1 z pytaniami blokującymi → Cursor odpowiada → Perplexity generuje REV 2 → Cursor implementuje.
> **Branch roboczy:** `phase-9a-1-npc-schema` (kontynuacja — commit 9A-1 najpierw)
> **Plik:** `docs/Phase_9_NPC_System/9A-2_npc_api.md`
> **Zależności:** 9A-1 ✔️

---

## Cel

Dodanie CRUD API dla NPC oraz sekcji NPC w panelu admina (lista, tworzenie, edycja, usuwanie, przypisanie lokacji).

---

## Kontekst techniczny (potwierdzony przez Cursora)

- **Nowe pliki:** `backend/app/api/npcs.py`, `frontend/admin_panel/sections/npcs.js`
- **Modyfikowane:** `backend/app/main.py`, `frontend/admin_panel/index.html`
- **Wzorzec routera:** `APIRouter`, zwraca `{"ok": True, "data": ...}`, wyjątki → `HTTPException`
- **Wzorzec JS sekcji:** `export async function init(container)`, `adminFetch(...)`, `showToast(parseApiError(...), "error")`
- **Cache `?v=`:** nowy `npcs.js` → `v=1`; `index.html` → inkrement najwyższego `?v=` w sekcjach dynamicznych (aktualnie max `v=32` → nowy wpis `v=33`)
- **Czego NIE ruszać:** `docker-compose.yml` prod, `data/ai_gm.db`, inne sekcje panelu, `game_locations.npc_keys`

---

## Implementacja (REV 2)

> ✅ Cursor implementuje poniższe — brak blokerów.

### Krok 0 — Commit zmian z 9A-1

Przed implementacją — commit uncommitted 9A-1:

```bash
git add backend/app/migrations_admin.py backend/tests/test_phase9a_npc_schema.py
git commit -m "feat(npc): dodaj tabele npcs i npc_locations z seedem 4 NPC (9A-1)"
git status --short   # musi być czysty
```

### Krok 1 — `backend/app/api/npcs.py`

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sqlite3, json
from app.config import DB_PATH

router = APIRouter(prefix="/npcs", tags=["npcs"])


class NpcCreateReq(BaseModel):
    key: str
    label: str
    npc_type: str = "neutral"       # neutral | merchant | quest_giver | ally
    description: str | None = None
    personality_json: str = "{}"    # NIE dialogue_json
    is_shop: int = 0
    shop_inventory_json: str = "[]"
    is_active: int = 1
    location_keys: list[str] = []   # wiele lokacji → npc_locations


class NpcPatchReq(BaseModel):
    label: str | None = None
    npc_type: str | None = None
    description: str | None = None
    personality_json: str | None = None
    is_shop: int | None = None
    shop_inventory_json: str | None = None
    is_active: int | None = None
    location_keys: list[str] | None = None  # None = nie zmieniaj; [] = usuń wszystkie


def _validate_json_fields(fields: dict):
    """HTTP 400 jeśli personality_json lub shop_inventory_json nie jest valid JSON."""
    for f in ("personality_json", "shop_inventory_json"):
        if f in fields and fields[f] is not None:
            try:
                json.loads(fields[f])
            except ValueError:
                raise HTTPException(400, f"Invalid JSON in {f}")


def _set_npc_locations(conn, npc_id: int, location_keys: list[str]):
    """Replace lokacji NPC — DELETE + INSERT OR IGNORE."""
    conn.execute("DELETE FROM npc_locations WHERE npc_id = ?", (npc_id,))
    for loc_key in location_keys:
        conn.execute(
            "INSERT OR IGNORE INTO npc_locations (npc_id, location_key) VALUES (?, ?)",
            (npc_id, loc_key)
        )


def _get_location_keys(conn, npc_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT location_key FROM npc_locations WHERE npc_id = ? ORDER BY location_key",
        (npc_id,)
    ).fetchall()
    return [r[0] for r in rows]


@router.get("")
def list_npcs(active_only: bool = False):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        q = "SELECT * FROM npcs"
        if active_only:
            q += " WHERE is_active = 1"
        rows = conn.execute(q + " ORDER BY npc_type, label").fetchall()
        data = []
        for r in rows:
            npc = dict(r)
            npc["location_keys"] = _get_location_keys(conn, npc["id"])
            data.append(npc)
    return {"ok": True, "data": data}


@router.get("/{npc_id}")
def get_npc(npc_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM npcs WHERE id = ?", (npc_id,)).fetchone()
        if not row:
            raise HTTPException(404, "NPC not found")
        npc = dict(row)
        npc["location_keys"] = _get_location_keys(conn, npc_id)
    return {"ok": True, "data": npc}


@router.post("")
def create_npc(body: NpcCreateReq):
    _validate_json_fields({"personality_json": body.personality_json,
                           "shop_inventory_json": body.shop_inventory_json})
    with sqlite3.connect(DB_PATH) as conn:
        try:
            cur = conn.execute(
                """INSERT INTO npcs
                   (key, label, npc_type, description, personality_json,
                    is_shop, shop_inventory_json, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (body.key, body.label, body.npc_type, body.description,
                 body.personality_json, body.is_shop, body.shop_inventory_json,
                 body.is_active)
            )
            npc_id = cur.lastrowid
            if body.location_keys:
                _set_npc_locations(conn, npc_id, body.location_keys)
            conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(409, "NPC key already exists")
    return {"ok": True, "id": npc_id}


@router.patch("/{npc_id}")
def patch_npc(npc_id: int, body: NpcPatchReq):
    data = body.model_dump(exclude_unset=True)
    location_keys = data.pop("location_keys", None)
    _validate_json_fields(data)
    with sqlite3.connect(DB_PATH) as conn:
        if data:
            data["updated_at"] = "datetime('now')"
            set_clause = ", ".join(f"{k} = ?" for k in data)
            conn.execute(
                f"UPDATE npcs SET {set_clause} WHERE id = ?",
                (*data.values(), npc_id)
            )
        if location_keys is not None:
            _set_npc_locations(conn, npc_id, location_keys)
        conn.commit()
    return {"ok": True}


@router.delete("/{npc_id}")
def delete_npc(npc_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM npcs WHERE id = ?", (npc_id,))
        conn.commit()
    return {"ok": True}
```

### Krok 2 — Rejestracja w `main.py`

Wzorując się na istniejących `include_router`:

```python
from app.api import npcs
app.include_router(npcs.router, prefix="/api")
```

Pokaż diff `main.py` przed zapisem.

### Krok 3 — `frontend/admin_panel/sections/npcs.js`

Nowy plik wg wzorca `accounts.js` (`export async function init(container)`):

```javascript
export async function init(container) {
    container.innerHTML = `
        <div class="section-header">
            <h2>NPC</h2>
            <button id="npc-add-btn" class="btn-primary">+ Nowy NPC</button>
        </div>
        <div id="npc-list"></div>
        <div id="npc-form-container" style="display:none"></div>
    `;
    await refreshNpcs();
    document.getElementById('npc-add-btn').addEventListener('click', () => showNpcForm());
}

async function refreshNpcs() { /* GET /api/npcs → renderuje tabelę */ }

function renderNpcsTable(npcs) {
    // Kolumny: ID | Key | Label | Typ | Lokacje | Sklep | Aktywny | Akcje
    // Akcje: [Edytuj] [Usuń]
    // Lokacje: wyświetla location_keys.join(', ') lub '—' jeśli brak
}

function showNpcForm(npc = null) {
    // Formularz: key, label, npc_type (select), description,
    //            is_shop (checkbox), personality_json (textarea),
    //            location_keys (textarea — jedna lokacja per linia)
    // Jeśli is_shop=1: dodatkowe pole shop_inventory_json (textarea JSON)
    // Walidacja JSON.parse przed POST/PATCH → showToast(parseApiError(...), 'error')
}

async function saveNpc(npc_id, data) { /* POST lub PATCH */ }
async function deleteNpc(npc_id) { /* DELETE z confirm() */ }
```

> Cursor implementuje pełną treść funkcji wzorując się na `accounts.js` — powyższy szkic to tylko struktura.

### Krok 4 — `index.html`

Dodaj w sidebarze (spójnie z innymi przyciskami):
```html
<button type="button" data-section="npcs">🧙 NPC</button>
```

Dodaj panel:
```html
<div class="section-panel" data-section="npcs" style="display:none"></div>
```

Dodaj import `npcs.js` z `?v=1`:
```html
<script type="module">
  import { init as initNpcs } from './sections/npcs.js?v=1';
  // ...
</script>
```

Inkrement `?v=` dla zmodyfikowanego `index.html` — o 1 od aktualnego max (`v=33`).

Pokaż diff `index.html` przed zapisem.

### Krok 5 — Testy

```python
# backend/tests/test_phase9a_npc_api.py

def test_list_npcs_returns_seeded_records(client)
def test_get_npc_by_id(client)
def test_get_npc_not_found_returns_404(client)
def test_create_npc(client)
def test_create_npc_duplicate_key_returns_409(client)
def test_create_npc_with_location_keys(client)   # POST → wpis w npc_locations
def test_patch_npc_label(client)
def test_patch_npc_invalid_json_returns_400(client)
def test_patch_npc_location_keys_replace(client) # PATCH [] → usuń lokacje
def test_delete_npc_cascades_locations(client)   # DELETE → npc_locations usunięte
```

### Krok 6 — Weryfikacja manualna na DEV

```bash
cd /home/piotrszmidt/ai-gm
docker compose -f docker-compose.dev.yml up -d --build --remove-orphans
curl -sf http://localhost:8100/api/healthz && echo "DEV OK"

# Lista NPC
curl -s http://localhost:8100/api/npcs | jq '.data[] | {key, npc_type, is_shop, location_keys}'

# Utwórz testowego NPC z lokacją
curl -X POST http://localhost:8100/api/npcs \
  -H "Content-Type: application/json" \
  -d '{"key":"test_npc","label":"Test","npc_type":"neutral","location_keys":["village_square"]}'

# Sprawdź npc_locations
sqlite3 data/ai_gm.db \
  "SELECT n.key, nl.location_key FROM npcs n LEFT JOIN npc_locations nl ON nl.npc_id = n.id;"

# Testy
docker compose -f docker-compose.dev.yml exec -T backend python3 -m pytest \
  tests/test_phase9a_npc_api.py -v

# Sprawdź panel admina w przeglądarce
# https://aigm-dev.studio-colorbox.com/panel/ → sidebar powinien mieć przycisk NPC
```

---

## Odpowiedzi Cursora (REV 1)

1. **Branch:** `phase-9a-1-npc-schema`
2. **Working tree:** nie czysty — uncommitted zmiany z 9A-1 (`migrations_admin.py` + `test_phase9a_npc_schema.py`)
3. **`backend/app/api/`:** `auth.py`, `campaigns.py`, `characters.py`, `combat.py`, `health.py`, `inventory.py`, `mechanics.py`, `turns.py` i inne; `npcs.py` nie istnieje
4. **`include_router` wzorzec:** `app.include_router(turns.router, prefix="/api")`
5. **Wzorzec routera:** `health.py` — `APIRouter()`, endpoint GET, dict response, lokalna obsługa wyjątków
6. **Panel admina:** `<button type="button" data-section="...">` + `<div class="section-panel" data-section="...">`; sekcje: `game-design`, `accounts`, `technical`, `config`, `ui-settings`, `test-runner`
7. **Wzorzec JS:** `accounts.js` — `export async function init(container)`, `adminFetch`, `showToast(parseApiError(...), 'error')`
8. **`npcs.js`:** nie istnieje
9. **Cache `?v=`:** max dynamiczna sekcja = `v=32` (game_design.js)

**Blokery:** brak.

---

## Co zostało zrobione *(uzupełnia Cursor)*

- Dodano backend API CRUD NPC: `backend/app/api/npcs.py`
  - `GET /api/npcs` (z `active_only`),
  - `GET /api/npcs/{npc_id}`,
  - `POST /api/npcs`,
  - `PATCH /api/npcs/{npc_id}`,
  - `DELETE /api/npcs/{npc_id}`.
- Zaimplementowano walidację:
  - `npc_type` (neutral/merchant/quest_giver/ally),
  - JSON dla `personality_json` i `shop_inventory_json` (`HTTP 400`),
  - konflikt klucza NPC (`HTTP 409`).
- Dodano obsługę relacji `npc_locations`:
  - helper replace (`DELETE + INSERT OR IGNORE`) dla `location_keys`,
  - `location_keys` zwracane w odpowiedziach listy/detalu,
  - przy `DELETE` NPC usuwane są też wpisy `npc_locations`.
- Podpięto router w `backend/app/main.py` (`app.include_router(npcs.router, prefix="/api")`).
- Dodano sekcję Admin UI: `frontend/admin_panel/sections/npcs.js`
  - tabela: ID/Key/Label/Typ/Lokacje/Sklep/Aktywny/Akcje,
  - modal formularza create/edit (JSON textarea + walidacja po stronie UI),
  - delete z confirm,
  - integracja przez `adminFetch` + `showToast(parseApiError(...))`.
- Zintegrowano UI w `frontend/admin_panel/index.html`:
  - nowy przycisk sidebar `🧙 NPC`,
  - nowy panel sekcji `data-section="npcs"`,
  - lazy import `sections/npcs.js?v=1`.
- Dodano testy backendowe: `backend/tests/test_phase9a_npc_api.py` (10 testów)
  - lista/odczyt/404/create/duplicate/create+locations/patch/invalid-json/replace-locations/delete-cascade.
- Weryfikacja:
  - `docker compose -f docker-compose.dev.yml up -d --build --remove-orphans`,
  - `curl -sf http://localhost:8100/api/healthz` -> `{"status":"ok"}`,
  - `pytest tests/test_phase9a_npc_api.py -v` -> **10 passed**.

---

## Notatki po implementacji *(uzupełnia Perplexity)*

*(Perplexity uzupełni po raporcie Cursora)*
