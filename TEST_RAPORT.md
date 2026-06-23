# Raport testów — issue in-review
Aktualizacja: 2026-06-23 | Zakres tej sesji: **FIX — Bugi i poprawki (34 issue)**
Model: sonnet | Effort: medium

## Dashboard
| Milestone | Łącznie | ✅ Zamknięte | ❌ Fail/Bug | ⏭ SKIP | 💬 Komentarz |
|---|---|---|---|---|---|
| Bugi i poprawki (FIX) | 34 | 18 | 0 | 1 | 5 |
| **Łącznie** | **34** | **18** | **0** | **1** | **5** |

> FIX-A DONE (15 issue): 11 zamknięte, 5 komentarze, 1 skip. FIX-B DONE (7 issue): 7 zamknięte. FIX-C/D kolejne.

## Plan — grupy testowe (FIX)

| Grupa | Silnik | Issue |
|---|---|---|
| FIX-A: Nowa Kampania | game-test-player + Playwright | #653 #747 #749 #750 #751 #757 #772 #776 #825 #826 #829 #783 #866 #900 #941 |
| FIX-B: Player UI visual | Playwright (player) | #896 #897 #899 #901 #949 #950 #951 |
| FIX-C: Admin panel | Playwright /admin/ | #727 #777 #779 #781 #849 #850 #852 #853 #955 |
| FIX-D: Loch bugs | Playwright + dungeon | #847 #865 |
| SKIP | triage | #748 (Whisper STT — voice service off na DEV) |

## Wyniki per issue

| # | Tytuł | Wynik | Notatka |
|---|---|---|---|
| #653 | Brak animacji kostki dla zaklęć leczących | 💬 KOMENTARZ | Kod OK; Scholar miał pełne HP — nie mógł testować rzutu; needs Scholar z obniżonymi HP |
| #727 | Combat Sandbox — HTTP 500 | ⏳ | FIX-C |
| #747 | Kreator postaci — skill budget bug | ✅ ZAMKNIĘTE | Playwright: 0/4→1/4→0/4 po +/- skillu; net model działa |
| #748 | Whisper STT z .16 nie aktywny | ⏭ SKIP | Voice service wyłączony na DEV |
| #749 | Łotrzyk bez wyposażenia na start | ✅ ZAMKNIĘTE | DB+API: dagger+shortbow+leather_armor+arrows przy tworzeniu |
| #750 | LLM gubi kontekst lokacji wnętrza | 💬 KOMENTARZ | 7 tur: narracja OK w wnętrzu; kod fix potwierdzony; LLM niedeterministyczny |
| #751 | Brak usługi posiłku (2GP vs 5GP) | ✅ ZAMKNIĘTE | API: tavern_meal=2GP; gold_log: delta=-2 service tavern_meal |
| #757 | Inventory klucz zamiast nazwy | ✅ ZAMKNIĘTE | API inventory/999420: poprawne nazwy, brak surowych kluczy |
| #772 | COMBAT_START blokowany spoza katalogu | ✅ ZAMKNIĘTE | Kod: turns.py:876 trust llm; 6/6 pytest GREEN |
| #776 | Questy dostawy nie domykają się | 💬 KOMENTARZ | Pytest 4/4 GREEN; organiczne wywołanie questu dostawy trudne w teście |
| #777 | Zakładki Stan/Decyzje puste | ⏳ | FIX-C |
| #779 | Zakładka Quest+XP w admin | ⏳ | FIX-C |
| #781 | Zakładka Zdarzenia w admin | ⏳ | FIX-C |
| #783 | Sklep gear→404 | ✅ ZAMKNIĘTE | API: gear→item mapping OK; Pochodnia zakupiona HTTP 200 |
| #825 | World State — wrogowie cały czas | ✅ ZAMKNIĘTE | Wstrzyknięci wrogowie → zmiana lokacji → scene_enemies=[] |
| #826 | Model obrony walki | 💬 KOMENTARZ | 19/19 pytest GREEN; 3 kryteria feel/Sandbox czekają na Piotra |
| #829 | Animacja kostki Stage 2 | ✅ ZAMKNIĘTE | Playwright: Stage1(d20) + Stage2(obrażenia) animowane — Nat20: 7 obrażeń |
| #847 | Loch: zagadka ukryta po cofnięciu | ⏳ | FIX-D |
| #849 | Combat narrative toggle | ⏳ | FIX-C |
| #850 | Admin dice style configurator | ⏳ | FIX-C |
| #852 | Tabela Czary utknięta na Ładowanie… | ⏳ | FIX-C |
| #853 | Tabela Rzuty brak obrażeń po redukcji | ⏳ | FIX-C |
| #865 | Modal zagadki klucz zamiast treści | ⏳ | FIX-D |
| #866 | Link /?join=TOKEN → login zamiast rejestracji | 💬 KOMENTARZ | Kod deployed OK; Playwright miał stały token — test w prawdziwym incognito potrzebny |
| #896 | Flash starego tła logowania | ✅ ZAMKNIĘTE | --bg-screen-login:none w CSS; brak FOUC |
| #897 | Niespójne ikony dolnego paska | ✅ ZAMKNIĘTE | SVG zamiast emoji w pasku nawigacji |
| #899 | Brak przycisku powrotu z Kampanii do Bohaterów | ✅ ZAMKNIĘTE | header__back w campaigns-screen (id=campaigns-back) |
| #900 | Nowa kampania cicho odpina bohatera | ✅ ZAMKNIĘTE | Playwright: modal "Nowa kampania?" + Anuluj działa |
| #901 | Ikona kodeksu → link do Księgi Zasad | ✅ ZAMKNIĘTE | showRulesBook() otwiera /rules/ w nowym tabie |
| #941 | Testowe lokacje wyciekają do kampanii | ✅ ZAMKNIĘTE | DB: 0 canonical+active test locations |
| #949 | Przycisk Wyślij poza ekran (mobile) | ✅ ZAMKNIĘTE | min-width:0 w .composer__input; send widoczny na 390px |
| #950 | Party Chat w sesji single | ✅ ZAMKNIĘTE | enterGame() woła multiplayerUI.deactivate() na starcie |
| #951 | Swipe nie zmienia zakładek karty postaci | ✅ ZAMKNIĘTE | initSheetTabSwipe: dynamiczny querySelectorAll zamiast stałej listy |
| #955 | Flaga Tester nie zapisuje się | ⏳ | FIX-C |

## Nowe bugi znalezione podczas testów
*(brak)*

## Nierozstrzygalne — czekają na decyzję Piotra
*(brak)*

---
*Legenda: ✅ zamknięte · ❌ fail (nowy bug) · ⏭ skip (spec-only/niezaimplementowane) · 💬 komentarz (nierozstrzygalne) · ⏳ w kolejce*
