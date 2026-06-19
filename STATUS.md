# STATUS — gdzie jesteśmy (captain's log)

> **Po co ten plik:** czytasz go na starcie sesji żeby w 30 sek wiedzieć gdzie jesteśmy.
> Po polsku, narracja — NIE lista zadań (ta jest w **GitHub Issues + Milestones = „Plan"**) i NIE spec (`game_mechanics.md`).
> **Claude utrzymuje ten plik** — aktualizuje sekcje na końcu każdej sesji. Ty tylko czytasz.
>
> Trzy sekcje: **CO ROBIMY TERAZ** · **OSTATNIO ZROBIONE** · **UWAŻAJ (pułapki)**.

_Ostatnia aktualizacja: 2026-06-19 (sesja #742 playwright-test-report)_

---

## 🎯 CO ROBIMY TERAZ

**Zadania = GitHub Issues + Milestones (Plan).** Rozkład faz: FAZA 5 Multiplayer 33 · **FIX 23** · FAZA L 12 · FAZA B 11 · FAZA 6 6 · FAZA LB 2 · FAZA SF 1.

**FOKUS: milestone `FIX` — bieżące bugi z przejść kampanii.** Cel: mechanika **sprawdzona i grywalna** → to brama do Multiplayera (FAZA 5 świadomie WSTRZYMANA aż single-player grywalny).

**Stan faz:**
- FAZA L (lochy) — praktycznie skończona i GRYWALNA (L19, 14/14 checkpointów na mobile).
- FAZA 5 Multiplayer — 33 issues (backlog, planowane); start dopiero po wyczyszczeniu FIX.

**Następne sensowne (milestone FIX, otwarte):** #751 (przepłata za posiłek), #746 (angielskie nazwy łupów), #757 (inventory klucz zamiast nazwy), #734 (brak mikstury w walce). Decyzja A/B przed startem (`design`): #733, #747, #753, #744.

---

## ✅ OSTATNIO ZROBIONE (ostatnie sesje)

**Audyt kampanii #99791 (A–D) — domknięty:**
- #775 — zapłata „mieszek z monetami" dawała 0 zł → parser grant_item→grant_gold (łamało ekonomię).
- #776 — questy dostawy/wymiany nie domykały się → `[QUEST_COMPLETE]` flipuje status.
- #755 — tagi mechaniczne (QUEST_SUGGEST itp.) wyciekały do narracji na mobile → front wycina tagi.
- #777 — zakładki Stan/Decyzje/Zdarzenia puste dla kampanii narracyjnych → emisja game_events.
- #779 — nowa zakładka 🎯 Questy+XP w monitorze kampanii.
- #780 — atak z zaskoczenia + ogólna bramka intencji po zdobyciu przewagi.

**Bugi gameplay / loch:**
- #766 — sklep otwierał się na zwykłe deklaracje (skUPiam/przygLADam) → regex granice słów.
- #740 — podwójna narracja wstępna przy wejściu do lochu → usunięty dublujący room_narrative.
- #767 — KRYTYCZNY: granie bohaterem przejmowało cudzą aktywną kampanię (korupcja danych) → guard.
- #743 — crash przy zakładaniu rękawic → slot `hands`.
- #759/#722/#721/#745 — bugi grafu lochu i zagadek (boss osiągalny za wcześnie, zagadki).
- **#756** — duplikacja questów co turę → zweryfikowane Playwright 2026-06-19 ✅.
- **#742** — sklep w lochu (guard dungeon-mode) + odświeżenie ekwipunku po buy/sell → TDD 4/4 + Playwright 3/3 + visual test 2026-06-19 ✅.

---

## ⚠️ UWAŻAJ (pułapki / kruche miejsca)

- **#516 BLOCKED** — smoke P1 wywala się na braku tabeli `character_rentals` (migracja F13). Trzeba najpierw odblokować migracją.
- **Backend = obraz Dockera.** `docker compose restart` NIE łapie zmian Pythona — zawsze `--build` (patrz CLAUDE.md).
- **Piloty lochów ruiny/zamek niegrane end-to-end** — content-complete ale bez pełnego przejścia; #733/#734 przeniesione do nowego lochu katakumby_mroku (#738).
- **PROD (.62 / main)** — nic tam nie wchodzi bez Twojego wyraźnego „tak". DEV (.61 / develop) = auto-commit.

---

## 📌 Jak czytać resztę
- **Plan** (GitHub Issues + Milestones, zakładka w pluginie) = **jedyne źródło zadań**. Milestone = faza. ← tu bierzesz pracę.
- **`notes.md`** (góra) = ściąga komend + „jak pracujemy"; (niżej) archiwum faz + proza/decyzje. NIE lista zadań.
- **`game_mechanics.md`** — spec mechanik (jak gra MA działać).
- GitHub Issue — pełna analiza każdego zadania (root cause + fix + acceptance + komentarze).
