Projekt ai-gm (RPG AI-GM, repo: szmidtpiotr/ai-gm).
Branch: phase-8d-location-integrity
Faza: Phase 8D — Location Integrity System

## Diagnoza z logów (Loki DEV)

Dwa blokerki uniemożliwiają działanie auto-create:

### BŁĄD 1 — location_intent_parse_error: '"moved"'
Log:
  "error": "'\"moved\"'",
  "event": "location_intent_parse_error",
  "session_id": null

GM zwraca odpowiedź w formacie:
  ```json
  { "narrative": "...", "location_intent": { "action": "move", ... } }
  ```
Hook w turns.py próbuje sparsować location_intent, ale:
  a) GM owija JSON w markdown code fence (` ```json ... ``` `) — parser dostaje surowy tekst z backtick
  b) Błąd `'"moved"'` sugeruje że action porównywane jest do stringa z cudzysłowem w środku
  c) session_id = null — mapowanie campaign_id → session nie działa

### BŁĄD 2 — JSON wyświetla się graczowi jako artefakt
Gracz widzi surowe ```json { "narrative": "...", "location_intent": {...} }```
zamiast samego tekstu narracji.

---

## Zadania do wykonania

### ZADANIE A — Napraw parser w turns.py

W funkcji `_process_location_intent()` (lub tam gdzie hook czyta location_intent):

1. **Strip markdown code fence przed parsowaniem JSON:**
```python
import re

def strip_code_fence(text: str) -> str:
    """Usuń markdown ```json ... ``` lub ``` ... ``` z odpowiedzi LLM."""
    text = text.strip()
    # usuń opening fence: ```json lub ```
    text = re.sub(r'^```(?:json)?\s*\n?', '', text, flags=re.MULTILINE)
    # usuń closing fence
    text = re.sub(r'\n?```\s*$', '', text, flags=re.MULTILINE)
    return text.strip()
```

2. **Napraw mapowanie campaign_id → session_id:**
Przed wywołaniem `validate_move()`, upewnij się że pobierasz aktywną sesję dla campaign_id:
```python
session = conn.execute(
    "SELECT id FROM game_sessions WHERE campaign_id = ? ORDER BY id DESC LIMIT 1",
    (campaign_id,)
).fetchone()
session_id = session["id"] if session else None
```
Przekaż `session_id` do walidatora.

3. **Napraw porównanie action:**
Sprawdź gdzie jest porównanie `action == "moved"` — powinno być `action == "move"`.
Przeszukaj: `grep -r "moved" backend/app/services/location_validator.py backend/app/api/turns.py`

### ZADANIE B — Napraw rendering w frontend

W miejscu gdzie renderujesz tekst GM (frontend/js/app.js lub ui.js lub odpowiednik dla stream):

```javascript
function extractNarrative(text) {
  if (!text) return text;
  // strip markdown code fence
  const stripped = text.replace(/^```(?:json)?\s*\n?/m, '').replace(/\n?```\s*$/m, '').trim();
  try {
    const parsed = JSON.parse(stripped);
    if (parsed.narrative) return parsed.narrative;
  } catch (e) {
    // nie JSON — zwróć oryginalny tekst
  }
  return text;
}
```

Wywołaj tę funkcję:
- przy renderowaniu odpowiedzi non-stream
- przy renderowaniu po zakończeniu stream (po zebraniu pełnego tekstu)
- przy ładowaniu historii tur z bazy (stare tury też mają artefakty)

### ZADANIE C — Opcjonalnie: napraw system_prompt

Dodaj do `backend/prompts/system_prompt.txt` jasne polecenie:
"Zwracaj WYŁĄCZNIE czysty JSON bez markdown code fence, bez ```json, bez ``` na początku i końcu."

---

## Przed implementacją sprawdź

1. `git branch --show-current` i `git status`
2. `grep -n "location_intent_parse_error\|parse_error\|moved" backend/app/api/turns.py backend/app/services/location_validator.py`
3. `grep -n "narrative\|parseGM\|assistant_text" frontend/js/app.js frontend/js/ui.js`
4. `grep -n "session_id\|campaign_id" backend/app/services/location_validator.py` — jak walidator przyjmuje ID

NIE ruszać: docker-compose.yml prod, data/ai_gm.db