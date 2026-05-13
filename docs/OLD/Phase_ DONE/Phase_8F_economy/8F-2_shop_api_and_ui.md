<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-29 -->

# PROMPT 8F-2 — Shop UI Modal + Integracja `open_shop`

> **Branch:** `phase-8f-1-economy-gold-flow`
> **Zależności:** 8F-1 ✅ | `shop_service.py` ✅ | `/api/shop/` ✅

---

## Cel

Frontend modal sklepu + integracja cue `open_shop` z parsera GM.

---

## Odpowiedzi Cursora (REV 1)

1. **Branch:** `phase-8f-1-economy-gold-flow`
2. **Niezacommitowane zmiany:** tak — `migrations_admin.py`, `shop_service.py`, `test_phase9a_shop.py` — commit przed dalszymi pracami
3. **`frontend/shop_modal.js`:** nie istnieje — jest **`frontend/js/shop.js`** (IIFE + `window.openShopByNpcKey`), podpięty w `index.html`
4. **Obsługa `open_shop`:** SSE token `[OPEN_SHOP]{...json...}` w `actions.js` → `applyOpenShopSseToken` czyta `npc_key` → `pendingOpenShopNpcKey` → po końcu streamu wywołuje `window.openShopByNpcKey(npcKey, selectedCharacterId)`
5. **API sklepu:** `GET /api/shop/by-key/{npc_key}?character_id=N` — response: `{ok, data: {npc, items, sell_items, character_gold}}`
6. **Ekwipunek:** endpoint to `GET /api/inventory/{character_id}`; modal może używać `data.sell_items` z odpowiedzi sklepu
7. **Cache `?v=`:** wersjonowanie opisowe np. `shop.js?v=9a4-open-shop-fallback`
8. **CSS modala:** `frontend/styles.css` — klasy `character-modal-overlay`, `character-modal`, `character-modal-close`; `#shop-modal` przełącza `display: flex/none`

---

## Co zostało zrobione

> ⚠️ Backend + modal + integracja SSE zostały **w całości zaimplementowane w ramach Phase 9A**.
> Ten task nie wymagał osobnej implementacji — zakres 8F-2 był już pokryty.

- ✅ `frontend/js/shop.js` — IIFE z pełnym UI modala (lista towarów, ekwipunek, Kup/Sprzedaj, toasty)
- ✅ Integracja SSE `[OPEN_SHOP]` → `openShopByNpcKey()` w `actions.js`
- ✅ `GET /api/shop/by-key/{npc_key}` + `POST /api/shop/{id}/buy` + `POST /api/shop/{id}/sell`
- ✅ `sell_items` w response (osobny GET inventory nie jest wymagany)
- ✅ CSS modal zgodny z reszta panelu gry

## Ewentualne UX dopieszczenie (opcjonalne, nie blokuje 8F-3)

Jeśli chcesz wyrównać z makietą z `00_brief.md`:
- [ ] Wyświetlanie aktualnego gold gracza w nagłówku modala (jeśli brakuje)
- [ ] Toast z dokładną kwotą brakującego gold przy 402: `"Za mało złota! (brakuje N GP)"`
- [ ] `dispatch CustomEvent('shopClosed')` po zamknięciu (na wypadek odświeżenia ekwipunku w HUD)

---

## Notatki po implementacji *(Perplexity)*

**Zgodność z Briefem:** ✅ pełna — wszystkie wymagania z `00_brief.md` spełnione przez prace 9A.

**Wnioski:**
- Kolejność faz była odwrotna: Phase 9A (NPC + sklep) wyprzedziła Phase 8F (economy), przez co 8F-2 nie miało co implementować.
- Na przyszłość: Brief powinien weryfikować co już istnieje przed pisaniem promptów.

**Następny krok:** 8F-3 — CHA modifier ceny sprzedaży.

### STATUS: DONE — `DATE_END: 2026-04-29`
