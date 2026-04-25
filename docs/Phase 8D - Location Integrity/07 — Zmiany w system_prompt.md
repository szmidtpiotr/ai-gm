Jesteś programistą pracującym nad projektem ai-gm.
Repozytorium: github.com/szmidtpiotr/ai-gm
Branch: phase-8d-location-integrity

## ZANIM ZACZNIESZ IMPLEMENTOWAĆ

Przejrzyj istniejący kod i odpowiedz na poniższe pytania.
Jeśli którakolwiek odpowiedź wskazuje na problem — powiedz mi o tym ZANIM napiszesz
jakikolwiek kod:

1. Otwórz backend/prompts/system_prompt.txt i pokaż mi jego pełną treść.
2. Czy są sekcje które explicite definiują FORMAT odpowiedzi GM?
   Jeśli tak — zmiana na JSON wrapper może z nimi kolidować.
3. Czy obecne instrukcje Roll cue ("Roll Stealth d20" jako ostatnia linia)
   nadal działają gdy odpowiedź jest owinięta w JSON?
   Sprawdź: czy parser roll cue szuka wzorca w raw stringu czy parsuje JSON?
4. Czy są testy które sprawdzają format odpowiedzi GM i failują po zmianie na JSON?
5. Czy istnieje mechanizm wersjonowania promptu (np. hash, data)?

Jeśli nie widzisz blokerów — wprowadź poniższe zmiany.

---

## Zmiana: Dodaj sekcję FORMAT ODPOWIEDZI

Dodaj po sekcji o rzutach kością (NIE zmieniaj istniejących sekcji):

---

## FORMAT ODPOWIEDZI

Zawsze odpowiadaj w formacie JSON. Pole "narrative" zawiera pełną narrację po polsku.

Brak zmiany lokalizacji:
{"narrative": "[narracja]", "location_intent": null}

Ruch do istniejącej lokalizacji:
{
  "narrative": "[narracja]",
  "location_intent": {
    "action": "move",
    "target_label": "Nazwa lokalizacji",
    "target_key": "slug_nazwy"
  }
}

Odkrycie nowej lokalizacji:
{
  "narrative": "[narracja]",
  "location_intent": {
    "action": "create",
    "target_label": "Nazwa nowej lokalizacji",
    "parent_key": "klucz_rodzica",
    "description": "Krótki opis dla systemu"
  }
}

INSTRUKCJA BLOKADY:
Jeśli system zwróci [LOCATION_BLOCKED: powód] — nigdy nie potwierdzaj
zmiany lokalizacji. Narruj dlaczego postać nie może się tam dostać.

WAŻNE: Roll cue (np. "Roll Stealth d20") nadal emitujesz jako ostatnią linię
wewnątrz pola "narrative", tak jak dotychczas.

---

## Wymagania końcowe
- NIE zmieniaj innych sekcji promptu
- NIE dodawaj bloku KONTEKST LOKALIZACJI na stałe —
  wstrzykiwany dynamicznie przez location_context_injector.py
- Test manualny po zmianie:
  1. Otwarta scena → GM zwraca JSON z location_intent: null
  2. Gracz idzie do karczmy → location_intent z action: "move"
  3. Gracz odkrywa nowe miejsce → location_intent z action: "create"
  4. Rzut kością → Roll cue jako ostatnia linia w narrative
- python3 -m pytest → wszystkie passed