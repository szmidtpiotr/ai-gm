<!-- STATUS: PENDING -->
<!-- REV: 1 | DATE: 2026-04-29 -->
<!-- NOTE: Odlożone z Phase 8D — do rozważenia jako Phase 8G (po 8F ekonomia) -->

# PROMPT — 8D-LOC-4: Guard kontekstowy — loot/interakcje zależne od lokacji

> **Workflow:** Perplexity generuje REV 1 z pytaniami blokującymi → Cursor odpowiada → Perplexity generuje REV 2 → Cursor implementuje.
> **Branch roboczy:** Wymaga nowego brancha (np. `phase-8g-loot-location-guard`) — do ustalenia.
> **Plik:** `docs/ToDo_Later/8D-LOC4_loot_location_guard.md`
> **Zależności:**
> - Phase 8D w całości (LOC-1, LOC-2, LOC-3) — musi być wdrożona
> - Phase 8F (ekonomia, gold flow) — odliczone do wykonania wcześniej

---

## Uzasadnienie odroczenia

To najbardziej kosztowna faza z całego planu 8D:
- Wymaga nowej kolumny DB (`last_interaction_location_id` lub podobnej)
- Dotyka logiki walki i lootu — ryzyko regresi
- Blokuje przejście do 8F (ekonomia), która jest wyższym priorytetem
- Eliminuje exploit który nie jest krytyczny dla podstawowego gameplay loop

---

## Cel

Backend śledzi `last_interaction_location` dla obiektów (np. ciało wroga po walce):
- Ponowne `[Gracz przeszukuje: X]` możliwe tylko jeśli `current_location_id == lokacja gdzie X się znajdował`
- Jeśli gracz zmienił lokację — backend zwraca informację do GM że obiekt jest niedostępny

**Efekt:** Eliminuje exploit "przeszukaj wroga z innego miejsca".

---

## Kontekst techniczny

- **Pliki do modyfikacji:**
  - `backend/app/api/turns.py`
  - `backend/app/services/location_validator.py`
  - Prawdopodobnie nowa migracja DB — nowa kolumna w `game_locations` lub `active_combat`
- **Czego NIE ruszać:**
  - `docker-compose.yml` prod
  - `data/ai_gm.db` (bez migracji)
  - Logiki walki która działa poprawnie

---

## ⛔ PRZED IMPLEMENTACJĄ — pytania blokujące

1. Jaki jest aktualny branch? (`git branch --show-current`)
2. Czy working tree jest czysty? (`git status --short`)
3. Jak aktualnie przechowywany jest stan lootu po walce? Czy `active_combat` ma kolumnę dla lokalizacji starcia?
4. Jak wygląda flow `[Gracz przeszukuje: X]` w `turns.py` — czy jest to keyword matching, pars LLM, czy coś innego?
5. Czy istnieje mechanizm śledzenia "co gracz może robić w aktualnej lokacji"?
6. Ile aktywnych kampanii może mieć jednocześnie otwarte interakcje z obiektami? (skala problemu)
7. Czy baza danych jest w dobrym stanie? (`ls -lh data/ai_gm.db`)
8. Czy Phase 8F (ekonomia) jest już zamknięta?

---

## Implementacja (REV 1 — szkic do zatwierdzenia przez Perplexity)

> ⚠️ Cursor **NIE implementuje** poniższego zanim Perplexity nie zatwierdzi po odpowiedziach blokujących.

### Krok 1 — Migracja DB

Nowa migracja (np. `migrations/XXX_loot_location.sql`):

```sql
-- Przechowuje lokację gdzie postać zabiła wroga / wejdzie w interakcję z obiektem
ALTER TABLE active_combat ADD COLUMN combat_location_id INTEGER REFERENCES game_locations(id);
```

> Jeśli loot nie jest w `active_combat` — do ustalenia na etapie REV 2 po odpowiedziach blokujących.

### Krok 2 — Zapis lokacji przy starcie walki

W `turns.py`, gdy backend wykrywa start walki (`active_combat` insert):

```python
db.execute(
    "UPDATE active_combat SET combat_location_id = ? WHERE campaign_id = ?",
    (current_location_id, campaign_id)
)
```

### Krok 3 — Guard przy "przeszukiwaniu"

When gracz próbuje przeszukać obiekt z walki:

```python
if current_location_id != combat_row["combat_location_id"]:
    # Gracz odszedł z miejsca walki
    context_note = "[SYSTEM: Gracz opuścił lokację walki. Obiekt jest niedostępny.]"
    # Doklejamy do kontekstu GM — nie blokujemy tury, GM decyduje narracyjnie
    messages.insert(1, {"role": "system", "content": context_note})
```

### Krok 4 — Logi

| Event | Kiedy |
|---|---|
| `loot_location_guard_triggered` | gracz próbuje przeszukać poza lokacją walki |
| `loot_location_guard_pass` | gracz w tej samej lokacji co walka |

### Krok 5 — Weryfikacja manualna na DEV

```bash
# 1. Rozegraj walkę w lokacji A
# 2. Przejdź do lokacji B
# 3. Spróbuj przeszukać ciało wroga z lokacji A
# 4. GM powinien narracyjnie odmówić lub zasugerować powrót
docker logs ai-gm-dev-backend-1 --tail=50 | grep loot_location_guard
```

---

## Odpowiedzi Cursora (REV 1)

*(Cursor uzupełnia po przejrzeniu pytań blokujących — NIE implementuje)*

---

## Co zostało zrobione *(uzupełnia Cursor)*

*(Cursor uzupełnia po implementacji REV 2)*

---

## Notatki po implementacji *(uzupełnia Perplexity)*

*(Perplexity uzupełni po raporcie Cursora)*
