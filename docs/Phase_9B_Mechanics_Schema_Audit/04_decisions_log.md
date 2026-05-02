# Log uchwał (decisions log)

**Zasada:** jedna sekcja na uchwałę. Po spotkaniu dopisz datę i uczestników (opcjonalnie). Nie usuwaj starych wpisów — tylko dopisuj nowe, jeśli decyzja się zmienia, z odniesieniem do poprzedniej.

---

## Szablon wpisu

```markdown
### [SKRÓT] Tytuł uchwały — YYYY-MM-DD

**Status:** proposed | accepted | superseded

**Kontekst:** …

**Uchwała:** …

**Konsekwencje dla schematu / API / dokumentacji gracza:** …

**Powiązane pliki / tabele:** …
```

---

### [PROC] Tryb pracy dyskusji — 2026-05-02

**Status:** accepted

**Kontekst:** Ustalenia co do sposobu prowadzenia audytu z udziałem człowieka.

**Uchwała:** Przechodzimy tematy **punkt po punkcie** wg [`03_discussion_agenda.md`](03_discussion_agenda.md); uczestnik odpowiada i zadaje pytania; asystent stawia pytania pomocnicze i przedstawia **sugestie** wyraźnie je oznaczając. Wszystkie wiążące ustalenia dokumentujemy w `04_decisions_log.md`; definicje słownikowe w [`00_brief.md`](00_brief.md); macierz kodu w [`02_code_usage_matrix.md`](02_code_usage_matrix.md); outline gracza zgodnie z uchwałami w [`player_rulebook/00_outline_and_tone.md`](player_rulebook/00_outline_and_tone.md).

**Konsekwencje:** Brak zmian w kodzie w ramach samego trybu — tylko dyscyplina dokumentacji.

**Powiązane pliki:** [`00_brief.md`](00_brief.md) (sekcja „Tryb pracy zespołowej”)

---

### [S0] Definicja „używane w grze” dla `game_config_*` — 2026-05-02

**Status:** accepted

**Kontekst:** Sesja 0 — ustalenie słownika przed audytem kolumn.

**Uchwała:** `game_config_*` jest **używane w grze**, gdy służy **twardym zasadom mechaniki** albo **dostarcza LLM twardych danych** (żeby nie halucynował). Np. miecz przyznawany ze sklepu, z questu lub z łupu musi opierać się na rekordzie w bazie z konkretnymi statystykami / kluczem, a nie na wolnym opisie bez powiązania z katalogiem.

**Konsekwencje dla schematu / API / dokumentacji gracza:** Macierz [`02_code_usage_matrix.md`](02_code_usage_matrix.md) powinna dla każdej kolumny dać się zmapować na „mechanika / twardy kontekst LLM / ani jedno ani drugie (kandydat do uporządkowania)”. Tekst dla gracza opisuje **skutki** uchwalonych zasad, nie zachowanie modelu bez kotwicy w bazie.

**Powiązane pliki / tabele:** [`00_brief.md`](00_brief.md) (sekcja definicji); wszystkie `game_config_*`.

---

## Wpis startowy — brak uchwał (stan początkowy)

### [INIT] Rozpoczęcie fazy 9B — 2026-05-01

**Status:** accepted

**Kontekst:** Faza audytu rozpoczęta; dokumentacja w [`00_brief.md`](00_brief.md) i macierz w [`02_code_usage_matrix.md`](02_code_usage_matrix.md) opisują **stan wyjściowy kodu**, nie przyszłe wymagania.

**Uchwała:** Do czasu pierwszego spotkania wg [`03_discussion_agenda.md`](03_discussion_agenda.md) **brak wiążących decyzji** dotyczących finesse, `effect_json`, synchronizacji `game_config_skills` z `dice.py` ani automatycznego wyboru DC.

**Konsekwencje:** Książka zasad w [`player_rulebook/00_outline_and_tone.md`](player_rulebook/00_outline_and_tone.md) musi **nie obiecywać** mechanik, które nie są w `04_decisions_log.md` — do czasu ich uchwalenia opisuj wyłącznie to, co wynika z macierzy („w kodzie jest / nie ma”).

**Powiązane pliki:** [`02_code_usage_matrix.md`](02_code_usage_matrix.md)

---

## Miejsce na kolejne uchwały

_(Dodawaj poniżej, najnowsza uchwała na dole lub na górze — wybierz jedną konwencję i trzymaj się jej.)_
