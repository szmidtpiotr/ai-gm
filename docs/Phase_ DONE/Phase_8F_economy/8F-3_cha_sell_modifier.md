<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-29 -->

# PROMPT 8F-3 — CHA Modifier + UX Dopieszczenie Sklepu

> **Branch:** `phase-8f-1-economy-gold-flow`
> **Zależności:** 8F-1 ✅ | 8F-2 ✅

---

## Cel

**A)** CHA modifier ceny sprzedaży w `shop_service.py`
**B)** 3 poprawki UX w `frontend/js/shop.js`

---

## Reguła CHA (ustalone)

| CHA | Sell ratio | Item 10 GP |
|---|---|---|
| 8 | 46% | 4 GP |
| 10 | 50% | 5 GP |
| 14 | 58% | 5 GP |
| 18 | 66% | 6 GP |
| 20 | 70% | 7 GP |

---

## Odpowiedzi Cursora (REV 1)

1. **Branch:** `phase-8f-1-economy-gold-flow`
2. **Niezacommitowane zmiany:** `migrations_admin.py`, `shop_service.py`, `test_phase9a_shop.py`
3. **`earned_gp` przed:** `SELL_RATIO = 0.5` (stałe 50%), `earned = floor(base_price * 0.5)`
4. **CHA w `sheet_json`:** `sheet_json.stats.CHA`
5. **Helper:** `parse_character_sheet()` w `dice.py`; w `shop_service.py` brak — dodano
6. **Gold w nagłówku:** do dodania
7. **Toast 402:** do dodania
8. **`shopClosed` event:** do dodania

---

## Co zostało zrobione *(Cursor)*

### Backend `shop_service.py`
- `_get_character_cha(character_id, conn)` — odczyt `sheet_json.stats.CHA`, fallback `10`
- `_cha_sell_ratio(cha)` — base `0.5`, krok `0.02`, clamp `0.10..0.70`
- `sell_item()` — dynamiczny `earned_gp` z CHA, min 1 GP dla `value_gp > 0`
- `sell_item()` response — rozszerzony o `sell_ratio` i `cha`
- `get_shop_inventory()` — `sell_items[*].sell_price_gp` używają CHA ratio
- `get_shop_inventory()` response — rozszerzony o `sell_ratio` i `cha`

### Frontend `frontend/js/shop.js`
- Zamknięcie modala emituje `CustomEvent('shopClosed')`
- Błąd 402 przy kupnie: toast `"Za mało złota! (brakuje N GP)"`
- Toast po sprzedaży: `"+N GP [CHA 14: 58%]"` (tag CHA gdy ratio != 50%)

### Testy
- Nowy plik: `backend/tests/test_phase8f_cha.py` (ratio, capy, min 1 GP, pola response)
- **17 passed, 1 warning** (`test_phase8f_cha.py` + `test_phase9a_shop.py`)

### Docker
- Rebuild backend + frontend wykonany: `docker compose -f docker-compose.dev.yml up -d --build backend frontend`

---

## Notatki po implementacji *(Perplexity)*

**Zgodność z Briefem:** ✅ pełna — wszystkie punkty z `00_brief.md` spełnione.

**Pokrycie testami:** 17 testów (8 CHA + 9 sklep) — dobre pokrycie logiki biznesowej.

**Ryzyka / dług techniczny:**
- `parse_character_sheet()` z `dice.py` jako źródło CHA — jeśli struktura `sheet_json` zmieni się w przyszłych fazach, `_get_character_cha()` wymaga aktualizacji
- `sell_ratio` i `cha` są teraz w response API — frontend może na tym polegac; warto zachować w kontraście

**Następne kroki:**
1. Commit na `phase-8f-1-economy-gold-flow` z opisem po polsku
2. Merge do `develop` i wdrożenie na PROD (`./scripts/promote_and_deploy_prod.sh`)
3. Przenieś folder do `docs/!Phase DONE/Phase_8F_economy/`
4. Następna faza: **Phase 8D — Location Integrity System** (jeśli nie skończona) lub **Phase 9 NPC Dialogue**

### STATUS: DONE — `DATE_END: 2026-04-29`
