<!-- STATUS: DONE -->
<!-- PHASE: 8G | DATE_START: 2026-04-30 | DATE_END: 2026-04-30 -->

# Phase 8G — Admin Debug Commands · Brief

> Cel: umożliwić użytkownikowi z rolą ADMIN wpisywanie komend `/admin ...` bezpośrednio
> w czacie gry oraz zarządzanie nimi z poziomu panelu adminowego (nowa zakładka).
> Implementacja została wykonana w 4 promptach: backend (API `/admin/cheat`),
> frontend autocomplete w czacie, zakładka panelu admin oraz hotfix `add weapon`/`add consumable`.

---

## 1. Cel fazy

Admin może podczas testów wydawać komendy debugowe wpisując `/admin <akcja>` w oknie czatu gry.
Komendy są przechwytywane po stronie frontendu (zanim trafią do LLM), wysyłane do
dedykowanego endpointu backendowego i wykonywane bezpośrednio na DB.
Panel adminowy (zakładka **Admin Commands**) pozwala śledzić historię wykonanych komend
i podgląd aktualnego stanu postaci.

**Definicja ukończenia (DoD):**
- [x] `POST /api/admin/cheat/{character_id}` działa dla wszystkich komend z listy
- [x] Frontend: wpisanie `/admin ` w czacie gracza pokazuje drzewo podpowiedzi
- [x] Frontend: nowa zakładka **🛠 Admin Cmd** w panelu adminowym
- [x] Zakładka zawiera: selektor postaci, terminal komend z historią, skróty (quick-action buttons)
- [x] Komenda wysłana z panelu daje taki sam efekt jak z czatu gry
- [x] Endpoint dostępny tylko z `require_admin_token`
- [x] healthcheck DEV OK po deployu
- [x] test manualny: `/admin add gold 100` dodaje 100 GP do postaci

---

## 2. Zakres

| # | Komponent | Opis | Priorytet |
|---|---|---|---|
| 1 | Backend `/admin/cheat` | Nowy router `admin_cheat.py`, parser komend, SQL updates | 🔴 Must |
| 2 | Frontend autocomplete | Drzewo podpowiedzi w czacie gry po wpisaniu `/admin` | 🔴 Must |
| 3 | Panel — zakładka Admin Cmd | Nowy `sections/admin_commands.js` + wpis w `index.html` | 🔴 Must |
| 4 | Historia komend w panelu | Log ostatnich N wykonanych komend (in-memory lub localStorage) | 🟡 Should |
| 5 | Quick-action buttons | Przyciski: Full Heal, +100 GP, Clear Inventory, End Combat | 🟡 Should |
| 6 | Podgląd stanu postaci | Karta z HP/GP/lokacją/inventory odświeżana po komendzie | 🟢 Nice to have |

**Out of scope:**
- Persystencja historii komend w DB
- Uprawnienia per-user (wystarczy `require_admin_token`)
- Komendy modyfikujące enemy/NPC stats w trakcie walki (faza 9)

---

## 3. Zależności

| Zależność | Status | Gdzie |
|---|---|---|
| `characters.gold_gp` kolumna | ✅ | `migrations/` |
| `characters.sheet_json` (hp, stats, quests) | ✅ | `backend/app/routers/debug.py` l.54-115 |
| `character_inventory` tabela | ✅ | `backend/app/routers/debug.py` l.66-90 |
| `active_combat` tabela | ✅ | `backend/app/db/migrations/014_active_combat.sql` |
| `require_admin_token` middleware | ✅ | `backend/app/routers/admin.py` |
| `adminFetch` helper | ✅ | `frontend/admin_panel/shared/api.js` |
| Wzorzec zakładki admin | ✅ | `frontend/admin_panel/sections/config.js` |

### Zgodność z Phase 8H (Item System Unification)

Po migracji **8H** katalog konsumowalnych jest w **`game_config_items`** z `item_type = 'consumable'`; wiersze inventory trafiają do kolumny **`character_inventory.item_key`** (nie do osobnej ścieżki „consumable_key” jako katalogu). Kolumna `consumable_key` w inventory pozostaje wyłącznie jako **legacy / fallback** dla starych wierszy.

- **`POST .../cheat` dla `cmd: "add item"`** przyjmuje opcjonalne pole **`kind`**: `"weapon"` \| `"consumable"` — backend rozwiązuje klucz przez `game_config_weapons` / `game_config_items` (patrz `admin_cheat._resolve_inventory_add_key`).
- Prefiks `weapon_` / `consumable_` w tekście komendy jest **opcjonalny**; ważniejsze jest dopasowanie do katalogu w DB.
- Komenda **`remove item`** usuwa po dopasowaniu do `item_key`, `weapon_key` lub legacy `consumable_key`.

---

## 4. Reguły biznesowe

- Komendy `/admin` przechwytywane są przez frontend **zanim** wiadomość trafi do LLM
- Backend modyfikuje DB bezpośrednio (nie przez system promptu ani LLM)
- `gold_gp` → kolumna `characters.gold_gp`, **NIE** w `sheet_json`
- `current_hp` / `max_hp` / stats → w `sheet_json` jako JSON TEXT, wymagają parse → update → dump
- Wartości `current_hp` nie mogą przekraczać `max_hp`; nie mogą być < 0
- Endpoint wymaga `character_id` w URL; frontend odczytuje go z aktywnej sesji gry
- Komenda nieznana → odpowiedź 422 z listą dostępnych komend
- Komenda w panelu adminowym nie wymaga aktywnej sesji gry (wystarczy `character_id`)

---

## 5. Architektura

### Nowe pliki
```
backend/app/routers/admin_cheat.py          ← nowy router, parser, SQL
frontend/admin_panel/sections/admin_commands.js  ← nowa zakładka panelu
```

### Modyfikowane pliki
```
backend/app/main.py                          ← rejestracja router admin_cheat
frontend/admin_panel/index.html              ← nowy nav button + section panel
frontend/js/actions.js                        ← przechwycenie /admin w czacie
frontend/js/slash_commands.js                 ← autocomplete dla /admin
frontend/js/admin_commands_tree.js            ← drzewo komend + parser
```

### NIE ruszamy
```
docker-compose.yml
data/ai_gm.db
backend/app/routers/admin.py               ← nie modyfikujemy istniejącego routera
backend/prompts/system_prompt.txt
```

---

## 6. API kontrakty

### POST /api/admin/cheat/{character_id}
```
Headers: Authorization: Bearer <admin_token>
Body: { "cmd": "add gold", "value": 100 }
       { "cmd": "set health", "value": "max" }
       { "cmd": "add item", "key": "torch" }
       { "cmd": "add item", "key": "battleaxe", "kind": "weapon" }
       { "cmd": "add item", "key": "health_potion", "kind": "consumable" }
       { "cmd": "remove item", "key": "torch" }
       { "cmd": "clear inventory" }
       { "cmd": "add stat", "stat": "STR", "value": 2 }
       { "cmd": "set level", "value": 3 }
       { "cmd": "set location", "key": "Tavern" }
       { "cmd": "combat end" }
       { "cmd": "quest add", "key": "find_artifact" }
       { "cmd": "quest complete", "key": "find_artifact" }
       { "cmd": "show state" }   ← read-only, zwraca stan

Response 200: { "ok": true, "cmd": "add gold", "result": { "gold_gp": 250 } }
Response 422: { "ok": false, "error": "unknown_cmd", "available": [...] }
Response 404: { "ok": false, "error": "character_not_found" }
```

---

## 7. UI/UX — Autocomplete w czacie

Użytkownik wpisuje w polu czatu:
```
/admin                    → podpowiedź: add | set | remove | clear | combat | quest | show
/admin add                → podpowiedź: gold | health | item | weapon | consumable | stat
/admin add gold           → podpowiedź: [amount] — np. 100
/admin set health         → podpowiedź: [amount] | max
/admin set location       → podpowiedź: [location_key]
/admin add item           → podpowiedź: [item_key]
/admin add weapon …       → body: `{ "cmd": "add item", "key": "<tekst>", "kind": "weapon" }` (prefiks `weapon_` opcjonalny)
/admin add consumable …   → body: `{ "cmd": "add item", "key": "<tekst>", "kind": "consumable" }` — insert do **`item_key`** wg klucza z `game_config_items` (typ consumable), nie do `consumable_key`
```

Implementacja: `<div class="admin-autocomplete">` pojawia się nad polem input,
zawiera max 6 pozycji, klik/Tab uzupełnia input do wybranej opcji.
Drzewo komend zdefiniowane jako stały JS object w nowym pliku `frontend/js/admin_commands_tree.js`.

---

## 8. UI/UX — Zakładka Admin Commands w panelu

```
[Selektor postaci: dropdown]   [Pole: /admin add gold 100]  [▶ Wykonaj]

╔══ Quick Actions ══════════════════════════════════════╗
║  [💛 +100 GP]  [❤️ Full Heal]  [🗑 Clear Inventory]  [⚔️ End Combat]  ║
╚═══════════════════════════════════════════════════════╝

╔══ Stan postaci ════╗   ╔══ Historia komend ═══════════════╗
║  HP: 14/20         ║   ║  [14:21] add gold 100 → OK +100  ║
║  GP: 250           ║   ║  [14:20] set health max → OK      ║
║  Lokacja: Tavern   ║   ║  [14:19] add item torch → OK      ║
║  Items: 3          ║   ╚══════════════════════════════════╝
╚════════════════════╝
```

---

## 9. Testy wymagane

```python
# tests/test_admin_cheat.py
def test_add_gold(client, admin_token, character_id):
    r = client.post(f"/api/admin/cheat/{character_id}",
                    json={"cmd": "add gold", "value": 100},
                    headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["ok"] is True

def test_set_health_max(client, admin_token, character_id): ...
def test_add_item(client, admin_token, character_id): ...
def test_unknown_cmd_returns_422(client, admin_token, character_id): ...
def test_no_token_returns_403(client, character_id): ...
```

---

## 10. Weryfikacja manualna (DEV)

```bash
cd /home/piotrszmidt/ai-gm
docker compose -f docker-compose.dev.yml up -d --build --remove-orphans
curl -sf http://localhost:8100/api/healthz && echo "DEV OK"
# Test komendy:
curl -X POST http://localhost:8100/api/admin/cheat/1 \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"cmd": "add gold", "value": 100}'
```

---

## 11. Podsumowanie wdrożenia (Cursor)

- Co zrobiono:
  - Backend: dodano `backend/app/routers/admin_cheat.py`, rejestrację routera w `backend/app/main.py`, oraz testy `backend/tests/test_admin_cheat.py`.
  - Frontend (gra): dodano `frontend/js/admin_commands_tree.js`, rozszerzono `frontend/js/slash_commands.js` o autocomplete `/admin`, dodano intercept `/admin` w `frontend/js/actions.js`.
  - Frontend (admin panel): dodano zakładkę **Admin Cmd** w `frontend/admin_panel/index.html` i nową sekcję `frontend/admin_panel/sections/admin_commands.js`.
  - Hotfix: parser rozszerzony o `add weapon` i `add consumable` → ten sam `cmd: "add item"` z polem **`kind`** (`weapon` / `consumable`); backend dopasowuje klucz do katalogu (8H).
- Co nie weszło:
  - Brak.
- Odchylenia:
  - W briefie początkowo wskazano ogólnikowy plik `chat.js`; finalnie implementacja weszła do `actions.js` + `slash_commands.js` + `admin_commands_tree.js`.
- Wyniki testów:
  - `python3 -m pytest tests/test_admin_cheat.py -v` na `.61`: **14 passed**.
  - DEV healthcheck po rebuildzie backendu: `curl -sf http://localhost:8100/api/healthz` → `{"status":"ok"}`.
- Commity:
  - W trakcie fazy (sync po zakończeniu całej fazy, zgodnie z ustaleniem).

## 12. Analiza po fazie (Perplexity)

- Zgodność z briefem:
- Ryzyka:
- Kolejne kroki:
