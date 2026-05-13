<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-29 -->

# PROMPT 9A-3 — Phase 9: NPC w kontekście LLM

> **Branch:** `phase-9a-1-npc-schema` | **Zależności:** 9A-1 ✔️, 9A-2 ✔️, 9A-0 ✔️

---

## Cel

Wstrzyknąć informację o NPC obecnych w lokacji gracza do kontekstu LLM przed każdą turą.

---

## Kontekst techniczny (potwierdzony)

- **Lokacja gracza:** `game_sessions.current_location_id` → JOIN `game_locations.key`
- **Wzorzec:** `_inject_location_llm_context` w `game_engine.py`
- **Budowanie messages:** `build_narrative_messages(...)`
- **Filtrowanie:** `npc_locations` JOIN + globalni (brak wierszy)
- **`personality_json`:** `{personality, topics, secret}` — wstrzykujemy `personality` + `topics`, `secret` pomijamy
- **Czego NIE ruszano:** `docker-compose.yml` prod, `data/ai_gm.db`, logika `Grant Gold`, walka

---

## Odpowiedzi Cursora (REV 1)

1. **Branch:** `phase-9a-1-npc-schema`, working tree nieczysty (9A-1)
2. **Kontekst LLM:** `build_narrative_messages`, wzór `_inject_location_llm_context`
3. **Lokacja:** `game_sessions.current_location_id`
4. **`personality_json`:** `{personality, topics, secret}`
5. **Aktywnych NPC:** 4
6. **Sekcja NPC w system_prompt:** brak
7. **DB:** ~2.6 MB, OK

---

## Co zostało zrobione *(Cursor)*

- `backend/app/services/game_engine.py`:
  - `build_npc_context_block(conn, campaign_id)` — bierze lokację z `game_sessions.current_location_id`, filtruje NPC przez `npc_locations` + globalni, `is_active=1`, buduje blok `[NPC CONTEXT]`
  - `_inject_npc_llm_context(...)` podpięty w `build_narrative_messages(...)` obok location context
  - fail-open: `sqlite3.OperationalError` → skip (brak crasha przy brakującym schemacie)
- `backend/prompts/system_prompt.txt`: sekcja `POSTACIE NIEZALEŻNE (NPC)`
- `tests/test_phase9a_npc_context.py`: **6 passed**
- Manual: log `npc_context_injected` z `npc_count=4` podczas tury

---

## Notatki po implementacji *(Perplexity)*

- **6 passed + log `npc_context_injected npc_count=4`** — NPC są widoczni dla GM od tej tury.
- **`build_npc_context_block(conn, campaign_id)`** zamiast `(location_key)` — Cursor trafnie przeniósł odpowiedzialność pobrania lokacji do środka funkcji (trzyma `conn` z zewnątrz). Wzór spójny z `_inject_location_llm_context`. ✅
- **Fail-open przy `OperationalError`** — dobra decyzja defensywna. Oznacza że nawet na starej DB bez tabel NPC gra nie crashuje. Warto utrzymać ten wzór przy kolejnych injections.
- **`secret` pominięty w bloku** — zgodnie z projektem. GM wie o sekrecie przez system_prompt ("dawkuj wskazówki"), nie przez dynamiczny kontekst. To dobra separacja.
- **Następny krok: 9A-4** — sklep NPC (buy/sell) + cue `Open Shop <npc_key>`. Odblokowuje Phase 8F Economy.
