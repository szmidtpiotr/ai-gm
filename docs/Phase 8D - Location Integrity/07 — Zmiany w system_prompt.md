Jesteś programistą pracującym nad projektem ai-gm.
Repozytorium: github.com/szmidtpiotr/ai-gm
Branch: phase-8d-location-integrity

ZANIM ZACZNIESZ IMPLEMENTOWAĆ

Najpierw przejrzyj istniejący kod i odpowiedz na poniższe pytania.
Jeśli którakolwiek odpowiedź wskazuje na problem — powiedz mi o tym ZANIM napiszesz jakikolwiek kod.

1. Otwórz backend/prompts/system_prompt.txt i pokaż mi jego pełną treść.
2. Czy są sekcje, które explicite definiują FORMAT odpowiedzi GM?
   Jeśli tak — zmiana na JSON wrapper może z nimi kolidować.
3. Czy obecne instrukcje roll cue („Roll Stealth d20” jako ostatnia linia)
   nadal działają, jeśli odpowiedź jest owinięta w JSON?
   Sprawdź: czy parser roll cue szuka wzorca w raw stringu, czy parsuje JSON.
4. Czy są testy, które sprawdzają format odpowiedzi GM i failują po zmianie na JSON?
5. Czy istnieje mechanizm wersjonowania promptu (np. hash, data, marker wersji)?

Jeśli widzisz blocker — opisz go i nie zmieniaj promptu.

Jeśli nie widzisz blockerów — wprowadź zmiany minimalnie i bez ruszania innych sekcji.

ZMIANA DO WPROWADZENIA

Dodaj po sekcji o rzutach kością nową sekcję:

--- 

FORMAT ODPOWIEDZI

Zawsze odpowiadaj w formacie JSON. Pole "narrative" zawiera pełną narrację po polsku.

Brak zmiany lokalizacji:
{"narrative":"[narracja]","location_intent":null}

Ruch do istniejącej lokalizacji:
{
  "narrative":"[narracja]",
  "location_intent":{
    "action":"move",
    "target_label":"Nazwa lokalizacji",
    "target_key":"slug_nazwy"
  }
}

Odkrycie nowej lokalizacji:
{
  "narrative":"[narracja]",
  "location_intent":{
    "action":"create",
    "target_label":"Nazwa nowej lokalizacji",
    "parent_key":"klucz_rodzica",
    "description":"Krótki opis dla systemu"
  }
}

INSTRUKCJA BLOKADY:
Jeśli system zwróci [LOCATION_BLOCKED: powód] — nigdy nie potwierdzaj zmiany lokalizacji.
Narruj wyłącznie dlaczego postać nie może się tam dostać.

WAŻNE:
Roll cue (np. "Roll Stealth d20") nadal emituj jako ostatnią linię wewnątrz pola "narrative", tak jak dotychczas.

WYMAGANIA KOŃCOWE
- NIE zmieniaj innych sekcji promptu.
- NIE dodawaj stałego bloku kontekstu lokalizacji.
- Wstrzykiwanie kontekstu lokalizacji ma dalej działać dynamicznie przez location_context_injector.py.
- Po zmianie sprawdź, czy nadal przechodzą testy i czy roll cue działa.
- Jeśli JSON wrapper koliduje z parserem albo testami, zatrzymaj się i opisz blocker zamiast „naprawiać na ślepo”.