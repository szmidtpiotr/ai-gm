<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-30 -->

# PROMPT 2 — Frontend: Autocomplete `/admin` w czacie gry

> **STATUS: DONE ✅ — zaimplementowane 2026-04-30**

---

## Odpowiedzi na pytania blokujące — potwierdzone z kodu

1. Input czatu: `document.getElementById('input')` / `window.getEls().inputEl`
2. Źródło tekstu: `let text = (inputEl.value || "").trim()` w `actions.js`
3. Intercept `/`: `window.slashRegistryKeyForChatClient(...)` — brak `/admin`
4. System-message: `window.addMessage({ speaker: '🛠 Admin', text, role: 'system' })`
5. `admin_commands_tree.js`: utworzony w ramach fazy
6. Błąd/brak tokenu: system-message (bez toastu)
7. Import ES module: bez versioning przy dynamicznym imporcie z `actions.js`
8. `window.API_BASE_URL`: dostępny, fallback `/api`
9. Token: `localStorage.getItem('aigm_admin_token')`
10. CSS `role: 'system'`: gotowy w UI

---

## Zgodność z Phase 8H

- Dla **`/admin add weapon …`** oraz **`/admin add consumable …`** parser zwraca `{ cmd: "add item", key, kind }` zamiast sztucznego prefiksu w polu `key` — backend sam mapuje klucz na **`weapon_key`** lub **`item_key`** (katalog consumable w `game_config_items`).
- Hint „consumable_key” w UI jest historyczny; semantycznie chodzi o **klucz rekordu consumable w `game_config_items`** (często ten sam co przed migracją z `game_config_consumables`).

---

## Co zostało zrobione *(Cursor, 2026-04-30)*

- **Nowy plik:** `frontend/js/admin_commands_tree.js`
  - `ADMIN_CMD_TREE`, `ADMIN_CMD_HINTS`, `getAdminSuggestions()`, `parseAdminCommand()`
- **Zmieniony:** `frontend/js/slash_commands.js`
  - import `getAdminSuggestions`
  - obsługa autocomplete `/admin ...` tylko gdy `playerIsAdmin === true`
- **Zmieniony:** `frontend/js/actions.js`
  - intercept `/admin` na początku `window.sendMessage`
  - dynamiczny import parsera, walidacja `selectedCharacterId` i `aigm_admin_token`
  - `POST ${API_BASE_URL}/admin/cheat/{charId}` z pełnym JSON body (w tym **`kind`** dla weapon/consumable), wynik jako `role: 'system'`
  - komenda nie idzie do LLM
- **Lint:** brak błędów
- **Rebuild:** nie wymagany (pliki statyczne, wystarczy hard-refresh)

---

## Notatki po implementacji *(Perplexity)*

- Architektura czysta: drzewo/parser oddzielone od UI i sendMessage.
- Dynamiczny import `admin_commands_tree.js` w `actions.js` — wyładowywany tylko gdy admin wpisze `/admin`, zero kosztu dla zwykłych graczy.
- **Następny krok:** PROMPT 3 — Zakładka panelu admin (REV 2, gotowy do implementacji).
