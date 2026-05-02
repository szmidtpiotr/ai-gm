<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-30 -->

# PROMPT 1 — Backend: `/admin/cheat` API

> **STATUS: DONE ✅ — zaimplementowane 2026-04-30**

---

## Odpowiedzi Cursora (REV 1) — potwierdzone 2026-04-30

1. **Blokery:** brak, można implementować.
2. **Import `require_admin_token`:** `from app.routers.admin import require_admin_token`
3. **Prefix endpointu:** `app.include_router(admin_cheat_router, prefix="/api")`
4. **Zmiany DB / migracje:** w momencie pierwotnego promptu — nie były wymagane. Po **Phase 8H** warstwa `add item` musi być spójna z ujednoliconym katalogiem (`game_config_items`, `item_key` dla consumable) — patrz implementacja `_resolve_inventory_add_key` oraz pole żądania **`kind`**.
5. **Bezpieczeństwo:** obecny `require_admin_token` wystarczy (401/403).
6. **Testy:** zakres z promptu poprawny i kompletny.

---

## Zgodność z Phase 8H (aktualizacja dokumentacji)

- **`CheatRequest`** zawiera opcjonalne **`kind`**: przy `cmd == "add item"` pozwala wymusić rozstrzygnięcie **broń vs konsumowalny** zanim zadziała heurystyka prefiksów / lookup w DB.
- **Konsumowalne:** katalog w **`game_config_items`** (`item_type = 'consumable'`); zapis inventory w **`character_inventory.item_key`**. Stara tabela `game_config_consumables` może nadal istnieć jako fallback read-only w resolverze — do usunięcia osobno po weryfikacji prod.
- **`result.added`** zwraca **kanoniczny klucz** z katalogu (może różnić się od wpisanego tekstu, np. bez prefiksu lub po normalizacji).

---

## Cel

Utworzenie routera `backend/app/routers/admin_cheat.py` z `POST /api/admin/cheat/{character_id}`.

---

## Co zostało zrobione *(Cursor, 2026-04-30)*

- **Nowe pliki:** `backend/app/routers/admin_cheat.py`, `backend/tests/test_admin_cheat.py`
- **Zmodyfikowane:** `backend/app/main.py` (rejestracja routera z `prefix="/api"`)
- **Testy:** `pytest tests/test_admin_cheat.py -v` → **14 passed**
- **Rebuild DEV:** wykonany po zmianach backendu
- **Healthcheck:** `curl -sf http://localhost:8100/api/healthz` → `{"status":"ok"}`
- **Uwaga:** w repo obecne niepowiązane pliki (`voice-service/config.json`, `.ssh/`, `chatgpt.txt`, `.nfs...`) — nie ruszane.
- **Phase 8H:** logika dodawania przedmiotów zsynchronizowana z migracją itemów — bez osobnej zmiany kontraktu HTTP poza polem `kind` i zachowaniem resolvera.

---

## Notatki po implementacji *(Perplexity)*

- Endpoint działa. 14/14 testów pokrywa pełny zakres (CRUD gold/health/stats/item/quest/combat + unknown cmd + auth).
- Niepowiązane pliki w repo — do sprzątnięcia osobno, nie blokują dalszej pracy.
- Sync do develop: wykonać po ukończeniu frontendów (PROMPT 2 + 3) lub osobno jeśli chcesz zachować krok backendu.
- **Następny krok:** PROMPT 2 — Frontend autocomplete (REV 2, gotowy do implementacji).
