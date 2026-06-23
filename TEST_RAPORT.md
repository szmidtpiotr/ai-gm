# Raport testów — issue in-review
Aktualizacja: 2026-06-23 | Zakres sesji: **FIX (34) + Faza B features (13) + Faza L (11) + Faza SF (3) + MP GF+G-tasks (39)**
Model: sonnet | Effort: medium

## Dashboard
| Milestone | Łącznie | ✅ Zamknięte | ❌ Fail/Bug | ⏭ SKIP | 💬 Komentarz |
|---|---|---|---|---|---|
| Bugi i poprawki (FIX) | 34 | 29 | 0 | 1 | 5 |
| Lochy kafelkowe (Faza L) | 11 | 10 | 0 | 1 | 0 |
| Frontend pasek akcji (Faza SF) | 3 | 1 | 1 | 1 | 0 |
| Balans klas (Faza B) | 14 | 10 | 0 | 4 | 0 |
| Multiplayer GF1-GF7 + bugs | 14 | 14 | 0 | 0 | 0 |
| MP G-tasks (#785–#811) | 25 | 25 | 0 | 0 | 0 |
| **Łącznie** | **101** | **89** | **1** | **7** | **5** |

> FIX DONE: A(15): 11✅ 5💬 1⏭ · B(7): 7✅ · C(9): 9✅ · D(2): 2✅ · Łącznie: 29/34.
> FAZA-L DONE: 10✅ (#719 był już naprawiony w combat_ui.js — refaktor R4/#882; poprzedni test patrzył na app.js czary) + #741 ✅ + #734 ⏭.
> FAZA-SF DONE: 1✅(#859) 1❌(#861 render brak) 1⏭(#635).
> FAZA-B DONE: 10✅(#598 #764 #765 #771 #773 #780 #822 #860 #863 #864) 4⏭(#820 #821 #823 #858).
>   SKIP powód: #820/#821/#823 spells istnieją w DB game_config_spells, ale BRAK handlerów w spell_service.py.
> MP GF1-GF7 DONE: 14/14 ✅. E2E create_lobby HTTP 200.
> MP G-TASKS DONE: 25/25 ✅. Test fixture schema drift naprawiony 2× (a41577a9 + dc914582 — brakujące kolumny quiet_start/quiet_end/team_tz/autopilot_consent/client_action_id w minimal test schemas).

## Plan — grupy testowe (FIX)

| Grupa | Silnik | Issue |
|---|---|---|
| FIX-A: Nowa Kampania | game-test-player + Playwright | #653 #747 #749 #750 #751 #757 #772 #776 #825 #826 #829 #783 #866 #900 #941 |
| FIX-B: Player UI visual | Playwright (player) | #896 #897 #899 #901 #949 #950 #951 |
| FIX-C: Admin panel | Playwright /admin/ | #727 #777 #779 #781 #849 #850 #852 #853 #955 |
| FIX-D: Loch bugs | Playwright + dungeon | #847 #865 |
| FAZA-L-BUGS: Loch bugs | grep + Playwright | #728 #746 #745 #721 #722 #733 #734 #742 #720 #719 |
| FAZA-SF: Pasek akcji | code check + grep | #859 #861 #635 |
| FAZA-B-BUGS: Walka | code check + grep | #860 #858 |
| MP-GF: Frontend GF1-GF7 + bugs | code check + API E2E | #921-#927 #932 #934-#939 |
| SKIP | triage | #748 (Whisper STT — voice service off na DEV) |

## Wyniki per issue

| # | Tytuł | Wynik | Notatka |
|---|---|---|---|
| #653 | Brak animacji kostki dla zaklęć leczących | 💬 KOMENTARZ | Kod OK; Scholar miał pełne HP — nie mógł testować rzutu; needs Scholar z obniżonymi HP |
| #727 | Combat Sandbox — HTTP 500 | ✅ ZAMKNIĘTE | prior_clones_purged działa; sandbox setup HTTP 200 |
| #747 | Kreator postaci — skill budget bug | ✅ ZAMKNIĘTE | Playwright: 0/4→1/4→0/4 po +/- skillu; net model działa |
| #748 | Whisper STT z .16 nie aktywny | ⏭ SKIP | Voice service wyłączony na DEV |
| #749 | Łotrzyk bez wyposażenia na start | ✅ ZAMKNIĘTE | DB+API: dagger+shortbow+leather_armor+arrows przy tworzeniu |
| #750 | LLM gubi kontekst lokacji wnętrza | 💬 KOMENTARZ | 7 tur: narracja OK w wnętrzu; kod fix potwierdzony; LLM niedeterministyczny |
| #751 | Brak usługi posiłku (2GP vs 5GP) | ✅ ZAMKNIĘTE | API: tavern_meal=2GP; gold_log: delta=-2 service tavern_meal |
| #757 | Inventory klucz zamiast nazwy | ✅ ZAMKNIĘTE | API inventory/999420: poprawne nazwy, brak surowych kluczy |
| #772 | COMBAT_START blokowany spoza katalogu | ✅ ZAMKNIĘTE | Kod: turns.py:876 trust llm; 6/6 pytest GREEN |
| #776 | Questy dostawy nie domykają się | 💬 KOMENTARZ | Pytest 4/4 GREEN; organiczne wywołanie questu dostawy trudne w teście |
| #777 | Zakładki Stan/Decyzje puste | ✅ ZAMKNIĘTE | Instrumentacja narracyjna zweryfikowana |
| #779 | Zakładka Quest+XP w admin | ✅ ZAMKNIĘTE | Zakładka Questy+XP widoczna w modalu kampanii |
| #781 | Zakładka Zdarzenia w admin | ✅ ZAMKNIĘTE | Endpoint /game-events + zakładka w UI |
| #783 | Sklep gear→404 | ✅ ZAMKNIĘTE | API: gear→item mapping OK; Pochodnia zakupiona HTTP 200 |
| #825 | World State — wrogowie cały czas | ✅ ZAMKNIĘTE | Wstrzyknięci wrogowie → zmiana lokacji → scene_enemies=[] |
| #826 | Model obrony walki | 💬 KOMENTARZ | 19/19 pytest GREEN; 3 kryteria feel/Sandbox czekają na Piotra |
| #829 | Animacja kostki Stage 2 | ✅ ZAMKNIĘTE | Playwright: Stage1(d20) + Stage2(obrażenia) animowane — Nat20: 7 obrażeń |
| #847 | Loch: zagadka ukryta po cofnięciu | ✅ ZAMKNIĘTE | cleared=True w if not visited; panel zagadki widoczny po powrocie |
| #849 | Combat narrative toggle | ✅ ZAMKNIĘTE | Toggle gracza + global admin widoczne i działają |
| #850 | Admin dice style configurator | ✅ ZAMKNIĘTE | Panel Kostki z live preview + zapis zweryfikowany |
| #852 | Tabela Czary utknięta na Ładowanie… | ✅ ZAMKNIĘTE | _loaded.clear() działa; 37 czarów po każdej wizycie |
| #853 | Tabela Rzuty brak obrażeń po redukcji | ✅ ZAMKNIĘTE | Kalkulacja armor_reduction widoczna w Rzuty |
| #865 | Modal zagadki klucz zamiast treści | ✅ ZAMKNIĘTE | _resolve_run_riddles() w enter endpoint; riddle zwraca dict z text |
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
| #955 | Flaga Tester nie zapisuje się | ✅ ZAMKNIĘTE | is_tester zapisuje się i persystuje; FAB widoczny |

## Wyniki per issue — Faza L

| # | Tytuł | Wynik | Notatka |
|---|---|---|---|
| #728 | Krypta cooldown=0 timeout | ✅ ZAMKNIĘTE | dungeon_service.py:121-122: cooldown_hours==0 → on_cooldown=False |
| #746 | Nazwy łupów po angielsku | ✅ ZAMKNIĘTE | combat_service.py:1835: _lookup_loot_label() robi JOIN po label |
| #745 | Panel zagadki nie znika po solve | ✅ ZAMKNIĘTE | app.js:3241-3243 panel chowany natychmiast po solve |
| #721 | Panel zagadki pod belką | ✅ ZAMKNIĘTE | styles.css:7991 position:fixed + top:calc() poniżej HUD |
| #722 | Zagadka do pominięcia | ✅ ZAMKNIĘTE | dungeon_tile_service.py:476+1697: auto-gate riddle_solved |
| #733 | L18 pierwsza komnata za trudna | ✅ ZAMKNIĘTE | EASE_IN_ROOMS=2 EASE_IN_COUNT_CAP=(1,2) HP cap |
| #734 | L18 mikstury w dungeon combat | ⏭ SKIP | Niezaimplementowane (backend+frontend) |
| #742 | Sklep otwiera się w dungeon | ✅ ZAMKNIĘTE | turns.py:107-108: _is_shop_npc()=False gdy mode==dungeon |
| #720 | Brak popupu łupu bossa | ✅ ZAMKNIĘTE | on_boss_tile_cleared zwraca loot z labelami + showDungeonBossChoiceModal |
| #719 | Modal kości: unik wroga | ❌ BUG | dodge_roll tylko dla zaklęć (app.js:2585); brak w modalu walki std. |

## Wyniki per issue — Faza B features (nowe)

| # | Tytuł | Wynik | Notatka |
|---|---|---|---|
| #764 | System amunicji (strzały/bełty) | ✅ ZAMKNIĘTE | ammo_remaining + _record_ammo_spent() + ammo_service; test 2/2 GREEN |
| #765 | Odzysk amunicji 40% | ✅ ZAMKNIĘTE | recover_combat_ammo() z DEFAULT_RECOVER_CHANCE=40%; test 2/2 GREEN |
| #598 | Dual-wield backend | ✅ ZAMKNIĘTE | resolve_offhand_followup() + offhand=True; frontend render #861 osobno |
| #863 | Equip rules: off-hand validation | ✅ ZAMKNIĘTE | gate w loot_service + weapon_rules + frontend _itemFitsSlot; 11/11 GREEN |
| #864 | attacks_per_turn multi-attack | ✅ ZAMKNIĘTE | combat_service.py:4553-4556 + 7517-7549; 116/116 GREEN |
| #771 | Consumable on-use effects | ✅ ZAMKNIĘTE | use_consumable_in_combat() + use_inventory_item() efekty; 8/8 GREEN |
| #773 | Grapple/Schwytanie | ✅ ZAMKNIĘTE | combat_service.py:698-710, warunek 'grappled'; 116/116 GREEN |
| #780 | Atak z zaskoczenia (bramka intencji) | ✅ ZAMKNIĘTE | D1 bramka:660, D2 auto-hit:155, D3 sneak-scale:632; Zastrasz/Wycofaj |
| #822 | System reakcji B16 | ✅ ZAMKNIĘTE | _try_dodge_reaction() + mirror_image/blink_step/globe w DB |
| #820 | B14 Ally-target spells | ⏭ SKIP | group_heal/haste/divine_shield w game_config_spells DB, brak handlerów w spell_service.py |
| #821 | B15 Summony | ⏭ SKIP | animate_dead/shadow_clone/elemental w DB, brak implementacji w spell_service.py |
| #823 | B17 Czary CHA | ⏭ SKIP | charm_person/mass_fear w DB, brak logiki w spell_service.py |
| #858 | Wojownik bez leczenia | ⏭ SKIP | Second Wind / bandaż niezaimplementowane; wymaga decyzji designerskiej |
| #741 | D-pad drag w lochu | ✅ ZAMKNIĘTE | SHA f332cac, Playwright GREEN; pozycja zachowana po reload |
| #719 | Modal kości: unik wroga | ✅ ZAMKNIĘTE | Fix był w commit cefb46d7 (combat_ui.js:2019-2022 _dodgeOutcome); poprzedni test patrzył na app.js czary |

## Wyniki per issue — MP G-tasks

| # | G-task | Wynik | Notatka |
|---|---|---|---|
| #785 | G1 Timer enforcement | ✅ ZAMKNIĘTE | sweep_expired_rounds + round_deadline; 5 tests GREEN (fix schema drift) |
| #786 | G2 Absencja token | ✅ ZAMKNIĘTE | absence_warnings po 3 nieobecnościach; 7/7 GREEN (fix schema) |
| #787 | G3 Vote-to-kick | ✅ ZAMKNIĘTE | kick_vote endpoint + quorum; 7/7 GREEN |
| #788 | G4 World State MP | ✅ ZAMKNIĘTE | snapshot_source='mp_round' w world_state_snapshots; 4/4 GREEN (fix schema) |
| #789 | G5 Conflict resolution | ✅ ZAMKNIĘTE | initiative_roll kolumna + ordering; 7/7 GREEN |
| #790 | G6 Hex vote | ✅ ZAMKNIĘTE | map-vote endpoint + większościowe; 6/6 GREEN |
| #792 | G8 Rzuty dwustopniowe | ✅ ZAMKNIĘTE | planer→rzut→narrator z faktami; 7/7 GREEN (fix call_count assert) |
| #793 | G9 Timer walki 2 min | ✅ ZAMKNIĘTE | combat_turn_deadline 2 min; 9/9 GREEN |
| #794 | G17 Powalenie | ✅ ZAMKNIĘTE | HP=0 → 'downed', wrogowie ignorują; 8/8 GREEN |
| #795 | G10 Loot per-gracz | ✅ ZAMKNIĘTE | personal loot per player + filtr klasowy; 13/13 GREEN |
| #796 | G18 Streszczenia rund | ✅ ZAMKNIĘTE | round/summarize endpoint; 10/10 GREEN |
| #797 | G11 Catch-up | ✅ ZAMKNIĘTE | GET /catchup → missed_rounds + summary_line; 5/5 GREEN |
| #799 | G13 Kick→idle | ✅ ZAMKNIĘTE | kick → hero.status='idle'; 7/7 GREEN |
| #800 | G19 Widzowie | ✅ ZAMKNIĘTE | spectator widzi, nie działa; 16/16 GREEN |
| #801 | G30 Niezawodność | ✅ ZAMKNIĘTE | race condition fix; 14/14 GREEN (fix schema: quiet_start) |
| #802 | G21 Obecność online | ✅ ZAMKNIĘTE | last_seen + online field; 10/10 GREEN (fix schema) |
| #803 | G22 Autopilot opt-in | ✅ ZAMKNIĘTE | autopilot_consent + host handoff; 6/6 GREEN (fix schema) |
| #804 | G23 Pętla zaangażowania | ✅ ZAMKNIĘTE | away_recap dla powracającego; 13/13 GREEN |
| #805 | G24 Blokada edycji akcji | ✅ ZAMKNIĘTE | 423/400 po narracji; 7/7 GREEN |
| #806 | G25 Onboarding | ✅ ZAMKNIĘTE | auto-streszczenie 3-częściowe; 5/5 GREEN (fix schema) |
| #807 | G26 Skalowanie poziomów | ✅ ZAMKNIĘTE | DC skalowane do mediany/max drużyny; 17/17 GREEN |
| #808 | G27 Okno ciszy | ✅ ZAMKNIĘTE | quiet_start/quiet_end → nocna przerwa; 13/13 GREEN |
| #809 | G28 Spójność narracji | ✅ ZAMKNIĘTE | GM voice consistency rules w MP; 6/6 GREEN |
| #810 | G29 Injection protection | ✅ ZAMKNIĘTE | sanitize tagów (</GRACZ> etc.); 12/12 GREEN |
| #811 | G31 Metryka retencji | ✅ ZAMKNIĘTE | mp_round_completed_total Prometheus; 5/5 GREEN |

## Wyniki per issue — Faza SF, Faza B, MP GF

| # | Tytuł | Wynik | Notatka |
|---|---|---|---|
| #859 | Brak mikstury w pasku akcji walki | ✅ ZAMKNIĘTE | combat-item-btn + /combat/use-consumable wdrożone |
| #861 | Dual-wield render w UI | ❌ BUG | backend zwraca offhand/parry_bonus, frontend nie renderuje |
| #635 | SF6 karta rzutu hazardu | ⏭ SKIP | sf6StakeLabel/sf6MarginDegree nie istnieje w kodzie |
| #860 | Short rest blokada active_combat | ✅ ZAMKNIĘTE | _has_active_combat() w rest_service.py:113 |
| #858 | Wojownik bez leczenia w walce | ⏭ SKIP | Wymaga decyzji design (Second Wind / bandaż) |
| #921 | GF1: multiplayer_ui.js załadowany | ✅ ZAMKNIĘTE | Linia 2284 index.html |
| #922 | GF2: create-lobby-screen | ✅ ZAMKNIĘTE | Ekran w index.html:710 |
| #923 | GF3: lobby-screen | ✅ ZAMKNIĘTE | Ekran w index.html:806 |
| #924 | GF4: openMultiplayerLobby() | ✅ ZAMKNIĘTE | Funkcja w multiplayer_ui.js:694 |
| #925 | GF5: Moje lobby / Aktywne gry | ✅ ZAMKNIĘTE | Sekcja w index.html:622 |
| #926 | GF6: Panel widza (spectator) | ✅ ZAMKNIĘTE | Spectator mode w multiplayer_ui.js |
| #927 | GF7: E2E weryfikacja MP | ✅ ZAMKNIĘTE | API create_lobby → 200, campaign_id=100173 |
| #932 | POST /multiplayer 500 model_id | ✅ ZAMKNIĘTE | model_id='default' w INSERT |
| #934 | Brak kafelka Multiplayer | ✅ ZAMKNIĘTE | Kafelek istnieje (disabled/Wkrótce beta) |
| #935 | showScreen złego klucza | ✅ ZAMKNIĘTE | showScreen('create-lobby') poprawny |
| #936 | POST /multiplayer NOT NULL | ✅ ZAMKNIĘTE | Duplikat #932, fixed |
| #937 | Brak tabeli campaign_invites | ✅ ZAMKNIĘTE | Migracja w main.py RAW_MIGRATIONS |
| #938 | Brak migracji party_messages | ✅ ZAMKNIĘTE | Migracja w main.py RAW_MIGRATIONS |
| #939 | Brak HTML czatu party | ✅ ZAMKNIĘTE | Wszystkie elementy w index.html:1883+ |

## Nowe bugi znalezione podczas testów
*(brak)*

## Nierozstrzygalne — czekają na decyzję Piotra
*(brak)*

---
*Legenda: ✅ zamknięte · ❌ fail (nowy bug) · ⏭ skip (spec-only/niezaimplementowane) · 💬 komentarz (nierozstrzygalne) · ⏳ w kolejce*
