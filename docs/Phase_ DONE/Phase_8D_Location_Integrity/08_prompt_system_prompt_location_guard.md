<!-- STATUS: PENDING -->
<!-- REV: 1 | DATE: 2026-04-29 -->

# PROMPT 08 — System Prompt: Blokada teleportacji gracza

> Workflow: Perplexity generuje REV 1 z pytaniami blokującymi → Cursor odpowiada → Perplexity generuje REV 2 → Cursor implementuje.

---

## Cel

GM aktualnie akceptuje deklaracje gracza w stylu `"jestem na plaży"` jako fakt i natychmiast generuje narrację w nowej lokacji + emituje `location_intent: move`. To prowadzi do nielogicznych teleportacji (np. gracz był w mieście → napisał "jestem na plaży" → GM teleportuje).

Zadanie: rozszerzyć sekcję `## LOKALIZACJE I PRZEMIESZCZANIE` w `backend/prompts/system_prompt.txt` o regułę blokującą samodzielne deklaracje lokacji gracza.

**Obserwacja z logów (kampania 1064, tura 4):**
- Tura 3: gracz idzie do miasta → `location_intent: move → "miasto"` ✅
- Tura 4: gracz pisze `"jestem na plaży"` → GM akceptuje, generuje narrację na plaży, emituje `location_intent: move → "plaza"` ❌

---

## Kontekst techniczny

- **Plik do edycji:** `backend/prompts/system_prompt.txt` — jedyne źródło prawdy dla GM
- **Sekcja docelowa:** `## LOKALIZACJE I PRZEMIESZCZANIE` (już istnieje, dodana w `07_system_prompt_changes.md`)
- **NIE ruszać:** żadnych innych sekcji system promptu, backendu, DB, docker-compose
- **Branch:** `phase-8d-location-integrity`
- **Zależność:** wymaga żeby zmiany z `07_system_prompt_changes.md` były już wdrożone (sekcja LOKALIZACJE musi istnieć)

---

## ⛔ PRZED IMPLEMENTACJĄ — pytania blokujące

Nie implementuj niczego. Odpowiedz tylko na poniższe pytania:

1. Na jakim branchu jesteś? (`git branch --show-current`)
2. Czy są niezacommitowane zmiany? (`git status --short`)
3. Czy sekcja `## LOKALIZACJE I PRZEMIESZCZANIE` już istnieje w `backend/prompts/system_prompt.txt`? (`grep -n "LOKALIZACJE" backend/prompts/system_prompt.txt`)
4. Czy w sekcji LOKALIZACJE istnieje już jakiś podpunkt `### BLOKADA RUCHU`? (`grep -n "BLOKADA" backend/prompts/system_prompt.txt`)
5. Pokaż mi aktualne pełne brzmienie sekcji `## LOKALIZACJE I PRZEMIESZCZANIE` (od nagłówka do następnego `##`)

---

## Implementacja (REV 1 — szkic, NIE wykonuj)

Po otrzymaniu odpowiedzi na pytania blokujące, Perplexity wygeneruje REV 2 z dokładnym diff do wklejenia.

Planowana zmiana to dodanie podsekcji `### ZASADA — RUCH INICJOWANY PRZEZ GRACZA` do sekcji `## LOKALIZACJE I PRZEMIESZCZANIE`, z treścią:

```
### ZASADA — RUCH INICJOWANY PRZEZ GRACZA

Gracz przemieszcza się TYLKO przez akcję ruchu ("idę do X", "wchodzę do X", "wracam do X").

Jeśli gracz deklaruje stan lokacji zamiast akcji ("jestem na plaży", "znajduję się w zamku"),
GM NIE akceptuje tego jako faktu i NIE emituje location_intent.
Zamiast tego:
- Narruj że postać jest nadal w poprzedniej lokacji
- Możesz zasugerować jak gracz mógłby się tam dostać
- Ustaw location_intent: null

Przykład błędnego inputu gracza: "jestem na plaży"
Poprawna reakcja GM:
{
  "narrative": "Jesteś wciąż w [poprzednia lokacja]. Plaża jest [odległość/kierunek] — czy chcesz tam ruszyć?",
  "location_intent": null
}
```

---

## Odpowiedzi Cursora (REV 1)

*(wklej tutaj odpowiedzi Cursora na pytania blokujące)*

---

## Co zostało zrobione *(uzupełnia Cursor po implementacji)*

*(wklej raport Cursora)*

---

## Notatki po implementacji *(uzupełnia Perplexity)*

*(uzupełniane po wdrożeniu)*
