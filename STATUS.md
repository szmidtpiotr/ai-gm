# STATUS — gdzie jesteśmy (captain's log)

> **Po co ten plik:** czytasz go na starcie sesji żeby w 30 sek wiedzieć gdzie jesteśmy.
> Po polsku, narracja — NIE lista zadań (ta jest w `fix_list.md` / GitHub Issues) i NIE spec (`game_mechanics.md`).
> **Claude utrzymuje ten plik** — aktualizuje sekcje na końcu każdej sesji. Ty tylko czytasz.
>
> Trzy sekcje: **CO ROBIMY TERAZ** · **OSTATNIO ZROBIONE** · **UWAŻAJ (pułapki)**.

_Ostatnia aktualizacja: 2026-06-19_

---

## 🎯 CO ROBIMY TERAZ

**FOKUS: `fix_list.md` — bieżące bugi wykryte przez Piotra grając przez kampanię.** To jest aktywny tor. Cel: doprowadzić mechanikę do stanu **sprawdzonej i grywalnej** — bo to brama do Multiplayera.

**Dwa tory zadań (zrozum różnicę):**
- **Tor A — `notes.md`** = planowy rozwój, wdrażanie mechanik z `game_mechanics.md` (fazy A–H, U, S, L, MP). *Obecnie przyhamowany* — patrz stan faz niżej.
- **Tor B — `fix_list.md`** = bieżące bugi z przejść kampanii. **← TU PRACUJEMY TERAZ.**

**Stan faz (Tor A):**
- FAZA L (lochy) — **praktycznie skończona** i GRYWALNA (L19 zaliczony 2026-06-17, Piotr przeszedł 14/14 checkpointów na mobile).
- Faza 5 / Multiplayer — **WSTRZYMANY** świadomie, aż mechanika single-player będzie sprawdzona i grywalna (czyli aż fix_list się wyczyści). Nie ruszamy MP wcześniej.

**Następne sensowne zadania** (z `fix_list.md`, priorytet malejąco):
- P1 quick wins jeszcze otwarte: **#756** (duplikacja questów co turę), **#742** (sklep w lochu + brak odświeżenia ekwipunku), **#751** (przepłata za posiłek 2 vs 5 GP), **#746** (angielskie nazwy łupów w modalu walki), **#757** (inventory pokazuje klucz zamiast nazwy), **#734** (brak mikstury w walce).
- Wymaga TWOJEJ decyzji A/B zanim ruszę (`design`): **#733** (balans 1. komnaty solo lvl1), **#747** (kreator: minus skilla zjada punkt), **#753** (unik double jeopardy), **#744** (wojownik z tarczą nie blokuje).

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

---

## ⚠️ UWAŻAJ (pułapki / kruche miejsca)

- **`notes.md` ma NIEROZWIĄZANY konflikt merge** (linie ~16–31: `<<<<<<< Updated upstream` / `>>>>>>> Stashed changes`) w tabeli postępu faz. Dwie wersje liczb (114/198 vs 103/193). **Do posprzątania** — Claude powinien to rozwiązać zanim tabela będzie wiarygodna.
- **Rozjazd w fix_list:** #740 jest `[DONE]` w bloku BOARD (commit 6172dac), ale w sekcji P1 (linia 95) wciąż odhaczone na `[ ]`. Lista wymaga drobnej synchronizacji.
- **#516 BLOCKED** — smoke P1 wywala się na braku tabeli `character_rentals` (migracja F13). Trzeba najpierw odblokować migracją.
- **Backend = obraz Dockera.** `docker compose restart` NIE łapie zmian Pythona — zawsze `--build` (patrz CLAUDE.md).
- **Piloty lochów ruiny/zamek niegrane end-to-end** — content-complete ale bez pełnego przejścia; #733/#734 przeniesione do nowego lochu katakumby_mroku (#738).
- **PROD (.62 / main)** — nic tam nie wchodzi bez Twojego wyraźnego „tak". DEV (.61 / develop) = auto-commit.

---

## 📌 Jak czytać resztę
- **`fix_list.md`** = **Tor B** — bieżące bugi z przejść kampanii, priorytety P0–P5. ← aktywny tor.
- **`notes.md`** = **Tor A** — master checklist faz (A–H, U, S, L, MP) = wdrażanie z game_mechanics + dziennik decyzji.
- **`game_mechanics.md`** — spec mechanik (jak gra MA działać). Źródło zadań Toru A.
- GitHub Issues — pełna analiza każdego bugu (root cause + fix + acceptance).
