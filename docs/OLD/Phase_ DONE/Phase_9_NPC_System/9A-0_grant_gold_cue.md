<!-- STATUS: DONE -->
<!-- REV: 2 | DATE: 2026-04-29 -->

# PROMPT 9A-0 — Grant Gold cue: `Grant Gold N`

> **Workflow:** Perplexity generuje REV 1 z pytaniami blokującymi → Cursor odpowiada → Perplexity generuje REV 2 → Cursor implementuje.
> **Branch roboczy:** `phase-9-npc-system` (nowy od `develop`) lub `feat/grant-gold-cue`
> **Plik:** `docs/Phase_9_NPC_System/9A-0_grant_gold_cue.md`
> **Zależności:** Phase 8E ✔️ (`characters.gold_gp` INTEGER), Phase 8D ✔️
> **Niezależny od Phase 9 NPC** — może być wdrożony przed 9A-1

---

## Cel

Dodanie cue `Grant Gold N` — mechanika nadawania złota postaci przez GM. Działa niezależnie od źródła (NPC quest, loot, nagroda fabularna). Analogiczne do istniejącego `Grant Item <nazwa>`.

---

## Kontekst techniczny (potwierdzony przez Cursora)

- **Format cue:** `Grant Gold N` jako **ostatnia linia** odpowiedzi GM (bez nawiasów kwadratowych — spójny z `Grant Item <nazwa>`)
- **Pliki do modyfikacji:**
  - `backend/app/api/turns.py` — dodanie `parse_grant_gold_cue()` + `strip_last_grant_gold_cue()` wzorowane na `parse_grant_item_cue` / `strip_last_grant_item_cue`
  - `backend/prompts/system_prompt.txt` — sekcja `## PRZEDMIOTY FABULARNE (GRANT ITEM)` rozszerzona o `Grant Gold N`
- **Istniejące API do użycia:**
  - `apply_character_gold_delta(character_id, delta, reason)` z `loot_service.py` — atomowa zmiana, nie schodzi poniżej 0
  - `parse_grant_item_cue` / `strip_last_grant_item_cue` w `turns.py` — wzór do powielenia
- **Czego NIE ruszać:** `docker-compose.yml` prod, `data/ai_gm.db`, logika walki, inventory, `apply_character_gold_delta`

---

## Implementacja (REV 2)

> ✅ Cursor implementuje poniższe — brak blokerów.

### Krok 0 — Branch

```bash
git checkout develop
git checkout -b feat/grant-gold-cue
git status --short
```

### Krok 1 — Parser w `turns.py`

Wzorując się dokładnie na `parse_grant_item_cue` i `strip_last_grant_item_cue`. Regex: `^Grant Gold (\d+)$` (ostatnia linia, case-insensitive).

### Krok 2 — Integracja z procesowaniem tury

W obu flow (`/turns` i `/turns/stream`): `extract_grant_cues()` obsługuje `Grant Item` i `Grant Gold` niezależnie od kolejności na końcu odpowiedzi. `apply_character_gold_delta()` z `loot_service` — bez ręcznego UPDATE.

### Krok 3 — System prompt

Sekcja `## ZŁOTO FABULARNE (GRANT GOLD)` obok `GRANT ITEM` w `system_prompt.txt`.

### Krok 4 — Testy: `backend/tests/test_grant_gold_cue.py` (9 testów)

### Krok 5 — Weryfikacja manualna na DEV

```bash
docker compose -f docker-compose.dev.yml exec -T backend python3 -m pytest tests/test_grant_gold_cue.py -v
sqlite3 data/ai_gm.db "SELECT id, name, gold_gp FROM characters ORDER BY id DESC LIMIT 3;"
docker logs ai-gm-dev-backend-1 --tail=30 | grep grant_gold_applied
```

---

## Odpowiedzi Cursora (REV 1)

1. **Branch:** `phase-8d-location-integrity`
2. **Working tree:** czysty
3. **Parser:** `parse_grant_item_cue` + `strip_last_grant_item_cue` w `turns.py`
4. **Gold:** `apply_character_gold_delta(character_id, delta, reason)` w `loot_service.py`
5. **Format system_prompt:** `Grant Item <nazwa>` jako ostatnia linia
6. **`gold_gp`:** `INTEGER`
7. **DB:** ~2.6 MB, OK

**Blokery:** brak.

---

## Co zostało zrobione *(Cursor)*

- `turns.py`: `parse_grant_gold_cue()`, `strip_last_grant_gold_cue()`, `extract_grant_cues()` (obsługa obu cue w obu flow sync+stream), `apply_grant_gold_to_character()` (`COALESCE`), log `grant_gold_applied`
- `system_prompt.txt`: sekcja `## ZŁOTO FABULARNE (GRANT GOLD)`
- `test_phase8e_gm_items.py`: 4 testy (parser, ignore 0, strip, update gold)
- `test_grant_gold_cue.py`: 9 passed (9A-0b)
- Manual DEV: gold `17 → 24`, `assistant_text` bez cue, log `grant_gold_applied` obecny

---

## Notatki po implementacji *(Perplexity)*

- **9 passed w `test_grant_gold_cue.py` + manualna weryfikacja gold `17→24`** — implementacja kompletna i działa end-to-end [cite:50].
- **`extract_grant_cues()` to dobra decyzja architektoniczna** — zamiast dwoch osobnych parserów wywoływanych sekwencyjnie, jeden aggregator obsługuje oba cue niezależnie od kolejności. Warto zachować ten wzorzec przy dodawaniu kolejnych cue (np. `Grant XP N` w przyszłości).
- **`apply_grant_gold_to_character()` z `COALESCE`** — bezpieczne gdy `gold_gp` jest NULL w starych rekordach. Warto dodać do listy znanych pułapek: nowe postacie mogą mieć `gold_gp = NULL` zamiast `0` jeśli migracja nie ustawiła `DEFAULT 0`.
- **Faile w `test_8d_admin_flags.py`** — wykryte przy regresji, ale nie są nowym problemem tej zmiany. Zapisane jako ToDo: `docs/ToDo_Later/fix_test_8d_admin_flags.md`.
- **Branch nadal `phase-8d-location-integrity`** — `Grant Gold` został wdrożony na tym branchu zamiast nowego. Przy merge do `develop` commit trafi razem z LOC-1/2/3/4. Nie jest blokerem, ale warto odnotować przy code review.
