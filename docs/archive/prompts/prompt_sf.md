# PROMPT STARTOWY — FAZA SF (Frontend FAZY S: pasek akcji + warstwa informacji zwrotnej)

Pracujemy nad **FAZĄ SF** — czysto frontendowy upgrade UX walki gracza po S20 (mechanika FAZY S jest kompletna; to wyłącznie prezentacja i czytelność). Przeczytaj najpierw:

- `CLAUDE.md` (zasady projektu i środowiska — tylko DEV `.61`, nigdy PROD),
- `game_mechanics.md` → CZĘŚĆ AI → sekcja **„FAZA SF"** (pełny opis SF1–SF7 + język wizualny z `/interface-design`),
- `notes.md` → sekcja **„FAZA SF"** (checklista — jedyne źródło statusów),
- bieżący kod paska walki: `frontend/front/index.html` (`#combat-composer`, ~782–832) + `frontend/front/js/app.js` (render walki, `COND_BADGE_MAP` ~4555).

## ZAKRES (decyzja Piotra, 2026-06-15)

- **Cel:** pasek walki upycha do 7 przycisków → zwinąć do **[Atak] · [Akcja ▾] · [Ucieczka]**; „Akcja" otwiera **bottom sheet** z resztą opcji. Plus **warstwa informacji zwrotnej** — gra ma mówić graczowi DLACZEGO coś się stało.
- **TYLKO frontend gracza** (`frontend/front/`). **ZERO zmian mechaniki i endpointów backendu** — wszystkie dane już są w combat snapshot / wyniku rzutu / katalogu `/api/mechanics/conditions`. Jeśli jakiegoś sygnału brakuje w payloadzie DLA GRACZA (np. `omen_applied`, `extra_action_used`) — odnotuj w issue jako drobne rozszerzenie payloadu, NIE przeprojektowuj mechaniki.
- **Reużyć istniejące tokeny dark-fantasy** (`--bg-primary`, `--accent` złoto `#c9a54a`, `--danger` krew, `--success` zieleń, skala `--space-*`) — BEZ nowej palety. Bottom sheet (wysuw od dołu, kciuk), NIE modal centralny.
- **Reakcja ≠ akcja:** Unik/Blok = toggle „uzbrojony" (`↺` za darmo); Zaklęcie/Zapasy/Zmiana strefy = akcja (`⏳` zużywa turę). Niedostępne opcje: widoczne, wyszarzone + powód.
- „Mechanika decyduje, LLM narruje" obowiązuje — feedback CZYTA stan, nic nie liczy.

## TWOJE ZADANIE W TEJ SESJI — dokładnie JEDNO zadanie SF

1. W `notes.md` → FAZA SF znajdź pierwsze niezaznaczone `[ ]` zadanie (kolejność SF1→SF2→…→SF7 → kamień SF).
2. Przeczytaj jego pełny opis w CZĘŚCI AI („Cel / Dla agenta / Weryfikacja") i sprawdź w kodzie, czy stan zgadza się z opisem. Sprzeczność → **STOP**, opisz prostym językiem, czekaj na decyzję.
3. Utwórz GitHub issue: tytuł `[TASK] SFNN — <nazwa>`, labels `enhancement` + `needs-testing`, struktura wg szablonu issue #18 (sekcja **Numbers Policy** jeśli dotyczy — rozmiary/czasy = wartości startowe).
4. Wdróż skillem **`/tdd`** w trybie auto (bez pytań pośrednich). Test = **Playwright UI** w `/admin/#tools → 🎭 Playwright` (kontrakt: pasek/arkusz/stan); pytest tylko jeśli zadanie dotknie helpera JS-logiki testowalnego osobno. **Bump `?v=`** przy zmianie współdzielonego modułu.
5. **Weryfikacja wizualna OBOWIĄZKOWA** — `/game-screen` na szerokości telefonu; obejrzyj zrzut, zanim ogłosisz GREEN. Kondycje/feedback weryfikuj w **Combat Sandbox** (admin → Narzędzia).
6. Zaktualizuj `notes.md` (`[x]` + `[#NNN]` + licznik) i `game_mechanics.md` CZĘŚĆ AI (zaznacz zadanie zrobione). Zaproponuj commit wg konwencji — **nie pushuj bez zgody**.
7. **STOP. Raport po polsku, prostym językiem:**
   - co zrobione i dlaczego (2–4 zdania bez żargonu),
   - „Jak możesz to sam sprawdzić" — krok po kroku na https://aigm-dev.studio-colorbox.com/ (co kliknąć, co zobaczysz; dla feedbacku: Sandbox, który przycisk, jaki komunikat),
   - co następne w kolejce.

## WYJĄTEK — kamień SF (ostatnia pozycja)

Czysty playtest czytelności (`/game-screen` telefon + Sandbox sweep feedbacku) — bez cyklu TDD i bez issue `[TASK]`; raport do issue `[SMOKE] FAZA SF` (utwórz/użyj).

## ZASADY ŻELAZNE

- Tylko DEV (`.61`). Nigdy PROD.
- ZERO zmian mechaniki/endpointów — frontend gracza only.
- Nigdy pełny `pytest tests/` — tylko test zadania.
- Issue zamyka tylko Piotr po weryfikacji wizualnej; `needs-testing` zostaje do tego momentu.

Zacznij od kroku 1.
