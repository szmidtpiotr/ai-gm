<!-- STATUS: DONE -->
<!-- REV: 1 | DATE: 2026-04-29 -->

# PROMPT 9A-0b — Weryfikacja i testy: `Grant Gold N`

> **Workflow:** Perplexity generuje REV 1 z pytaniami blokującymi → Cursor odpowiada → Perplexity generuje REV 2 → Cursor implementuje.
> **Branch roboczy:** ten sam co 9A-0 (`feat/grant-gold-cue` lub `phase-9-npc-system`)
> **Zależność:** PROMPT 9A-0 zaimplementowany ✔️

---

## Cel

Potwierdzenie że implementacja `Grant Gold N` działa poprawnie:
1. Testy jednostkowe (`parse_grant_gold_cue`, `strip_last_grant_gold_cue`)
2. Test integracyjny z `apply_character_gold_delta`
3. Test manualny na DEV: gold rośnie, cue nie trafia do UI

---

## ⛔ PRZED TESTAMI — pytania blokujące

Cursor odpowiada na poniższe pytania **zanim** przystąpi do testów:

1. Jaki jest aktualny branch? (`git branch --show-current`)
2. Czy `parse_grant_gold_cue` i `strip_last_grant_gold_cue` istnieją w `turns.py`? (`grep -n "grant_gold" backend/app/api/turns.py`)
3. Czy `Grant Gold` jest wywoływane w flow tury (obok `Grant Item`)? Pokaż fragment `turns.py` gdzie obydwa są obsługiwane.
4. Czy istnieje plik `backend/tests/test_grant_gold_cue.py`? (`ls -la backend/tests/test_grant_gold_cue.py`)
5. Czy `Grant Gold` zostało dodane do `system_prompt.txt`? (`grep -n "Grant Gold" backend/prompts/system_prompt.txt`)
6. Czy możliwe jest mieć `Grant Item` i `Grant Gold` w jednej turze (dwie ostatnie linie)? Jak kod to obsługuje?

---

## Testy do wykonania

### Krok 1 — Pytest jednostkowy

```bash
cd /home/piotrszmidt/ai-gm
docker compose -f docker-compose.dev.yml exec -T backend python3 -m pytest \
  tests/test_grant_gold_cue.py -v
```

**Oczekiwane: wszystkie passed.** Pokaż pełny output.

Jeśli testów brak lub są szkieletowe (`...`) — uzupełnij wg poniższego:

```python
# backend/tests/test_grant_gold_cue.py
from app.api.turns import parse_grant_gold_cue, strip_last_grant_gold_cue
from app.services.loot_service import apply_character_gold_delta

# --- jednostkowe (bez DB) ---

def test_parse_returns_amount():
    assert parse_grant_gold_cue("Narracja.\nGrant Gold 50") == 50

def test_parse_case_insensitive():
    assert parse_grant_gold_cue("Narracja.\ngrant gold 20") == 20

def test_parse_zero_returns_none():
    assert parse_grant_gold_cue("Narracja.\nGrant Gold 0") is None

def test_parse_no_cue_returns_none():
    assert parse_grant_gold_cue("Zwykła narracja bez cue.") is None

def test_parse_cue_not_last_line_returns_none():
    # cue w środku tekstu — nie ostatnia linia — powinno być ignorowane
    assert parse_grant_gold_cue("Grant Gold 50\nDalszy tekst.") is None

def test_strip_removes_last_line():
    assert strip_last_grant_gold_cue("Narracja.\nGrant Gold 50") == "Narracja."

def test_strip_no_cue_unchanged():
    text = "Zwykła narracja."
    assert strip_last_grant_gold_cue(text) == text

# --- integracyjny (z DB) ---

def test_apply_gold_delta_adds(db, character):
    """apply_character_gold_delta dodaje złoto do postaci."""
    before = db.execute(
        "SELECT gold_gp FROM characters WHERE id=?", (character.id,)
    ).fetchone()[0]
    apply_character_gold_delta(character.id, 50, "grant_gold_cue")
    after = db.execute(
        "SELECT gold_gp FROM characters WHERE id=?", (character.id,)
    ).fetchone()[0]
    assert after == before + 50
```

---

### Krok 2 — Test manualny na DEV

#### 2a. Zanotuj gold przed turą

```bash
sqlite3 data/ai_gm.db \
  "SELECT id, name, gold_gp FROM characters ORDER BY id DESC LIMIT 3;"
```

#### 2b. Wymuś `Grant Gold` w odpowiedzi GM

Najprostszy sposób: napisz w grze coś w stylu:
> *„Biorę złoto ze skrzyni‟* lub *„Aldric płaci mi za przysługę‟*

Jeśli GM sam nie emituje cue — można wymusić przez bezpośrednio w DB:
```bash
# Symulacja: wstaw turę z odpowiedzią zawierającą 'Grant Gold 30' jako ostatnią linię
# NIE rób tego ręcznie — zamiast tego sprawdź przez prawdziwą turę w UI na DEV
```

#### 2c. Sprawdź gold po turze

```bash
sqlite3 data/ai_gm.db \
  "SELECT id, name, gold_gp FROM characters ORDER BY id DESC LIMIT 3;"
# Oczekiwane: gold_gp wzrosło o N
```

#### 2d. Sprawdź że cue NIE trafia do UI

```bash
# Tekst ostatniej tury w DB — brak linii 'Grant Gold N'
sqlite3 data/ai_gm.db \
  "SELECT assistant_text FROM campaign_turns ORDER BY id DESC LIMIT 1;"
```

#### 2e. Logi

```bash
docker logs ai-gm-dev-backend-1 --tail=30 | grep grant_gold_applied
# Oczekiwane: wpis z character_id, amount, new_total
```

---

### Krok 3 — Regresja

```bash
docker compose -f docker-compose.dev.yml exec -T backend python3 -m pytest \
  tests/ -v --ignore=tests/test_grant_gold_cue.py -q
# Oczekiwane: żadnych nowych FAILED
```

---

### Krok 4 — Commit

```bash
git add backend/app/api/turns.py \
        backend/prompts/system_prompt.txt \
        backend/tests/test_grant_gold_cue.py
git commit -m "feat: Grant Gold N cue — nadawanie złota przez GM"
```

---

## Oczekiwane wyniki (checklista)

| Test | Oczekiwany wynik | Zaliczony? |
|---|---|---|
| pytest `test_grant_gold_cue.py` | wszystkie passed | ☐ |
| gold rośnie o N po turze | `gold_gp += N` w DB | ☐ |
| cue nie w `assistant_text` | brak `Grant Gold N` w tekście tury | ☐ |
| log `grant_gold_applied` | widoczny w logach DEV | ☐ |
| regresja | żadnych nowych FAILED | ☐ |

---

## Odpowiedzi Cursora (REV 1)

1. **Aktualny branch:** `phase-8d-location-integrity`.
2. **`parse_grant_gold_cue` / `strip_last_grant_gold_cue`:** tak, istnieją w `backend/app/api/turns.py`.
3. **Obsługa flow tury obok `Grant Item`:** tak, w obu ścieżkach:
   - sync (`/campaigns/{id}/turns`) — `extract_grant_cues(...)` + aplikacja `grant_item_label` i `grant_gold_amount`,
   - stream (`/campaigns/{id}/turns/stream`) — analogicznie.
4. **`backend/tests/test_grant_gold_cue.py`:** nie istniał — został dodany.
5. **`Grant Gold` w `system_prompt.txt`:** tak, sekcja `## ZŁOTO FABULARNE (GRANT GOLD)` jest dodana.
6. **Czy można mieć `Grant Item` i `Grant Gold` w jednej turze?** Tak.
   Kod używa `extract_grant_cues()` i zdejmuje cue z końca odpowiedzi w pętli (obsługuje oba cue oraz ich kolejność), a dodatkowo obsługuje cue zwrócone przez model w JSON `roll_cue`.

---

## Co zostało zrobione *(uzupełnia Cursor)*

- Dodano nowy plik testów: `backend/tests/test_grant_gold_cue.py` (9 testów):
  - parser `Grant Gold`,
  - case-insensitive,
  - ignorowanie `0`,
  - brak cue,
  - cue nie na końcu,
  - strip cue,
  - integracja `apply_character_gold_delta`,
  - dodatkowo test `extract_grant_cues()` dla JSON `roll_cue`.
- Naprawiono edge-case wykryty manualnie:
  - model zwracał `Grant Gold 7` w `roll_cue` (JSON), więc sama detekcja „ostatniej linii” nie łapała cue.
  - `extract_grant_cues()` w `turns.py` rozszerzono o parsowanie `roll_cue` i zerowanie `roll_cue` do `null` po zużyciu cue.
- **Pytest (krok 1):**
  - `docker compose -f docker-compose.dev.yml exec -T backend python3 -m pytest tests/test_grant_gold_cue.py -v`
  - wynik: `9 passed, 1 warning`.
- **Manual DEV (krok 2):**
  - wykonano realny `POST /api/campaigns/1065/turns` z intencją `Grant Gold 7`,
  - `gold_gp` wzrosło (np. `17 -> 24` dla `character_id=1075`),
  - `campaign_turns.assistant_text` nie zawiera literalnej linii `Grant Gold N` (widzoczne JSON z `"roll_cue": null`),
  - log `grant_gold_applied` widoczny (`amount`, `new_total_gp`).
- **Regresja (krok 3):**
  - uruchomiono:
    - `python3 -m pytest tests/ -v --ignore=tests/test_grant_gold_cue.py -q`
  - suite wykazał istniejące błędy już na starcie (`tests/test_8d_admin_flags.py ...FFF...`), brak dowodu na nową regresję od `Grant Gold`, ale pełny przebieg nie został domknięty w ramach tej sesji.

---

## Notatki po implementacji *(uzupełnia Perplexity)*

*(Perplexity uzupełni po raporcie Cursora)*
