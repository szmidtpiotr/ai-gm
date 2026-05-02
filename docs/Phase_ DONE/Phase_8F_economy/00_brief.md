<!-- STATUS: DONE -->
<!-- PHASE: 8F | DATE_START: 2026-04-29 | DATE_END: 2026-04-29 -->

# Phase 8F — Economy: Gold Flow + Sklep NPC · Brief

---

## 1. Cel fazy

Wprowadzenie pełnego systemu ekonomii: gracz może kupować i sprzedawać przedmioty w sklepie NPC. Gold (GP) jest wydawane przy zakupie i zarabiane przy sprzedaży. System cen jest deterministyczny (stałe `value_gp` z katalogu) z opcjonalnym modyfikatorem CHA w v2.

**Definicja ukończenia (DoD):**
- [x] Gracz może otworzyć sklep i zobaczyć dostępne przedmioty z cenami
- [x] Zakup odejmuje `gold_gp` od postaci i dodaje item do ekwipunku
- [x] Sprzedaż usuwa item z ekwipunku i dodaje `gold_gp` wg reguły ekonomii (v1: 50%, v2: CHA modifier)
- [x] Brak złota → HTTP 402 + komunikat w UI
- [x] Testy backendowe przechodzą (`pytest -q`)
- [x] Healthcheck DEV OK
- [x] Przetestowane manualnie w przeglądarce (kup + sprzedaj)

---

## 2. Zakres — co wchodzi w fazę

| # | Komponent | Opis | Priorytet |
|---|---|---|
| 1 | `shop_service.py` | Logika transakcji: buy / sell, walidacja gold, atomic update | 🔴 Must |
| 2 | API `/api/shop/` | GET inventory, POST buy, POST sell | 🔴 Must |
| 3 | UI Sklepu (frontend) | Modal sklepu z listą itemów, gold gracza, przyciskami Kup/Sprzedaj | 🔴 Must |
| 4 | Uzupełnienie `value_gp` | Seed wartości dla itemów/broni/konsumabli gdzie `value_gp = 0` | 🟡 Should |
| 5 | CHA modifier sprzedaży | Dynamiczny % sprzedaży zależny od CHA (v2, osobny prompt) | 🟢 Nice to have |

**Out of scope w tej fazie:**
- System aukcji / targowania
- Różne ceny dla różnych kupców
- Historia transakcji
- Restock sklepu po czasie

---

## 3. Zależności

| Zależność | Status | Gdzie |
|---|---|---|
| Tabela `npcs` + `is_shop` + `shop_inventory_json` | ✅ DONE | `migrations/` + `backend/app/api/npcs.py` |
| `characters.gold_gp` kolumna | ✅ DONE | migration 8E-1 |
| `GET/POST /api/characters/{id}/gold` | ✅ DONE | `backend/app/api/inventory.py` |
| `grant_loot_to_character()` | ✅ DONE | `inventory_service.py` |
| `open_shop` cue + parser w frontend | ✅ DONE | 9A-4b / 9A-4c |
| `value_gp` w katalogach | ✅ DONE | 8F-1 (seed + filtr cen 0) |

---

## 4. Ustalone reguły biznesowe / design decisions

### Reguły ogólne
- Ceny zawsze w GP (integer), bez ułamków — `floor()` przy obliczeniach
- NPC musi mieć `is_shop = 1` żeby sklep działał
- Sklep NPC to lista kluczy (`shop_inventory_json`) — join z katalogami po `key`
- Transakcje atomiczne (SQLite `BEGIN`/`COMMIT`) — brak partial state
- `gold_gp` nigdy poniżej 0

### Reguły specyficzne dla fazy

| Reguła | Wartość | Uzasadnienie |
|---|---|---|
| Procent sprzedaży (v1) | **50% value_gp** | Standard RPG; floor do int |
| Procent sprzedaży (v2) | **CHA modifier** | +2% za każdy punkt CHA względem 10, base 50%, clamp 10%..70% |
| HTTP przy braku GP | **402 Payment Required** | Semantycznie poprawny |
| Sell ratio config | `SELL_RATIO = 0.5` w `shop_service.py` | Łatwa zmiana bez deploy |
| Źródło ceny | `value_gp` z katalogu (NIE z `shop_inventory_json`) | Jedna prawda o cenie |

---

## 5. Architektura — pliki

### Nowe pliki
```
backend/app/services/shop_service.py     ← logika buy/sell
backend/app/api/shop.py                  ← FastAPI router /api/shop/
backend/tests/test_phase9a_shop.py       ← testy shop/open_shop (9A)
backend/tests/test_phase8f_cha.py        ← testy CHA modifier (8F-3)
frontend/js/shop.js                      ← UI modal sklepu
```

### Modyfikowane pliki
```
backend/app/main.py                      ← include_router(shop.router)
backend/app/migrations_admin.py          ← seedy value_gp (8F-1)
frontend/js/actions.js                   ← obsługa tokenu [OPEN_SHOP]
frontend/index.html                      ← modal + script shop.js
```

### ⛔ NIE ruszamy
```
docker-compose.yml
data/ai_gm.db
backend/app/api/npcs.py
backend/prompts/system_prompt.txt
```

---

## 6. API — kontrakty endpointów

```
GET /api/shop/{npc_id}?character_id=N
  response: { ok, data: { npc, items, sell_items, character_gold, sell_ratio, cha } }
  errors: 404 — NPC nie istnieje lub is_shop=0

POST /api/shop/{npc_id}/buy
  request:  { character_id, item_key, item_type }
  response: { ok, data: { gold_gp, item: { key, label, value_gp } } }
  errors: 402 — za mało gold | 404 — brak itemu / NPC

POST /api/shop/{npc_id}/sell
  request:  { character_id, inventory_id }
  response: { ok, data: { gold_gp, earned_gp, sell_ratio, cha, sold_item } }
  errors: 404 — inventory_id nie należy do gracza | 400 — value_gp = 0
```

---

## 7. UI / UX — modal sklepu

```
┌─────────────────────────────────────────┐
│  🏪 Sklep: Aldric, kupiec               │
│  Twój gold: 42 GP                       │
├─────────────────────────────────────────┤
│  DOSTĘPNE PRZEDMIOTY                    │
│  Miecz krótki       10 GP  [Kup]       │
│  Mikstura życia      5 GP  [Kup]       │
├─────────────────────────────────────────┤
│  TWÓJ EKWIPUNEK (sprzedaj wg CHA)       │
│  Stara zbroja    → 3 GP  [Sprzedaj]   │
├─────────────────────────────────────────┤
│                          [Zamknij]      │
└─────────────────────────────────────────┘
```

---

## 8. Testy

```python
# test_phase9a_shop.py — 9 testów (shop flow + open_shop)
# test_phase8f_cha.py  — 8 testów (CHA ratio, capy, min 1 GP, pola response)
```

---

## 9. Weryfikacja manualna (DEV)

```bash
curl -sf http://localhost:8100/api/healthz && echo "DEV OK"
curl -s "http://localhost:8100/api/shop/1?character_id=1" | jq '.data | {character_gold, sell_ratio, cha}'
docker compose -f docker-compose.dev.yml exec -T backend \
  python3 -m pytest tests/test_phase8f_cha.py tests/test_phase9a_shop.py -q
```

---

## Podsumowanie wdrożenia *(Cursor)*

### Co zostało zaimplementowane
- [x] `shop_service.py` — buy / sell z CHA modifier
- [x] `backend/app/api/shop.py` — 3 endpointy
- [x] `frontend/js/shop.js` — UI modal (gold w nagłówku, toast 402 z kwotą, `shopClosed` event, toast CHA)
- [x] Integracja `[OPEN_SHOP]` → modal w `actions.js`
- [x] Testy: `test_phase9a_shop.py` (9) + `test_phase8f_cha.py` (8) = **17 passed**

### Co NIE zostało zaimplementowane
- Aukcje, negocjacje per NPC, historia transakcji, restock — poza zakresem

### Odchylenia od Briefu
- Użyto `frontend/js/shop.js` (istniejący) zamiast nowego `shop_modal.js`
- Testy w `test_phase9a_shop.py` + `test_phase8f_cha.py` zamiast jednego `test_phase8f_shop.py`
- CHA clamp dolny 10% aktywuje się dla CHA ≤ 7 (CHA=1 daje 32% liniowo, nie 10%)

### Wyniki testów
```
17 passed, 1 warning in 1.91s
```

### Wyniki weryfikacji manualnej
```
curl -sf http://localhost:8100/api/healthz → {"status":"ok"}
```

### Hash commitów
```
Zmiany lokalne na phase-8f-1-economy-gold-flow — commit do wykonania
```

---

## Analiza po fazie *(Perplexity)*

### Ocena implementacji
- **Zgodność z Briefem:** ✅ pełna — wszystkie 5 komponentów z zakresu zrealizowane, DoD spełniony
- **Pokrycie testami:** 17 testów — dobre; pokrywa logikę CHA, capy, min 1 GP, walidację 402, pola response
- **Ryzyka i dług techniczny:**
  - `_get_character_cha()` używa `parse_character_sheet()` z `dice.py` — jeśli struktura `sheet_json` zmieni się, wymaga aktualizacji w dwóch miejscach
  - Clamp dolny CHA (10%) aktywuje się dopiero przy CHA ≤ 7, nie przy CHA = 1 — do rozważenia czy to zamierzone
  - `sell_ratio` i `cha` są teraz częścią publicznego API — breaking change gdyby usunąć

### Decyzje do przeniesienia do następnej fazy
- Ewentualne **hard-min 10%** dla każdej wartości CHA (nie tylko ≤ 7) — jeśli balance wymaga
- **Historia transakcji** (out of scope 8F) — kandydat na osobny task w Phase 9+
- **Restock sklepu po czasie** — kandydat na Phase 9 (NPC System + Dialogue)
- Przed następną fazą: **commit + merge `phase-8f-1-economy-gold-flow` → `develop`** i release na PROD

### STATUS: DONE — `DATE_END: 2026-04-29`
