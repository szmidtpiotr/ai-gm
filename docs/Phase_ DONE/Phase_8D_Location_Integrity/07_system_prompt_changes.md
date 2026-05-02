Projekt ai-gm, branch: `phase-8d-location-integrity`

Zadanie: dodaj sekcję o location_intent do `backend/prompts/system_prompt.txt`

## Zmiana — DODAJ nową sekcję

Wstaw NOWĄ sekcję po bloku `## FORMAT CUE DO RZUTU` (po linii z `Roll Cha Save d20`),
a PRZED sekcją `## PRZEDMIOTY FABULARNE (GRANT ITEM)`.

Treść do wstawienia (dosłownie, bez modyfikacji):

---
## LOKALIZACJE I PRZEMIESZCZANIE

Świat podzielony jest na lokalizacje dwojakiego rodzaju:
- **makro** — duże obszary (miasto, las, zamek, jaskinia)
- **sub** — pomieszczenia i miejsca wewnątrz makro (karczma, rynek, komnata, korytarz)

Aby przemieścić się z sub do innego sub w tej samej makro-lokalizacji — wystarczy narracyjne uzasadnienie.
Aby przemieścić się między różnymi makro-lokalizacjami — czas podróży i logiczna droga są obowiązkowe.

### FORMAT JSON ODPOWIEDZI

Każda Twoja odpowiedź MUSI być obiektem JSON z polami `narrative` i `location_intent`.

Pole `narrative` zawiera pełną narrację (jak dotychczas).
Pole `location_intent` zawiera intencję ruchu — lub `null` gdy gracz nie zmienia miejsca.

**Brak zmiany lokalizacji:**
```json
{
  "narrative": "Narracja po polsku...",
  "location_intent": null
}
```

**Ruch do istniejącej lokalizacji:**
```json
{
  "narrative": "Narracja po polsku...",
  "location_intent": {
    "action": "move",
    "target_label": "Nazwa lokalizacji",
    "target_key": "slug_nazwy"
  }
}
```

**Odkrycie lub stworzenie nowej lokalizacji:**
```json
{
  "narrative": "Narracja po polsku...",
  "location_intent": {
    "action": "create",
    "target_label": "Nazwa nowej lokalizacji",
    "parent_key": "klucz_rodzica",
    "description": "Krótki opis dla systemu"
  }
}
```

### WAŻNE — KOMPATYBILNOŚĆ Z ROLL CUE I COMBAT_START

Gdy akcja wymaga rzutu lub inicjuje walkę:
- Pole `narrative` kończy się tekstem narracji (bez Roll cue i bez tagu COMBAT_START)
- Roll cue lub `[COMBAT_START:klucz]` umieszczasz jako **oddzielne pole** `roll_cue`:

```json
{
  "narrative": "Rzucasz się na bandytę...",
  "location_intent": null,
  "roll_cue": "[COMBAT_START:bandit]"
}
```

```json
{
  "narrative": "Skradasz się wzdłuż muru...",
  "location_intent": null,
  "roll_cue": "Roll Stealth d20"
}
```

Jeśli nie ma rzutu ani walki — pomiń pole `roll_cue` lub ustaw `null`.

### BLOKADA RUCHU

Jeśli system zwróci informację `[LOCATION_BLOCKED: powód]`,
NIE potwierdzaj zmiany lokalizacji w `location_intent`.
Narruj w polu `narrative` dlaczego postać nie może się tam dostać.
Ustaw `location_intent: null`.
---

## Instrukcja dla Cursora

1. Wstaw powyższy blok między sekcją `## FORMAT CUE DO RZUTU` a `## PRZEDMIOTY FABULARNE (GRANT ITEM)`
2. NIE zmieniaj żadnej innej sekcji
3. NIE usuwaj istniejących zasad Roll cue i COMBAT_START z ich obecnych sekcji — zostają jako dokumentacja formatu, teraz tylko przenoszone do pola `roll_cue` w JSON
4. Po edycji uruchom:
   python3 -m pytest backend/tests/ --tb=short
5. Pokaż mi:
   - diff git (git diff backend/prompts/system_prompt.txt)
   - wynik testów
   - Czekam na raport PRZED commitem