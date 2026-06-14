# Acceptance — Usability Gate (FAZA U → Brama do Multiplayera)

> **Zadanie U27** ([GATE] Go/No-Go MP). Obiektywna checklista odpowiadająca na pytanie
> **„czy gra jest używalna"** — zamiast wrażenia. Pozytywny wynik wszystkich kryteriów +
> decyzja Piotra = start Fazy G (Multiplayer).
>
> **Zakres (decyzja Piotra 2026-06-12):** tylko tryby **Nowa Kampania** i **Gotowa Kampania**.
> Tryb **Loch kafelkowy** ⏸ ODŁOŻONY — kryteria wrócą po redesignie (FAZA L). Nie blokuje tej bramki.
>
> Pełny opis zadania: `game_mechanics.md` CZĘŚĆ AH → BLOK 8 (U27).

## Jak czytać tę checklistę

Każde kryterium ma **warstwę dowodu**:

| Warstwa | Co dowodzi | Jak sprawdzane |
|---------|-----------|----------------|
| **MECH** | deterministyczna prawda backendu (endpoint / invariant DB) | `pytest` lub bezpośredni odczyt `/data/ai_gm.db` |
| **PLAY** | zachowanie obserwowalne przez gracza | playtest LLM `/game-smoke <tryb>` (15 tur, tabela checkpointów) |
| **MAN** | stan wizualny UI | ręczny zrzut / `/game-test-player-screenshot` |

Bramka jest **zielona** gdy wszystkie kryteria w zakresie = ✅ (lub ⚠️ wyłącznie z defektem P2,
który Piotr świadomie akceptuje). Każdy ❌ lub P0/P1 = issue + naprawa + retest TEGO punktu.

**Narzędzie playtestu:** U27 w specie wskazuje `/game-test-player-screenshot`, ale pyta o
grywalność **per tryb, 15 tur, każdy archetyp** — to dokładnie cel `/game-smoke <tryb>`
(narzędzie milowych bramek U9b/U32b: 2 tryby × 15 tur × tabela checkpointów + defekty P0/P1/P2).
Dlatego warstwa PLAY = `/game-smoke nowa-kampania` + `/game-smoke gotowa-kampania`.

---

## A. Kryteria wspólne (oba tryby)

| # | Kryterium | Warstwa | Mapowanie na FAZĘ U |
|---|-----------|---------|---------------------|
| A1 | Nowa postać + onboarding bez pomocy z zewnątrz | PLAY/MAN | U20 |
| A2 | 15 tur bez ani jednej sprzeczności narracja↔stan (`llm_tag_errors` = 0 **nieobsłużonych**) | MECH/PLAY | U5/U6 |
| A3 | Pełny cykl walki (start → atak → rana → śmierć wroga → loot) | PLAY | U5/HF-1/HF-7 |
| A4 | Quest przyjęty i ukończony automatycznie | MECH/PLAY | HF-2/U8/HF-10/HF-11 |
| A5 | Zakup + sprzedaż z poprawnymi cenami (złoto zdjęte/dopisane, saldo po) | MECH/PLAY | U16/U26 |
| A6 | Odpoczynek + wydanie XP (każdy archetyp łącznie min. raz) | PLAY | U16/HF-5 |
| A7 | Śmierć → ekran śmierci → wskrzeszenie | PLAY/MAN | (rdzeń) |
| A8 | Recap „Poprzednio…" po powrocie | MECH/MAN | U19 |
| A9 | Dziennik zgodny ze stanem gry (Zadania/Wątki/Kronika) | MECH/MAN | U18 |
| A10 | Reset bohatera przy nowej kampanii (conditions/rentale/mana czyszczone; XP/złoto/ekw. nietknięte) | MECH | U14 |

## B. Świat i ruch (Blok 9)

| # | Kryterium | Warstwa | Mapowanie |
|---|-----------|---------|-----------|
| B1 | Min. 3 zmiany hexa w 15 turach — ≥1 klikiem na mapie, ≥1 przez tekst | PLAY | U30 |
| B2 | `current_hex` w World State = podświetlony hex na mapie po każdej turze | MECH/MAN | U30 (#518) |
| B3 | LLM użył ≥1 gotowej lokacji z bazy (key w logu) | PLAY | U29 |
| B4 | 0 duplikatów pending dla lokacji istniejących w bazie | MECH | U29 (#522) |
| B5 | Wejście do lokacji ładuje NPC z bazy do sceny | MECH/PLAY | U31 |
| B6 | log `travel_narrated_without_move` = 0 | MECH | U30 (anty-desync guard) |

## C. Tylko Gotowa Kampania

| # | Kryterium | Warstwa | Mapowanie |
|---|-----------|---------|-----------|
| C1 | Beaty odpalają się (min. 2 w 15 tur, w tym 1 przez fallback U8) | MECH/PLAY | U8/HF-8/HF-10/HF-11 |
| C2 | Story Gravity L1 widoczne przy stagnacji | PLAY | U8 |

## D. Loch kafelkowy — ⏸ ODŁOŻONE

Kryteria wrócą po redesignie lochów (FAZA L). NIE wchodzą do tej bramki:
pełny run win/death/abandon z semantyką U21; trap + riddle przechodzalne; pity timer; cooldown.

---

## Wykonanie (U27)

1. Warstwa MECH: zob. sekcję „Mechaniczne invarianty" niżej — odczyty endpointów/DB po runach.
2. Warstwa PLAY: `/game-smoke nowa-kampania` + `/game-smoke gotowa-kampania` (raporty → #512/#513),
   tabela checkpointów per run, defekty jako issues `smoke-defect` z priorytetem.
3. Każdy fail = issue + naprawa + retest TEGO punktu. Wszystko zielone → decyzja Piotra o Fazie G.

### Mechaniczne invarianty (odczyt po runie, na żywej kampanii smoke)

```sql
-- A2: nieobsłużone błędy tagów (oczekiwane 0; obsłużone z korektą U6 są OK)
SELECT COUNT(*) FROM llm_tag_errors WHERE campaign_id = :cid AND handled = 0;
-- B4: duplikaty pending lokacji istniejących w bazie (oczekiwane 0)
SELECT COUNT(*) FROM pending_locations p
  JOIN game_locations g ON lower(g.label) = lower(p.label);
-- B6: narracja podróży bez ruchu mechanicznego (oczekiwane 0)
SELECT COUNT(*) FROM llm_tag_errors WHERE campaign_id = :cid AND error_type='travel_narrated_without_move';
-- A4/C1: ukończone questy i beaty
SELECT status, COUNT(*) FROM character_quests WHERE character_id = :hid GROUP BY status;
```

---

## Wynik bramki

> Run wykonany 2026-06-13 (U27, issue #577). Werdykt go/no-go podejmuje **Piotr** po przeglądzie.

| Tryb | Run | Werdykt | P0 | P1 | P2 | Raport |
|------|-----|---------|----|----|----|--------|
| Nowa Kampania | camp 74 (`#512-run3`, warrior) | GRYWALNY (P1 #578 naprawiony) | 0 | 0 (#578 fixed) | 2 (#579,#580) | #512 |
| Gotowa Kampania | camp 75 (`#513-run3`, scholar, szablon 1) | GRYWALNY | 0 | 0 | 0 | #513 |

### Wyniki kryteriów (oba tryby łącznie)

- **A1–A10 (wspólne):** ✅ wszystkie zweryfikowane (onboarding, walka, quest+persystencja, sklep, odpoczynek+XP, dziennik/recap z poprzednich zadań). Archetypy: warrior (nowa) + scholar (gotowa).
- **B1 (ruch hex):** ✅ klik mapy / `POST /travel` ✅; **tekst kierunkowy ✅ po naprawie #578** (live: JSON `{0,1}→{0,0}`, streaming `{1,0}→{0,1}`).
- **B2/B3/B5:** ✅ `current_hex` sync, lokacje z bazy (`ai_generated=0`), NPC z `location_npc_assignments`.
- **B4 (0 duplikatów pending):** ✅ 0 nowych AI-lokacji w runach.
- **B6 (`travel_narrated_without_move`):** ✅ po naprawie #578 — guard `guard_travel_desync` wpięty w oba żywe tory (loguje desync do `llm_tag_errors`); 0 desyncu = prawdziwe zero.
- **C1/C2 (Gotowa — beaty):** ✅ 2 beaty auto-complete (talk_to_npc + visit_location), `objective_type` na beatach (HF-8), plan z szablonu (HF-3).
- **D (Loch):** ⏸ poza zakresem.

**Rekomendacja agenta (zaktualizowana 2026-06-13):** wszystkie kryteria A/B/C ✅ — **#578 naprawione** (B1/B6 zielone,
7/7 pytest + 1/1 Playwright, live verify na obu endpointach). Pozostają tylko P2 (#579/#580), które nie blokują.
Bramka U27 jest technicznie zielona dla 2 trybów w zakresie.

**Decyzja Piotra (go/no-go Faza G): NO-GO (2026-06-13)** — Multiplayer wstrzymany; #578 naprawione.
Niezależnie od tej bramki, start FAZY G wymaga jeszcze **FAZY S** (skille/stany) i **FAZY L** (lochy kafelkowe).
