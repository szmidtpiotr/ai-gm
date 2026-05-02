<!-- STATUS: DONE -->
<!-- PHASE: 9 | DATE_START: 2026-04-29 | DATE_END: 2026-04-29 -->

# Phase 9 — NPC System · Brief

---

## 1. Cel fazy

Wdrozenie pelnego systemu NPC: model danych, CRUD admina, kontekst NPC dla LLM oraz integracja sklepu NPC z flow tury i frontendem.
Faza rozwiazuje problem "bezosobowego" swiata i odblokowuje dalsze etapy ekonomii oraz questow.

**Definicja ukonczenia (DoD):**
- [x] Istnieje tabela `npcs` z seedem startowych NPC i tabela mapowania lokacji
- [x] Dziala CRUD API NPC + sekcja NPC w panelu admina
- [x] LLM dostaje blok `[NPC CONTEXT]` z aktywnymi NPC
- [x] Dziala cue `Open Shop <npc_key>` i modal sklepu (buy/sell)
- [x] Testy backendowe fazy przechodza (`pytest`)
- [x] Healthcheck DEV OK (`/api/healthz`)
- [x] Funkcje zweryfikowane manualnie (API + UI)

---

## 2. Zakres — co weszlo w faze

| # | Komponent | Opis | Priorytet |
|---|---|---|---|
| 1 | 9A-0 Grant Gold cue | Cue `Grant Gold N` + parser/strip + integracja flow tury | 🔴 Must |
| 2 | 9A-1 NPC schema | Tabele `npcs`, `npc_locations`, seed 4 NPC | 🔴 Must |
| 3 | 9A-2 NPC API + Admin UI | Backend CRUD + sekcja `NPC` w admin panelu | 🔴 Must |
| 4 | 9A-3 NPC context | Iniekcja `[NPC CONTEXT]` do promptu LLM | 🔴 Must |
| 5 | 9A-4 NPC shop | API sklepu, parser `Open Shop`, modal buy/sell | 🔴 Must |

**Czego NIE bylo w tej fazie (Out of scope):**
- System questow oparty o stan i etapowanie dialogow
- Zaawansowana ekonomia (np. dynamiczne ceny per NPC)
- Rozbudowany system "sekretow" NPC poza aktualnym kontekstem LLM

---

## 3. Zaleznosci

| Zaleznosc | Status | Gdzie zaimplementowane |
|---|---|---|
| `characters.gold_gp` | ✅ DONE | migracje i API postaci (fazy 8E) |
| Kontekst lokacji (`game_sessions.current_location_id`) | ✅ DONE | `backend/app/services/game_engine.py` (8D + 9A-3) |
| Katalogi itemow/broni (`value_gp`) | ✅ DONE | migracje + `migrations_admin.py` |
| `Grant Item` cue jako wzorzec | ✅ DONE | `backend/app/api/turns.py` |
| Tokenizacja SSE w turze | ✅ DONE | `frontend/js/actions.js`, `backend/app/api/turns.py` |

---

## 4. Ustalone reguly biznesowe / design decisions

### Reguly ogolne
- NPC moze byc przypisany do wielu lokacji (`npc_locations`) lub byc globalny.
- `personality_json` sluzy do sterowania stylem wypowiedzi NPC; pole `secret` nie trafia do dynamicznego bloku kontekstu.
- Przypisanie lokacji NPC to wskazowka dla GM/LLM, nie twarda blokada narracyjna.
- Sklep dziala tylko dla NPC z `is_shop = 1`.

### Reguly specyficzne dla fazy

| Regula | Wartosc / decyzja | Uzasadnienie |
|---|---|---|
| Model lokacji NPC | Osobna tabela `npc_locations` | Relacyjne, wydajne filtrowanie po lokacji |
| Cue zlota | `Grant Gold N` jako cue koncowe | Spojnosc z `Grant Item` i prosty parser |
| Cue sklepu | `Open Shop <npc_key>` + token `[OPEN_SHOP]` | Stabilna integracja backend-frontend |
| Bezpieczenstwo starej bazy | Fail-open przy brakujacym schemacie NPC | Brak crasha na starszych DB |
| JSON pola NPC | Walidacja + HTTP 400 przy bledzie | Przewidywalny kontrakt API |

---

## 5. Architektura — pliki stworzone / zmodyfikowane

### Nowe pliki
```
backend/app/api/npcs.py
backend/app/api/shop.py
backend/app/services/shop_service.py
backend/tests/test_phase9a_npc_schema.py
backend/tests/test_phase9a_npc_api.py
backend/tests/test_phase9a_npc_context.py
backend/tests/test_phase9a_shop.py
backend/tests/test_grant_gold_cue.py
frontend/admin_panel/sections/npcs.js
frontend/js/shop.js
```

### Modyfikowane pliki
```
backend/app/migrations_admin.py
backend/app/main.py
backend/app/api/turns.py
backend/app/services/game_engine.py
backend/prompts/system_prompt.txt
frontend/admin_panel/index.html
frontend/index.html
frontend/js/actions.js
frontend/styles.css
```

### ⛔ NIE ruszano
```
docker-compose.yml (PROD)
data/ai_gm.db (produkcyjna baza)
```

---

## 6. API — kontrakty endpointow wdrozone w fazie

```
GET  /api/npcs
GET  /api/npcs/{npc_id}
POST /api/npcs
PATCH /api/npcs/{npc_id}
DELETE /api/npcs/{npc_id}
  response: { ok: true, data: ... } / { ok: true, id: ... }
  errors:   400 (invalid JSON), 404 (not found), 409 (duplicate key)

GET  /api/shop/{npc_id}?character_id=N
GET  /api/shop/by-key/{npc_key}?character_id=N
POST /api/shop/{npc_id}/buy
POST /api/shop/{npc_id}/sell
  errors: 402 (brak GP), 404 (NPC/item/inventory not found), 400 (item bez ceny)
```

---

## 7. UI / UX — co widzi uzytkownik

```
Admin Panel:
- nowa sekcja "NPC" (lista + create/edit/delete)
- formularz NPC z walidacja JSON i przypisaniem lokacji

Gra:
- po cue "Open Shop <npc_key>" frontend odbiera token [OPEN_SHOP]
- otwiera sie modal sklepu z:
  - lista itemow NPC i cenami
  - gold postaci
  - akcje Kup/Sprzedaj
- cue jest usuwany z narracji wyswietlanej graczowi
```

---

## 8. Testy — wykonane

```python
# NPC schema
backend/tests/test_phase9a_npc_schema.py   # 8 passed

# NPC API
backend/tests/test_phase9a_npc_api.py      # 10 passed

# NPC context
backend/tests/test_phase9a_npc_context.py  # 6 passed

# NPC shop
backend/tests/test_phase9a_shop.py         # 5 passed

# Grant Gold cue
backend/tests/test_grant_gold_cue.py       # 9 passed
```

---

## 9. Weryfikacja manualna (DEV)

```bash
cd /home/piotrszmidt/ai-gm
docker compose -f docker-compose.dev.yml up -d --build --remove-orphans
curl -sf http://localhost:8100/api/healthz && echo "DEV OK"

# API NPC
curl -s http://localhost:8100/api/npcs | jq .

# API shop
curl -s "http://localhost:8100/api/shop/by-key/merchant_aldric?character_id=1" | jq .

# Smoke test cue
# tura z "Open Shop <npc_key>" -> modal otwiera sie, cue znika z finalnej narracji
```

---

## 10. Prompt dla Perplexity

Nie dotyczy — faza zakonczona i podsumowana po wdrozeniu.

---

## Podsumowanie wdrozenia *(Cursor)*

### Co zostalo zaimplementowane
- [x] `Grant Gold N` (sync + stream), parser/strip + integracja z update `gold_gp`
- [x] Schemat NPC: `npcs` + `npc_locations` + seed 4 NPC
- [x] CRUD NPC API i panel admina `NPC`
- [x] Iniekcja `[NPC CONTEXT]` do kontekstu LLM
- [x] Sklep NPC: endpointy buy/sell/list, parser `Open Shop`, token `[OPEN_SHOP]`, modal UI

### Co NIE zostalo zaimplementowane (jesli dotyczy)
- Pelny system quest-state NPC (przeniesione do kolejnych faz)
- Rozszerzone testy sklepu do poziomu 10 scenariuszy (aktualnie core coverage)

### Odchylenia od Briefu
- Zamiast `dialogue_json` finalnie utrzymano model oparty o `personality_json` + runtime context.
- Dodano endpoint pomocniczy `GET /api/shop/by-key/{npc_key}` dla prostszej integracji frontendu.
- `Grant Gold` wdrozono jako niezalezny task 9A-0/0b, ale wlaczono do podsumowania fazy 9.

### Wyniki testow
```
test_phase9a_npc_schema.py  -> 8 passed
test_phase9a_npc_api.py     -> 10 passed
test_phase9a_npc_context.py -> 6 passed
test_phase9a_shop.py        -> 5 passed
test_grant_gold_cue.py      -> 9 passed
```

### Wyniki weryfikacji manualnej
```
- DEV stack uruchomiony i healthcheck OK
- Potwierdzone dzialanie CRUD NPC w API i panelu admina
- Potwierdzone `npc_context_injected` w turze
- Potwierdzone dzialanie `Open Shop` + modal buy/sell
- Potwierdzone przyrosty `gold_gp` po cue `Grant Gold N`
```

### Hash commitow
```bash
phase-9a-1-npc-schema -> [zobacz git log] -- implementacja 9A-1/2/3/4
phase-8d-location-integrity -> [zobacz git log] -- implementacja 9A-0/0b
```

---

## Analiza po fazie *(Perplexity)*

### Ocena implementacji
- **Zgodnosc z Briefem:** ✅ pelna (z drobnymi odchyleniami technicznymi opisanymi wyzej)
- **Pokrycie testami:** 38 testow fazowych zaliczonych
- **Ryzyka i dlug techniczny:** warto domknac dodatkowe edge-case testy sklepu oraz uporzadkowac starsze flaky z 8D

### Decyzje do przeniesienia do nastepnej fazy
- Utrzymac `npc_locations` jako docelowy model relacyjny.
- Kontynuowac wzorzec cue parserow agregowanych (`extract_grant_cues`) dla przyszlych cue (np. XP).
- Rozwazyc rozszerzenie ekonomii o dynamiczne modyfikatory i reakcje NPC na reputacje gracza.

### STATUS: DONE — `DATE_END: 2026-04-29`
