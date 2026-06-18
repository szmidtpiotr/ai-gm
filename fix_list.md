# FIX LIST — backlog wdrożeń (bugi + feature)

Jedyne źródło statusów dla `/mass-implement prompt_fix.md`. Jedna sesja = jedno zadanie (jeden issue).
Każdy issue ma już PEŁNĄ analizę w GitHub (root cause + fix + pliki + acceptance) — agent czyta issue i wdraża, nie tworzy nowego.

Format: `- [ ] #NNN — krótki tytuł` · `(dep: #MMM)` = zależność (rób PO prereq) · `(design)` = wymaga decyzji A/B w issue.

> **UWAGA o kolumnie TO DO (GitHub board):** nie mam scope `read:project`, więc NIE widzę kolumn board.
> Lista zbudowana z **otwartych issues** (stan=open). Aby auto-sync z kolumną TO DO board:
> `gh auth refresh -s read:project` (lub PAT z `read:project`) — wtedy będę czytał status z Projects v2.
> Do tego czasu: aktualizuję na podstawie issues open + Twoich wskazań.

---

## A. Bugi deterministyczne — niskie ryzyko, mały zakres (rób najpierw)

- [ ] #743 — Slot `hands` w loot_service (zakładanie rękawic: invalid armor_coverage)
- [ ] #749 — Rogue nie dostaje wyposażenia na start (dodać "rogue" do whitelist starter items)
- [ ] #748 — Whisper STT z .16 nieaktywny (voice_hosts is_active=1)
- [ ] #746 — Nazwy łupów po angielsku (_preview_loot_from_roll_items: JOIN po label z DB)
- [ ] #757 — Inventory pokazuje klucz zamiast nazwy (narracyjny item → też do game_items + dymek opisu)
- [ ] #751 — Brak usługi posiłku (dodać tavern_meal ~2 GP; reguła cena↔klucz w prompcie)

## B. Sklep / trade

- [ ] #766 — Modal sklepu przy zwykłych deklaracjach (trade regex granice słów + usunąć fallback keys[0])
- [ ] #742 — Sklep w lochu (guard dungeon-mode) + brak odświeżenia ekwipunku po zakupie (refreshCharacterData)

## C. Loch — zagadki / wejście / loot

- [ ] #722 — Zagadka do pominięcia: puste exit_conditions na kaflach z riddle_key (engine auto-gate lub backfill)
- [ ] #721 — Panel zagadki pod belką + goły klucz string (move_through_door resolve riddle + z-index + pole text)
- [ ] #745 — Panel zagadki nie znika po rozwiązaniu (node.cleared=true on solved)
- [ ] #740 — Podwójna narracja wstępna lochu (LLM_OPEN + room_narrative)
- [ ] #759 — Boss osiągalny w 1-2 komnacie (_fill_open_doors: wyklucz węzeł bossa z weldu + BFS-walidacja)

## D. Narracja / kontekst / czas

- [ ] #750 — LLM gubi kontekst wnętrza: blok ŚWIAT (teren hexa) nadpisuje scenę karczmy (gate imperatywu dla interior sub-location)
- [ ] #755 — Wyciek tagów (QUEST_SUGGEST/NPC_MEMORY) w streamie (front stripMechanicTags w streaming + finalize)
- [ ] #756 — Duplikacja questów (inject aktywne questy do promptu + reguła anty-dup + dedup po celu)
- [ ] #758 — Rozjazd czasu: time_advance_minutes nieudokumentowane w prompcie (kontrakt LLM + opcja advance_to_time_of_day)
- [ ] #752 — Kampania znika z listy po wyjściu z lochu (filtr loadCampaigns dla idle hero + previous_campaign_id auto-powrót)
- [ ] #763 — Ruch zignorowany + zły test Oszustwo zamiast Skradania (prompt skill-select; dep: #750)

## E. Kreator / mechanika (część design — decyzja A/B w issue)

- [ ] #747 — Kreator: obniżenie skilla zużywa punkt budżetu (Math.abs) (design A/B)
- [ ] #753 — Unik double jeopardy + dodge poza pulą losowania (design — unik zastępuje AC / niższy DC / pula)
- [ ] #744 — Wojownik z tarczą nie może blokować (shield_block rank>=1, brak startowych skilli) (design)

## F. Feature (wdrażać na moją prośbę, nie auto)

- [ ] #764 — System amunicji (strzały/bełty + start 20 + odejmowanie przy ataku dystansowym)
- [ ] #765 — Odzyskiwanie amunicji (40% + pill) (dep: #764)
- [ ] #741 — Loch D-pad: przeciąganie + środkowy ⊕ otwiera mapę

---

## G. Starszy backlog (otwarte issues sprzed sesji — do potwierdzenia czy w TO DO)

- [ ] #719 — L-fix: modal kości pokaż test uniku wroga
- [ ] #720 — L-fix: brak popupu „co wypadło z bossa"
- [ ] #724 — L20b: portrety wrogów/NPC u gracza
- [ ] #727 — Combat Sandbox setup HTTP 500 (FK stale clone)
- [ ] #728 — Krypta cooldown=0 nadal pokazuje timeout
- [ ] #733 — L18: pierwsza komnata za trudna solo lvl1
- [ ] #734 — L18: brak użycia mikstury w walce
- [ ] #647 — Wskrzeszenie nie reaktywuje kampanii (410)
- [ ] #653 — Brak wizualizacji rzutu dla zaklęć leczących poza walką
- [ ] #516 — SMOKE P1: brak tabeli character_rentals (F13 migracja)

### Feature backlog (osobno, na prośbę)
- [ ] #598 — Walka dwoma broniami (dual-wield)
- [ ] #659 — B11 AoE multi-target maga
- [ ] #635 — SF6 karta rzutu hazardu
- [ ] #547 — G20 eksport kampanii do książki
- [ ] #593 — Web Push pełny stack
- [ ] #602 — Niezawodne powiadomienia (wielokanałowe)
- [ ] #738 — LB4 głębszy loch katakumby_mroku

---

## Log zmian listy
- 2026-06-18 — utworzono; sekcje A–F z issues sesji #721–#766, G ze starszego open backlog.
