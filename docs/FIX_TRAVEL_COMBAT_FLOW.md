# FIX SPEC — Flow walki w drodze (zasadzka) + composer walki ŻAR

> Analiza: 2026-07-12, na bazie sesji gracza (kampania 77770021, walka #501, mag Drundor
> vs "Nieznany napastnik"). Dokument dla agenta wdrażającego — analiza zrobiona,
> file:line zweryfikowane na branchu `develop`. Zadania T1–T4 są niezależne;
> T4 jest P0 i można je robić pierwsze.

---

## Stan zastany (fakty, zweryfikowane)

**Flow zasadzki w podróży:**

1. `hex_travel_service.py:905-914` — trafiony rzut na spotkanie w hexie →
   `_pick_encounter_enemy()` (`:260-267`) losuje z `encounter_pool` hexa, a gdy pusty —
   z fallbacku terenowego `_WORLD_ENCOUNTER_FALLBACK_POOLS` (`:248-257`).
   Pule fallback zawierają **`unknown_attacker`** (generyczny placeholder silnika,
   `game_config_enemies.key='unknown_attacker'`, label "Nieznany napastnik").
   Teren spoza mapy (np. tundra) → `_WORLD_ENCOUNTER_FALLBACK_DEFAULT =
   ["bandit","unknown_attacker","wolf"]`. Stąd w sesji gracza wylosował się placeholder.
2. Wylosowany `enemy_key` ląduje w `session_flags.travel_plan` (`hex_travel_service.py:1163-1188`),
   `interrupt_reason="encounter"`.
3. Frontend dostaje `travel_notice` budowany w `turns.py:9052-9074` z **statycznego**
   szablonu `_TRAVEL_NOTICE_BY_REASON["encounter"]` (`turns.py:9044-9048`):
   title "Zasadzka w drodze", message "Ktoś zagrodził ci drogę…".
   **`travel_notice` NIE niesie żadnych danych wroga** (brak enemy_key/label/image/threat).
4. Walka startuje przy `POST /travel-resume` (log: `combat_start`, `enemy_keys=["unknown_attacker"]`).
   Snapshot walki (`_row_to_combat_dict`, `combat_service.py:2098-2176`) niesie już wszystko:
   `image_url` (JOIN po enemy_key, `:2152-2161`) oraz `relative_threat {glyph,label,tier,count}`
   (`:2163-2167`, progi w `threat_display_service.py:38-41`: 🟢 słaby / 🟡 wyrównany / 🔴 groźny / 💀 zabójczy).
5. Frontend montuje **oba overlaye naraz**: `EnemyRevealCard` (z‑59, `CombatView.tsx:173-183, 593-599`)
   NA WIERZCHU oraz `TravelInterruptModal` (z‑58, `Game.tsx:763-863`) POD SPODEM.
   Gracz widzi kartę wroga, zamyka ją ("Stań do walki") i… pod spodem czeka drugi,
   generyczny modal "Zasadzka w drodze" z guzikiem "⚔ Walcz". Dublet z pkt 1+2 zgłoszenia.

**Composer walki (piguły):** `CombatActionBar.tsx:33-45` — piguły hardcoded:
Atak / Czar (gdy `hasMana`) / Zbliż–Cofnij / **Unik** / Uciekaj.

**ActionSheet:** `ActionSheet.tsx:30-35` — wewnętrzne taby `MODES` (Atak|Czar|Ruch|Obrona)
dublują piguły. Zakładka Obrona (`:179-200`) hardcoduje tylko unik+blok.

---

## T1 — Modal zasadzki z danymi wroga (pkt 1+2 zgłoszenia)

**Cel:** jeden modal zamiast dwóch; pokazuje obrazek wroga, nazwę i wskaźnik trudności.
Tekst: „**{label} stanął ci na drodze. Stań do walki.**" (przy >1 wrogach:
„{label} i {n-1} innych zagrodzili ci drogę…").

**Zmiany backend:**

- `turns.py` `_travel_notice_for()` (`:9052`): dla `reason=="encounter"` dołóż do payloadu
  dane wroga z `travel_plan.enemy_key`:
  `enemy: {key, label, image_url, count}` + `relative_threat: {glyph, label, tier}`.
  - label/image_url: SELECT z `game_config_enemies` po key.
  - `relative_threat`: policz przez `threat_display_service.relative_threat` na statblocku
    z configu (tak jak #1344 — wartość STAŁA ze statblocku, nie z rankowanego combatanta).
  - Message generuj z labela; zostaw obecny generyczny string jako fallback, gdy
    enemy_key pusty/nieznany.
- **Nie zmieniaj** `_TRAVEL_NOTICE_BY_REASON` dla dusk/forced_camp.

**Zmiany frontend (`Game.tsx:763-863` TravelInterruptModal):**

- Gdy `notice.enemy` obecne: renderuj obrazek (skalowany, jak w `EnemyRevealCard.tsx:62-73`,
  z fallbackiem „Brak wizerunku") + badge zagrożenia (glyph+label, wzór
  `EnemyRevealCard.tsx:50-59`) + nowy message. Najlepiej wydziel współdzielony
  komponent z EnemyRevealCard zamiast kopiować markup.
- **Deduplikacja karty wroga:** gdy TravelInterruptModal z `reason=="encounter"` został
  pokazany, `EnemyRevealCard` dla tej walki ma się NIE pokazać. Mechanizm: `Game.tsx`
  przekazuje do `CombatView` prop `suppressReveal`/`revealSeenCombatId`, a `CombatView.tsx:173-183`
  dopisuje ten `combat_id` do `revealedRef` zanim odpali reveal. (Uwaga na race:
  oba montują się w tym samym renderze — nie polegaj na kolejności efektów, tylko na
  propie liczonym z `travelNotice` + `activeCombat.combat_id`.)
- EnemyRevealCard zostaje bez zmian dla walk NIE-podróżnych (start z narracji) — tam
  dalej pełni rolę karty pojawienia (#1344).

**Content (opcjonalny podtask):** wywal `unknown_attacker` z pól fallback
`_WORLD_ENCOUNTER_FALLBACK_POOLS` / `_DEFAULT` (`hex_travel_service.py:248-257`) i dołóż
brakujące tereny (tundra!). Placeholder ma zostać w silniku (fallback techniczny), ale nie
powinien być normalnym losem z puli. Rozważ szerszy dobór przez `eligible_enemy_pool`
(teren + power, jak w #1345) — jeśli to za duży zakres, wydziel do osobnego issue.

**Weryfikacja:** podróż aż do zasadzki (albo test pytest na `_travel_notice_for` z
travel_plan.enemy_key) → modal z obrazkiem, nazwą, badge; PO zamknięciu modal
„Nieznany napastnik / Stań do walki" się NIE pojawia. Walka z narracji (nie-podróżna) →
EnemyRevealCard działa jak dotąd.

---

## T2 — Piguła obrony maga: Bariera + Tarcza Many (pkt 3)

**Cel:** mag z wykupionymi skillami widzi swoje opcje obronne zamiast (lub obok) Unika.

**Fakty:**

- Piguła „Unik" hardcoded (`CombatActionBar.tsx:44`) → otwiera ActionSheet tab defense,
  który hardcoduje 2 opcje: unik + blok (`ActionSheet.tsx:179-200`) → POST
  `/combat/declare-reaction`, a backend `declare_player_reaction` przyjmuje TYLKO
  `{"dodge","shield_block"}` (`combat_service.py:8577`).
- Cała logika skill-gated JUŻ ISTNIEJE po stronie reaktywnej (SF10):
  `_reaction_options()` (`combat_service.py:6321-6378`) zwraca per postać:
  `dodge` / `shield_block` (tarcza założona) / `arcane_ward` (#1324, skill + mana ≥ koszt) /
  `mana_shield` (#1325, skill + mana > 0 + nieużyta w rundzie). `ReactionModal.tsx:51-54,113-162`
  już to renderuje przy trafieniu wroga.

**Zmiany:**

1. Backend: dodaj `defense_options: list[str]` do snapshotu walki
   (`_row_to_combat_dict` albo `load_combat_snapshot`) — wynik `_reaction_options()`
   dla aktualnego stanu gracza. Frontend nie może sam zgadywać skilli.
2. Backend: rozszerz akceptowane wartości `declare_player_reaction`
   (`combat_service.py:8577`) o `arcane_ward` i `mana_shield`; pre-deklaracja ma przy
   następnym trafieniu wroga odpalić istniejące resolvery
   (`_try_arcane_ward_reaction :1218`, `_try_mana_shield_reaction :1310`) — walidacja many
   w momencie WYZWOLENIA, nie deklaracji.
3. Frontend `CombatActionBar.tsx`: pigułę „Unik" przemianuj na „**Obrona**" (otwiera sheet).
   Zakładka defense w `ActionSheet.tsx:179-200`: renderuj opcje z `defense_options`
   zamiast hardcode — mapa labeli: dodge→„Unik", shield_block→„Blok tarczą",
   arcane_ward→„Arkanowa Bariera (1✦)", mana_shield→„Tarcza Many". Postać bez żadnego
   skilla obronnego → opcja „take" / komunikat „Brak wyszkolonych reakcji".

**Numbers Policy:** żadnych nowych liczb — koszty/capy z #1324/#1325 bez zmian.

**Weryfikacja:** pytest na `declare_player_reaction("arcane_ward")` → następne trafienie
wroga rozwiązane barierą (mana −1, dmg wg resolvera). Sandbox/Playwright: mag ze skillami
widzi w Obronie obie nowe opcje; wojownik widzi unik+blok jak dotąd.

---

## T3 — ActionSheet czarów: bez dubli, kategorie PL, opisy (pkt 4+5)

**Fakty:**

- Taby `MODES` w `ActionSheet.tsx:30-35` (Atak|Czar|Ruch|Obrona) dublują piguły composera.
- Wiersz czaru pokazuje surowy enum jako podtytuł — fallback `sp.spell_type` w
  `ActionSheet.tsx:219-224` („narrative", „attack"…).
- `description` czarów ISTNIEJE end-to-end: kolumna `game_config_spells.description`,
  serwowana przez `GET /spells` i `GET /characters/{id}/spells`
  (`characters.py:3302-3318`, `spell_service.py:113-146`), typ
  `SpellCatalogEntry.description` (`sheet.ts:190`) — ale jest **wycinana** przy mapowaniu
  na `SpellAction` w `CombatView.tsx:135-144`.
- Gotowa mapa PL kategorii istnieje i jest nieużywana w walce:
  `PanelSpells.tsx:19-25` (`SPELL_TYPE_PL`).
- Lista czarów NIE filtruje narracyjnych — `magic_light`/`detect_magic` widoczne w walce
  (`CombatView.tsx:127-147` — brak filtra po spell_type).

**Zmiany frontend:**

1. **Usuń pasek tabów z ActionSheet** (`:106-127`). Sheet otwiera się w trybie z piguły
   i pokazuje tylko ten tryb (tytuł już się przełącza, `:77`). Przełączanie trybów =
   zamknij sheet, kliknij inną pigułę. (Mniej kodu, zero dubli.)
2. Tryb czar: **grupuj listę po `spell_type`** z nagłówkami sekcji PL — rozszerz
   `SPELL_TYPE_PL` o wszystkie realne wartości z DB
   (attack 14, attack_aoe 4, heal 3, defense 5, effect 8, effect_aoe 1, narrative 2,
   reaction 3, summon 4): Atakujące / Obszarowe / Lecznicze / Ochronne / Efekty /
   Obszarowe efekty / Użytkowe / Reakcje / Przyzwania. Wynieś mapę do współdzielonego
   modułu (np. `lib/spells.ts`), importuj w `PanelSpells` i `ActionSheet`.
3. Wiersz czaru: pod nazwą **`description` (1–2 zdania)**, a kości/mana jako meta
   (obecny format `1d8 obr. · 2✦` zostaje jako druga linia meta). Dodaj `description`
   do `SpellAction` (`ActionSheet.tsx:17-26`) i przestań ją wycinać w
   `CombatView.tsx:135-144`. Surowy enum NIE może być już nigdzie fallbackiem.
4. Czary `narrative` w walce: pokaż w sekcji „Użytkowe" na końcu (nie ukrywaj — decyzja
   designowa Piotra może być inna; jeśli ma zniknąć z walki, to osobny 1-liniowy filtr).

**Zmiany content (data bug):**

- `rdzen_shield` („Rdzeń-Tarcza") ma `spell_type='attack'` → powinno być `defense`
  (zweryfikowane w DEV DB). Popraw w seedzie (`migrations_admin.py`, sekcja rdzeń) +
  migracja UPDATE dla istniejących DB. Sprawdź przy okazji `rdzen_pulse` (attack — OK).
- Przejrzyj długości `description` — np. `rdzen_shield` ma 10 znaków; czary z opisem
  < ~30 znaków dopisać (1–2 zdania, po polsku, opis EFEKTU nie lore).

**Weryfikacja:** Playwright: mag → piguła Czar → sheet bez tabów, sekcje PL, opis pod
każdym czarem, brak surowych enumów. `?v=`/build ŻAR na .61.

---

## T4 — P0: walka znika w trakcie, bez wyniku i lootu (pkt 6)

**Symptom:** wróg żyje, interfejs walki znika, wraca chat, zero informacji, brak modalu lootu.

**Dowód z DEV (2026-07-12):** walka #501 (kampania 77770021): w DB `status='active'`,
wróg `hp_current=8/12`, `current_turn='unknown_attacker_01'` — a gracz zgłasza zniknięcie
UI. Do tego walki #479, #462, #451, #443 wiszą `status='active'` od dni — ten sam wzorzec.
Backend w oknie zdarzenia zwracał same 200 (resolve-attack, enemy-turn, GET /combat).

**Architektura (dlaczego znika bez śladu):**

- Frontend polluje `GET /campaigns/{id}/combat` co 2 s (`useCombat.ts:15-27`).
  Endpoint (`combat.py:89-95` → `get_active_combat`, `combat_service.py:2194-2205`)
  filtruje `WHERE status='active'` → po końcu walki poll zwraca `{active:false, combat:null}`
  i **nigdy nie dostarcza `ended_reason` ani `loot_pool`**.
- `Game.tsx:116-119` liczy `activeCombat`; `Game.tsx:658-663` renderuje `CombatView`
  tylko gdy truthy — inaczej chat.
- **Cały UI końca walki (victory/loot/death modale + toast) żyje WEWNĄTRZ `CombatView`**
  (`CombatView.tsx` efekt „koniec walki" → `setOutcome` → `CombatOutcomes`,
  loot z `endedCombat.loot_pool`, `lib/outcomes.ts:97-100`). Gdy koniec przychodzi pollem,
  React odmontowuje `CombatView` ZANIM efekt zdąży pokazać modal → cichy powrót do chatu.

**Przyczyny (rankowane):**

1. **[frontend] Unmount race** — jw.; każdy koniec zaobserwowany pollem = gwarantowany
   cichy vanish.
2. **[backend] Asymetria poll vs mutacja** — mutacje zwracają `load_combat_snapshot()`
   (bez filtra statusu, `combat_service.py:2179+`), poll ukrywa stan ended. Jedyny kanał
   z `ended_reason` to response mutacji, który łatwo przegapić.
3. **[backend] Fałszywe zwycięstwo przy desyncu `turn_order`** — `_advance_turn_impl`
   (`combat_service.py:9265-9278`) kończy walkę victory gdy `len(living)<=1`, ale `living`
   buduje iterując po **`turn_order`**, nie po `combatants`. Wróg żywy, lecz nieobecny w
   `turn_order` (summony/reinforcementy/multi-enemy z FAZY BL; utrzymanie turn_order tylko
   w `_b15_persist_with_turn_order`, `:5226-5336`) → victory z HP>0. To jedyna znana
   ścieżka „koniec mimo żywego wroga" — `_all_enemies_dead` (`:5815-5821`) iteruje po
   combatants i ten guard (`:9233`) jest wtedy False.
4. **[frontend] Auto-driver tury wroga połyka błędy** — `.catch(() => setHpFreeze(null))`
   w `CombatView.tsx` bez `pushCombatState` i bez komunikatu; przegapiony snapshot końca
   przepada, a `endedRef` nie ponawia.
5. **[frontend, hipoteza do potwierdzenia — case #501]** walka AKTYWNA w DB a UI znikł:
   sprawdź w `useCombat.ts` co się dzieje z `data` przy błędzie/refetchu (czy query może
   przejść w `undefined` → `activeCombat=null` → unmount, i czy po udanym refetchu UI
   wraca). Restart backendu w trakcie sesji (19:51 w logach) to realny scenariusz.

**Zmiany (wszystkie cztery, to komplet):**

1. Backend: poll `GET /combat` ma zwracać także stan `ended` (snapshot z `ended_reason`,
   `loot_pool`, `xp`), przynajmniej do czasu potwierdzenia przez klienta — najprościej:
   zwracaj ostatnią walkę kampanii niezależnie od statusu (`load_combat_snapshot`),
   pole `active` licz z `status=='active'`. Front sam decyduje, czy ended już obsłużył
   (po `combat_id`).
2. Frontend: **wynieś stan `outcome` NAD `CombatView`** (do `Game.tsx` albo osobny
   provider): przejście `active→ended/null` nie może odmontować UI zanim gracz zobaczy
   `CombatOutcomes` (victory/loot/death). `CombatView` może zniknąć, modal wyniku zostaje.
   Fallback: gdy poll zwróci ended/null bez wcześniejszego snapshotu — pokaż chociaż toast
   „Walka zakończona: {ended_reason}".
3. Backend: napraw warunek zwycięstwa w `_advance_turn_impl` (`:9265-9278`) — `living`
   licz z `combatants` (źródło prawdy jak `_all_enemies_dead`), `turn_order` służy tylko
   kolejności; ewentualnie asercja/log `combat_turn_order_desync` gdy żywy combatant nie
   występuje w turn_order.
4. Frontend: `.catch` w auto-driverze tury wroga → refetch snapshotu + toast błędu;
   błąd/`undefined` w pollu NIE zeruje `activeCombat` (trzymaj ostatni znany stan,
   pokaż wskaźnik reconnect).

**Weryfikacja:**

- pytest: walka z wrogiem w `combatants` nieobecnym w `turn_order` → `_advance_turn_impl`
  NIE kończy walki victory.
- pytest/integracja: `GET /combat` po `end_combat("victory")` → payload z
  `ended_reason='victory'` + `loot_pool`.
- Playwright: dobij wroga → modal zwycięstwa + loot ZAWSZE widoczny (także gdy koniec
  przyjdzie pollem — zasymuluj przez zabicie wroga cheatem admina między pollami).
- Sprzątanie: wiszące walki #479/#462/#451/#443 (+ #501 jeśli dalej wisi) zamknąć ręcznie
  po weryfikacji albo zostawić jako materiał do reprodukcji — decyzja przy wdrożeniu.

---

## T5 — Sekwencja i czytelność tur walki (analiza 2026-07-12, druga runda)

**Zgłoszenie Piotra (oczekiwany flow):** (1) inicjatywa z animacją + wynik wroga + kto
zaczyna; (2) rzut na trafienie z widocznym testem obrony wroga (czemu trafiłem / czemu
uniknął); (3) trafienie → osobny rzut na obrażenia → odjęcie HP; (4) tura wroga: przy
trafieniu modal przyjmij/unik/blok → test reakcji → dopiero wtedy obrażenia; (5) pętla.
Symptomy: (A) klik unik/blok, a HP już odjęte; (B) modal rzutu przy ataku gracza czasem
w ogóle się nie pokazuje.

**Kluczowe ustalenie: silnik (backend) już implementuje ten flow niemal 1:1.
Gubi go warstwa prezentacji w ŻAR.** Fakty:

1. **Inicjatywa** — obie strony rzucają (`initiate_combat`, `combat_service.py:4881`
   gracz, `:4972` wróg), oba wyniki SĄ w snapshotcie (`initiative_roll` na combatancie),
   remis wygrywa gracz (`:5028`). Frontend: zero animacji, zero banera „kto zaczyna" —
   tylko statyczny złoty chip z liczbą przy portrecie (`CombatBanner.tsx:218-220`).
   Dane są, prezentacji brak.
2. **Obrona wroga to RZUT, nie statyczne AC** — `compute_player_attack_dodge_outcome`
   (`combat_service.py:6298`): wróg rzuca d20+DEX przeciw atakowi gracza. Response
   `resolve-attack` niesie komplet: `player_raw_d20`, `attack_total`, `dodge_roll
   {raw, modifier, total, verdict}`, `hit`, `dodged`, `damage_rolls`,
   `margin_damage_bonus`, `armor_reduction`. Karta w feedzie rozróżnia „WRÓG UNIKA"
   vs „PUDŁO" (`lib/combat.ts:99-114`; „PUDŁO" tylko przy Nat 1). Ale **overlay kości
   NIE pokazuje rzutu obrony wroga liczbowo** — gracz nie widzi „twój atak 16 vs unik
   wroga 14", stąd „mało czytelne czemu trafił lub nie".
3. **Rzut obrażeń jest osobnym etapem** — overlay dwustopniowy: d20 „NA TRAFIENIE",
   potem kość obrażeń przy trafieniu (`CombatView.tsx:260-286`), wynik maskowany do
   końca animacji. Działa — ale patrz symptom B niżej.
4. **Okno reakcji: backend ODRACZA obrażenia — nie ma żadnego „odjął i odda".**
   `_attack_try_reaction` (`combat_service.py:6602-6635`) zapisuje
   `pending_reaction {damage, attack_roll, options…}` i robi early-return PRZED mutacją
   HP (zapis HP w `:8029` nieosiągalny na tej ścieżce); router wstrzymuje turę
   (`awaiting_reaction`, `combat.py:276-279`). HP mutuje się WYŁĄCZNIE w
   `resolve_reaction` (`:8379`), po teście wybranej reakcji. Snapshot polla w otwartym
   oknie niesie HP sprzed ciosu, a `pending_reaction.damage` jest wycinany
   (`_row_to_combat_dict :2101-2107`) — nic nie wycieka z backendu.

**Symptom A (HP odjęte „przed" wyborem) — przyczyny frontendowe:**

- `hpFreeze` (zamrożenie wyświetlanego HP, `CombatView.tsx:84-98`) jest zakładany
  **tylko na ścieżce animowanej**: przy reakcji dopiero gdy
  `willAnimate = showPlayerDice && choice !== "take"` (`:465`). Gdy preferencja kości
  wyłączona / wybór „przyjmij" / reakcja `available=false` → po response mutacji
  `useCombatMutation.onSuccess` (`useCombat.ts:51-57`) + `pushCombatState` (`:468`)
  wpychają zredukowane HP do cache i pasek/rail spada NATYCHMIAST, zanim gracz
  przeczyta kartę wyniku → wrażenie „już odjęte".
- Ścieżka `showEnemyDice` OFF otwiera ReactionModal w ogóle bez freeze (`:411-413`) —
  działa tylko dzięki odroczeniu backendowemu; każdy przyszły refactor to rozjedzie.
- Dodatkowo trafienia BEZ okna reakcji (postać nie ma żadnej opcji z `_reaction_options`
  — np. mag bez skilla `dodge`, bez many na barierę): silnik sam rzuca
  `player_evasion` (d20+DEX, widoczne w `combat_turns.narrative`) i od razu aplikuje
  obrażenia — gracz widzi tylko spadek HP, bez modalu i bez informacji, że automatyczny
  unik zawiódł. W sesji Drundora (walka #502, event 3140: atak 19 vs AC 11,
  `player_evasion {raw:3,+1=4}`, −7 HP) dokładnie to zaszło. To się miesza percepcyjnie
  z oknami reakcji → „czasem modal jest, czasem HP samo spada".

**Doprecyzowanie od Piotra (2026-07-12): obie animacje kości ma WŁĄCZONE.** Czyli
symptom A wystąpił mimo ścieżki animowanej — do zbadania przy wdrożeniu dodatkowo:
(a) wyścig `useCombatMutation.onSuccess` (cache z obniżonym HP zapisany PRZED startem
animacji — czy każdy element poza bannerem/railem na pewno czyta przez `view` z freeze,
np. karta w feedzie, DeathScreen, VitalsRail w innych rozdzielczościach);
(b) ścieżka „przyjmij" (bez animacji z definicji, freeze nie zakładany);
(c) ciosy BEZ okna reakcji (auto `player_evasion` — patrz 5e, u maga bez skilla `dodge`
to WIĘKSZOŚĆ trafień) — HP spada bez żadnego modalu, co gracz skleja percepcyjnie
z oknami reakcji. Symptom B analogicznie: skoro preferencja ON, przyczyną są ścieżki
`blocked`/błąd requestu albo race — do reprodukcji z otwartą konsolą.

**Symptom B (brak modalu rzutu przy ataku gracza) — przyczyny:**

- Overlay kości gracza jest CAŁKOWICIE warunkowy od preferencji
  `gamePrefShowPlayerDice` (`appStore.ts:18,178`, przełącznik w `GameMenu.tsx:119`,
  default ON): gdy OFF → tylko mała karta w logu, zero modalu (`CombatView.tsx:287-290`).
- `r.blocked` (poza zasięgiem / brak many) → sam toast, bez rzutu (`:234-246`).
- Błąd requestu → catch z toastem, bez modalu (`:291-295`).
- Do sprawdzenia u Piotra: czy preferencja kości nie została wyłączona w menu gry.

**Zmiany (wszystko frontend poza 5e-opcją):**

1. **5a Karta inicjatywy**: na starcie walki (po/równolegle z modalem zasadzki z T1)
   pokaż sekwencję „Inicjatywa: Ty {X} vs {wróg} {Y} — zaczynasz / zaczyna wróg"
   (dane już w snapshotcie; opcjonalnie animacja d20 obu rzutów). Może być karta w
   feedzie + krótki banner, nie musi być modal.
2. **5b Czytelny wynik trafienia**: etap „NA TRAFIENIE" overlaya pokazuje OBIE liczby:
   atak gracza (d20+mod=total) vs obrona wroga (d20+DEX=total) + werdykt
   („wróg uniknął: 14 ≥ 16? nie → trafienie"). Karta w feedzie analogicznie z liczbami.
   Semantyka zostaje (#826: obrona = rzut, zwykłe pudło = udany unik wroga).
3. **5c Freeze HP przez całe okno reakcji**: zamrożenie wyświetlanego HP od momentu
   `reaction_window=true` do zakończenia PREZENTACJI wyniku reakcji — niezależnie od
   `showPlayerDice`/`showEnemyDice`/wyboru „przyjmij". Ujednolicić: jeden tor
   window→choice→test→obrażenia→reveal HP, z animacją lub bez (bez animacji = te same
   karty, tylko natychmiast).
4. **5d Wynik reakcji zawsze widoczny**: po kliknięciu unik/blok pokaż test reakcji
   (rzut + próg + sukces/porażka), potem obrażenia (0 przy sukcesie), dopiero potem
   spadek paska. Ścieżka animowana już tak działa (`onDiceDone :321`) — wyrównać
   nieanimowaną.
5. **5e Okno reakcji ZAWSZE — silnik nigdy nie rozstrzyga za gracza** (decyzja
   designowa Piotra, 2026-07-12): przy KAŻDYM trafieniu wroga w gracza otwiera się
   okno reakcji, nawet gdy jedyną dostępną opcją jest „Przyjmij cios" (postać bez
   skilli obronnych / bez many / cap reakcji w rundzie #1322 wyczerpany — wtedy opcje
   obronne wyszarzone z powodem, „Przyjmij" aktywne). Automatyczna ścieżka
   `player_evasion` (silnik sam rzuca unik i aplikuje obrażenia, bez pytania)
   **wylatuje z trybu single-player** — zamiast niej normalne okno. Backend:
   `_attack_try_reaction` otwiera okno także przy pustych `_reaction_options`
   (opcja `take` zawsze); ścieżka auto-evasion zostaje wyłącznie tam, gdzie nie ma
   aktywnego gracza (MP sweep nieobecnych — zweryfikować przy wdrożeniu).
   Uwaga: to zmiana zasad gracza → wpis w Księdze Zasad w tym samym PR.
6. **(higiena)** Timeout 8 s auto-„przyjmij" w ReactionModal (`ReactionModal.tsx:41`)
   → po timeout pokaż wyraźnie „czas minął — przyjąłeś cios", nie cichy spadek HP.

**Weryfikacja:** Playwright z `showPlayerDice` ON i OFF: (a) start walki → karta
inicjatywy z obiema wartościami; (b) atak gracza → widoczne atak vs unik wroga;
(c) trafienie wroga w gracza z oknem → HP na pasku NIE zmienia się do rozstrzygnięcia
reakcji (obie preferencje kości); (d) cios bez okna → karta auto-uniku.
DB: `combat_turns.hp_after` dla eventu `reaction_window` = HP sprzed ciosu (już tak jest
— regresja pilnowana testem).

**Uwaga porządkowa (do T4):** wiersz `active_combat` jest KASOWANY przy starcie
kolejnej walki w kampanii (potwierdzone: start #502 usunął #501). Stan „ended" żyje
w DB tylko do następnej walki — kolejny powód, by wynik+loot dostarczać frontowi
niezwłocznie i nie polegać na późniejszym odczycie.

---

## T6 — Loot po zwycięstwie: zawsze modal, zawsze coś wypada

**Decyzja designowa Piotra (2026-07-12):** gracz po zwycięstwie MUSI dostać modal
lootu — także gdy losowanie dało zero (wtedy jasny komunikat „nie miał nic przy
sobie"). Preferencja: **zawsze powinno coś wypaść**, choćby bezwartościowy/narracyjny
drobiazg — puste ręce bez słowa = gracz czuje się oszukany.

**Dowód problemu:** walka #502 (bandyta, `drop_chance=0.8`, `loot_wolf`-style tabela
`loot_bandit`) zakończona victory z `loot_pool='[]'` — i zero informacji w UI
(dodatkowo modal zwycięstwa w ogóle nie wystąpił — to T4; T6 zakłada, że T4 przywróci
modal, i definiuje jego treść przy pustym lootcie).

**Zmiany:**

1. **Backend — gwarantowany drop minimalny**: w `loot_service.roll_loot()` /
   miejscu składania `loot_pool` przy victory: gdy wynik losowania pusty (nietrafiony
   `drop_chance` albo pusta tabela), dorzuć pozycję z **puli narracyjnych drobiazgów**
   (nowa tabela lootu `loot_trash_common`, seedowana: np. „zniszczony mieszek
   (3 miedziaki)", „szczerbaty nóż", „kościana kostka do gry", „strzęp mapy bez
   wartości" — pozycje `game_config_items` z `is_active=1`, wartość 0–1 gp,
   oznaczone narracyjnie). Alternatywnie minimalny rzut złota 1d4 miedziaków.
   Wybór wariantu (przedmiot vs miedziaki vs mix) — do decyzji przy wdrożeniu,
   wartości STARTING. Seed przez git (content-as-code #1202), `created_by='seed'`.
2. **Backend — flaga w payloadzie**: `loot_pool` w snapshotcie końca walki dostaje
   rozróżnienie: `rolled` (z tabeli wroga) vs `consolation` (drop minimalny) —
   front może opisać drobiazg innym tonem („W sakwie tylko śmieci: …").
3. **Frontend — modal lootu zawsze po victory** (zależność: T4 pkt 1-2 musi najpierw
   przywrócić dostarczanie stanu ended): trzy warianty treści:
   (a) normalny loot → lista jak dotąd; (b) tylko consolation → „Przeszukujesz ciało.
   Niewiele przy sobie miał: {drobiazg}"; (c) awaryjnie pusto (nie powinno się już
   zdarzyć) → „Nie miał nic przy sobie". Zero cichych przejść do chatu.
4. **Dungeony/MP**: sprawdzić, czy loot z pokoi lochów i walk MP idzie tą samą
   ścieżką `roll_loot` — jeśli tak, drop minimalny obejmie je automatycznie;
   jeśli nie, wyrównać w osobnym issue.

**Numbers Policy:** szansa 100% na drop minimalny przy pustym losowaniu, wartość
0–1 gp / 1d4 miedziaków — wartości startowe do tuningu.

**Weryfikacja:** pytest: `roll_loot` z wymuszonym pudłem `drop_chance` → pool
niepusty, pozycja oznaczona `consolation`. Playwright: victory → modal ZAWSZE,
wariant (b) przy pustym losowaniu. Księga Zasad: dopisek w rozdziale o łupach.

---

## Kolejność wdrożenia i zakres issue

| Task | Priorytet | Sugerowane issue | Zależności |
|---|---|---|---|
| T4 walka znika | **P0** | osobne issue, backend+frontend | brak |
| T1 modal zasadzki | P1 | osobne issue | snapshot #1344 (jest) |
| T2 obrona maga | P1 | osobne issue | #1324/#1325 (są) |
| T5 sekwencja/czytelność tur + zawsze-pytaj | P1 | osobne issue (5a-5e można ciąć na podtaski) | T2 zwiększy częstość okien reakcji |
| T6 loot: zawsze modal + drop minimalny | P1 | osobne issue | T4 (dostarczenie stanu ended) |
| T3 sheet czarów | P2 | osobne issue (+ data-fix rdzen_shield w tym samym) | brak |

Konwencje: implementation-record issue per task (szablon #18), `enhancement`+`needs-testing`,
ŻAR = `frontend/front-v2` (build na .61: `sudo npm run build`), zmiany backendu wymagają
`docker compose -f docker-compose.dev.yml up -d --build backend`. Zmiana zasad gracza w T2
(nowe opcje deklaracji obrony) → dopisek w Księdze Zasad `/rules/` w tym samym PR.
