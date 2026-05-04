# Agenda dyskusji — kolejność tematów

Spotkania można dzielić na sesje 60–90 min. Po każdej sesji: wpisać uchwały do [`04_decisions_log.md`](04_decisions_log.md).

**Lista „co jeszcze nie jest domknięte” (uchwały proposed, częściowe, [AUDIT], bloki agendy):** [`08_open_decisions_checklist.md`](08_open_decisions_checklist.md).

**Bieżący tryb (2026-05):** jedna sesja = jeden blok z listy poniżej; omawiamy **punkt po punkcie**, bez przeskakiwania do implementacji kodu. Asystent aktualizuje pliki fazy po każdej zamkniętej porcji ustaleń.

---

## Sesja 0 — Słownik (15 min)

**Cel:** Ustalić, co znaczy „pole jest używane w grze”.

- **Wariant A:** tylko kod deterministyczny (walka, `resolve_roll`, walidatory).
- **Wariant B:** A + dozwolone interpretacje GM/LLM według opisów w `config_service`.
- **Wariant C:** wszystko, co widzi gracz w UI.

**Wyjście:** Jedno zdanie-definicja w [`00_brief.md`](00_brief.md) (sekcja do dopisania) + wpis w `04_decisions_log.md`.

---

## Sesja 1 — Broń (`game_config_weapons`)

### Kontekst (bez żargonu)

Przy uderzeniu gra potrzebuje: **jaką kością** liczyć obrażenia oraz **która cecha postaci** (np. siła czy zwinność) jest do tego dodawana. Przy broni w bazie są też pola typu: **zwinność (finesse)**, **dwuręczność**, **typ** (wręcz / dystans / magia), **zasięg w metrach**. Chodzi o to, czy to już **zmienia liczenie i zasady**, czy na razie tylko **utrwala fakt**, żeby opowieść i Mistrz Gry (AI) nie podawali sprzecznych informacji.

### Pytania — wersja do rozmowy z graczem / projektantem

1. **Broń „zwinna”:** Czy do obrażeń ma iść **lepsza z dwóch cech** (typowo siła *albo* zwinność), czy na razie zawsze jedna ustalona cecha zapisana przy broni?
2. **Dwuręczna:** Czy ma **realnie coś blokować** (np. druga ręka zajęta, brak tarczy), czy na razie tylko **opis**, bez twardych konsekwencji w liczeniu?
3. **Wręcz / dystans / magia:** Czy typ broni ma **zawsze pasować** do rodzaju ataku (żeby nie było łuku liczonego jak miecz), czy na razie liczy się **to, co gra już robi**, a typ służy **spójności opowieści**?
4. **Zasięg w metrach:** Czy ma w przyszłości **sam z siebie** decydować „za blisko / za daleko”, czy na razie to **pewna liczba metrów w świecie gry** (żeby nikt nie halucynował), a trafienie i tak rozstrzyga obecna mechanika?
5. **Priorytet:** Co jest **„musimy to wdrożyć w programie w następnej porządnej rundzie”**, a co może zostać na później jako **opis i klimat**?

### Pytania — skrót techniczny (dla kodu / macierzy)

1. Czy `finesse` ma zmieniać sposób liczenia modyfikatora obrażeń (np. max(STR, DEX)) zamiast samego `linked_stat`?
2. Czy `two_handed` wymaga drugiej ręki / blokuje tarczę / zmienia sloty w ekwipunku?
3. Jak `weapon_type` (melee / ranged / spell) łączy się z testami ataku (`melee_attack` vs `ranged_attack` vs `spell_attack` w `dice.py`)?
4. Czy `range_m` ma wejść do przyszłych rzutów zasięgu, czy zostaje opisem dla LLM?
5. Które pola są **must-implement** w następnej fazie kodu, a które **flavor**?

**Wyjście:** Tabela decyzji per kolumna w `04_decisions_log.md`.

---

## Sesja 2 — Przedmioty (`game_config_items`)

### Kontekst (bez żargonu)

Przy każdym przedmiocie w „księdze” bazy mogą być: **typ** (pancerz, mikstura…), **cena**, **bonus do pancerza**, **opis efektu** (np. leczenie), czasem **dowolny blok JSON** oraz **dozwolone klasy** postaci. Trzeba ustalić: **co jest tylko opisem dla opowieści**, a **co ma wpływać na liczby w grze** — i czy dwa sposoby zapisu efektu (proste pola vs JSON) mają żyć obok siebie, czy jeden z nich ma być docelowo główny.

### Pytania — wersja do rozmowy

1. **Dwa zapisy efektu:** Czy **proste pola** (rodzaj efektu, kość, bonus, cel) mają być **tym**, co gra liczy przy miksturach itd., a **JSON** — na rzeczy specjalne (unikalne przedmioty), czy odwrotnie, czy wszystko ma iść w **jeden** sposób?
2. **Sztywny schemat:** Czy chcesz, żeby przy zapisie w panelu admin **system pilnował** poprawnego formatu (żeby nie wklejono przypadkiem śmieci)?
3. **Bonus pancerza:** Czy **liczba AC** z przedmiotu ma **sama podbijać obronę** postaci w programie, czy na razie tylko **pokazuje się w opisie** i w tekście dla Mistrza Gry?
4. **Klasy postaci:** Kiedy **„tylko dla wojownika”** ma **blokować** — przy tworzeniu postaci, przy zakupie, przy założeniu, przy użyciu?

### Pytania — skrót techniczny

1. Jaka jest rola `effect_json` vs zestawu `effect_type` / `effect_dice` / `effect_bonus` / `effect_target`?
2. Czy planujemy **jeden schemat JSON** (np. bonus do testu, raz na scenę, aktywacja) + walidację przy zapisie?
3. `ac_bonus` — czy ma kiedykolwiek wpływać na automatyczny AC w silniku, czy tylko na tekst katalogu / narrację?
4. `allowed_classes` — kiedy jest egzekwowane (tworzenie postaci, noszenie, użycie)?

**Wyjście:** Uchwały w `04_decisions_log.md` + wiersze w [`06_schema_gaps.md`](06_schema_gaps.md) jeśli widać brak kolumn.

---

## Sesja 3 — Statystyki (`game_config_stats`)

### Kontekst (bez żargonu)

**Statystyki** to liczby na karcie postaci (siła, zwinność, inteligencja itd.). W „księdze” gry jest **lista dozwolonych cech** z krótkimi opisami. Od tego zależy m.in. **modyfikator** do rzutów (np. siła do uderzenia). Trzeba ustalić: czy **tylko** to, co jest w tej liście, może pojawić się na karcie, i co się dzieje, gdy chcecie **dodać nową** cechę (np. „Wola”).

### Pytania — wersja do rozmowy

1. Czy **wyłącznie** cechy zapisane w konfiguracji mogą być na karcie postaci — **żadnych** „wymyślonych na boku” bez aktualizacji gry?
2. Gdy dodajecie **nową** cechę: czy traktujecie to jak **aktualizację całej gry** (nowa wersja zasad + ewentualnie zmiany w programie tam, gdzie cecha wchodzi w rzuty)?

### Pytania — skrót techniczny

1. Czy lista statów w DB jest **jedynym** dozwolonym zestawem kluczy w arkuszu?
2. Dodanie nowego statu — obowiązkowa aktualizacja `dice.py` / arkusza / UI?

**Wyjście:** Uchwała w `04_decisions_log.md` (np. **[S3]**).

---

## Sesja 4 — Umiejętności (`game_config_skills`) vs `dice.py`

### Kontekst (bez żargonu)

Na karcie masz **umiejętności** (np. skradanie, medycyna) z **rangą** (jak bardzo jesteś w tym dobry). Przy rzucie „test skradania” gra musi wiedzieć: **która cecha** (np. zwinność) dodaje się do rzutu — i **jaki jest sufit** rangi. Dziś część tego siedzi w **bazie** (lista umiejętności + powiązanie z cechą), a część jest **na stałe wpisana w program** przy konkretnych nazwach testów. Jeśli te dwie rzeczy się **rozjeżdżają**, gracz może dostać **inne liczby**, niż myślał Mistrz Gry po edycji w panelu.

### Pytania — wersja do rozmowy (z przykładami)

1. **„Która cecha do skradania?”**  
   Wyobraź sobie: w panelu admina przy umiejętności **Skradanie** zmieniasz powiązanie z **zwinności** na **inteligencję** (bo tak chcecie w zasadach).  
   **Pytanie:** Czy po zapisaniu w bazie **gra przy rzucie na skradanie** ma **od razu** używać inteligencji — czy dopóki ktoś nie zaktualizuje **drugiego miejsca** (program), dalej liczy się stara zwinność?  
   *(Innymi słowy: czy **jedna prawda** ma być w bazie, czy dalej dopuszczacie dwa niezależne zapisy?)*

2. **Sufit rangi**  
   W konfiguracji jest np. „maksymalna ranga tej umiejętności = 5”.  
   **Pytanie:** Czy program ma **zatrzymać** gracza, który próbuje wystawić rangę **6** (np. przy awansie), czy na razie wystarczy **ostrzeżenie w opisie** / u Mistrza Gry?

3. **Nowa umiejętność w świecie gry**  
   Dodajecie np. **Żeglarstwo** jako pełnoprawną umiejętność.  
   **Pytanie:** Jaki jest **minimalny zestaw kroków**, żeby wszystko było spójne — np. najpierw wpis w „księdze”, potem test w grze, potem opis w instrukcji? Co **musi** być zrobione, żebyście nie mieli „umiejętności widocznej w panelu, ale niewidocznej przy rzucie”?

### Pytania — skrót techniczny

1. Czy `linked_stat` w DB ma być **źródłem prawdy**, a `SKILL_STAT_MAP` generowany / walidowany przy buildzie?
2. Czy `rank_ceiling` z DB musi być egzekwowany przy awansie (API postaci)?
3. Nowa umiejętność — procedura (klucz w DB + wpis w mapie + test)?

**Uwaga:** To jest **główka architektoniczna** — rezerwuj więcej czasu.

**Wyjście:** Uchwała w `04_decisions_log.md` (np. **[S4]**).

---

## Sesja 5 — DC (`game_config_dc`)

### Kontekst (bez żargonu)

**DC** to próg liczbowy do pokonania rzutem. W bazie macie **nazwy** (łatwe, trudne…) i **liczby** przypisane do każdej nazwy. Chodzi o to, czy Mistrz Gry może mówić „to będzie trudne”, ale **faktyczna liczba** zawsze pochodzi z **jednej tabeli** — i czy słowa **łatwy/trudny** w ogóle się pojawiają, dopiero gdy **jest** rzut, a nie przy samej opowieści bez testu.

### Pytania — wersja do rozmowy (z przykładem)

1. Gracz chce **podkraść się** do strażnika. W narracji: dużo światła, żwir na ziemi — wygląda na **trudny** test. Czy po ustaleniu, że to **Skradanie**, mechanika ma wziąć liczbę z wiersza **„trudny”** w konfiguracji, a nie liczbę wymyśloną przez model?
2. Czy **jedna** tabela w systemie ma być **jedynym** miejscem, gdzie żyją te liczby (żeby zmiana w adminie od razu zmieniała grę)?
3. Czy **łatwy / średni / trudny** używacie **tylko wtedy**, gdy naprawdę robicie **rzut** — a jeśli LLM uzna, że to tylko opowieść bez testu, **nie** mapujecie tego na DC?

### Pytania — skrót techniczny

1. Czy `game_config_dc.value` jest **źródłem prawdy** przy mapowaniu `key` (np. `hard`) → DC w `resolve_roll`?
2. Czy automatyczny wybór DC „z trudności sceny” jest w scope, czy na razie zawsze **jawny** wybór klucza DC po stronie procedury/LLM zgodnie z **[S5]**?

**Wyjście:** Uchwała w `04_decisions_log.md` (**[S5]**); opisy umiejętności vs LLM — **[S5a]**; wrogowie vs karta gracza — **[S5b]** (otwarte).

---

## Sesja 6 — Warunki i konsumable

### Kontekst (bez żargonu)

**Warunki** to rzeczy typu „podpalony”, „wystraszony”, „trucizna kłuje co rundę” — coś, co **przykleja się** do postaci lub wroga i ma **skutek** w zasadach. W bazie jest zwykle **blok JSON** opisujący efekt. **Konsumable** to to, co **połykasz / zużywasz** (mikstura, żarcie z efektem). W projekcie macie **dwie ścieżki historyczne:** osobna stara tabela **konsumable** oraz **przedmioty** z typem „consumable” — trzeba ustalić, czy idziecie w **jeden katalog**, jak przy **[S2]** (JSON jako standard dla przedmiotów).

### Pytania — wersja do rozmowy

1. **Ten sam język co mikstury:** Gdy postać ma stan „**zatruty**” a mikstura **leczy truciznę** — czy **sposób zapisu** efektu warunku i sposób zapisu efektu mikstury mają być **z tej samej „księgi”** (jeden schemat), żeby program i admin nie musieli uczyć się dwóch dialektów? *(To jest powiązane z **[S2]** — JSON jako standard dla przedmiotów.)*

2. **Co warunek może robić:** Czy wyobrażacie sobie **te same rodzaje bonusów/kar** co przy przedmiotach (np. −2 do celnego strzału, obrażenia co turę), czy warunki mają **szerszy** zestaw (np. „nie możesz się ruszyć”, „musisz uciekać”) — i czy **wszystko** ma dać się zapisać w JSON-ie, czy część zostaje **tylko opisem dla LLM**?

3. **Dwa katalogi konsumable:** W systemie bywa **osobna tabela** konsumable i osobno **przedmioty-consumable**. Czy docelowo macie **jedną półkę** („wszystko co się zużywa jest **przedmiotem** z odpowiednim typem”), a druga tabela tylko **dla starych zapisów**, do wygaszenia — czy **świadomie** trzymacie dwa miejsca?

4. **Loot i sklep:** Gdy losujecie łup lub sprzedajecie miksturę — czy **ważne jest**, żeby **jeden** klucz (jedna nazwa w bazie) był wszędzie ten sam, żeby nie było „ta sama mikstura pod dwoma nazwami”?

### Pytania — skrót techniczny

1. Czy `game_config_conditions.effect_json` ma dzielić **schemat** z `game_config_items.effect_json` ([**S2**]) — jeden walidator?
2. Czy migracja docelowa to **wyłącznie** `game_config_items` (`item_type = consumable`) + deprecation `game_config_consumables`, zgodnie z kierunkiem w [`01_schema_inventory.md`](01_schema_inventory.md)?

**Wyjście:** Uchwała w `04_decisions_log.md` (np. **[S6]**); ewentualnie wiersze w [`06_schema_gaps.md`](06_schema_gaps.md).

---

## Sesja 6b — Luki w kolumnach (przedmioty, umiejętności, czary)

### Cel

Ustalić, czy w bazie **brakuje** kolumn (lub jest **nadmiar** martwych pól), żeby utrzymać **już uchwalone** mechaniki — patrz **[AUDIT]** w [`04_decisions_log.md`](04_decisions_log.md). Wynik trzymać w [`06_schema_gaps.md`](06_schema_gaps.md) (tabela + uwagi „schemat vs kod”).

### Kontekst (bez żargonu)

Macie **księgę** rzeczy w bazie i **program**, który z niej korzysta. Jeśli zasady mówią „DC z tabeli”, a kod **jeszcze** nie podstawia liczby z wiersza — to nie zawsze „brak kolumny”, czasem **luka w kodzie** — ale musi być **wpisana**, żeby przy wdrożeniu nic nie umknęło. To samo: **umiejętność dwuręczność**, **sufit rangi**, **czary vs broń** — czy da się to **zapisać** tam, gdzie trzeba, czy trzeba **nowego pola** albo **jednego JSON-u** zamiast dziesięciu kolumn.

### Pytania — wersja do rozmowy

1. **Przedmioty:** Przy każdym **typie** (pancerz, mikstura, przedmiot fabularny…) — czy **docelowy JSON** ([**S2**]) pozwoli zapisać wszystko, co ustaliliście (np. magia wymagana, AC, ładunki), bez obejść „tylko tekst dla LLM”?
2. **Umiejętności:** Czy do **[S1]** (dwuręczność) i **[S4]** (rangi, kara) macie w bazie **wszystkie haczyki** — np. **jednoznaczny klucz** umiejętności do dwuręczności, **sufit rangi** egzekwowalny przy zapisie postaci?
3. **Czary / magia:** Czy zostajecie przy **broni typu spell + przedmioty**, czy **przewidujecie** osobną tabelę — i czy obecny schemat **wystarczy** do AOE / pojedynczego celu ([**S1**])?
4. **Warunki:** Czy **[S6]** §2 (stany złożone **parametryzowane** w JSON) wymaga **nowych typów** w schemacie efektu — i czy macie je już wypisane jako checklistę w `06_schema_gaps`?

### Pytania — skrót techniczny

1. Porównać [`06_schema_gaps.md`](06_schema_gaps.md) z [`02_code_usage_matrix.md`](02_code_usage_matrix.md) — dla każdego „brak”: **migracja SQL** vs **tylko kod** vs **tylko prompt**.
2. Po Sesji 6b: ewentualny wpis domykający w `04_decisions_log.md`, jeśli pojawi się uchwała „**zamykamy AUDIT na ten moment**” (opcjonalnie).

**Wyjście:** Zaktualizowany [`06_schema_gaps.md`](06_schema_gaps.md); bez zmiany uchwał, chyba że odkryjecie **nową** decyzję merytoryczną.

---

## Sesja 7 — Eksport / import konfiguracji

### Cel

Ustalić **co jest „oficjalnym pakietem”** konfiguracji między środowiskami (dev → staging → prod), jak **wersjonować** bundle i jak unikać **dwóch prawd** — export JSON vs to, co faktycznie czyta gra.

### Kontekst z kodu (stan na przeglądzie)

W [`admin_config_transfer.py`](../../backend/app/services/admin_config_transfer.py) są **dwa** niezależne torby:

| Tor | Funkcje | Zakres tabel | Uwaga |
|-----|-----------|--------------|--------|
| **„Config”** | `export_config` / `import_config` | `stats`, `skills`, `dc`, opcjonalnie `weapons`, `enemies`, `conditions` | Import **nie obejmuje** `game_config_items`, lootu ani konsumable. Zapis broni w `import_config` używa **węższego zestawu kolumn** niż pełna migracja schematu — ryzyko **ucięcia** pól (np. finesse, zasięg), jeśli ktoś wdraża tylko ten tor. |
| **„Catalog snapshot”** | `export_catalog_snapshot` / `import_catalog_snapshot` | Szerszy zestaw: m.in. **`game_config_items`, `consumables`, loot_tables, loot_entries`, enemies**, … | Import przez `PRAGMA table_info` — **dynamicznie** wszystkie kolumny z JSON-a; `game_config_meta` w pliku jest **ignorowane** przy imporcie (komentarz w kodzie). |

**Wniosek roboczy:** Pełny „design katalogu” zgodny z **[S2]** / **[S6]** prawdopodobnie wymaga ścieżki **catalog snapshot**, nie samego `import_config` — do potwierdzenia w uchwale **[S7]**.

### Pytania — wersja do rozmowy

1. **Jeden pakiet:** Czy przy przenoszeniu świata gry między serwerami macie **jeden** uznawany format („ten ZIP / JSON to **kanon**”), czy dopuszczacie **dwa workflow** (np. „tylko podstawowe staty” vs „cały sklep i łupy”)?
2. **Co musi zawsze jechać razem:** Czy **przedmioty + loot + bronie + umiejętności + DC** mają być **niepodzielnym** pakietem — żeby nie było serwera ze „skillem skradania podłączonym pod DEX”, ale bez zaktualizowanej tabeli DC?
3. **Wersja zasad:** Pole `config_version` — czy podnosicie je przy **każdej** zmianie balansu, czy tylko przy **łamających** zmianach schematu?
4. **Bezpieczeństwo:** Import robi **DELETE + INSERT** na całych tabelach — czy akceptujecie „**zastępujemy całość**” (snapshot), czy potrzebujecie **merge** częściowy (trudniejsze)?

### Pytania — skrót techniczny

1. Czy **docelowy** deployment treści = **`import_catalog_snapshot`** (+ ewentualnie osobno meta), a `import_config` = **legacy / wąski** — do oznaczenia w docs?
2. Czy należy **zsynchronizować** `import_config` z pełnym INSERT-em broni / innymi tabelami, żeby nie **uciąć** kolumn przy pomyłce wyboru ścieżki?

**Wyjście:** Uchwała **[S7]** w `04_decisions_log.md`; wpisy w [`02_code_usage_matrix.md`](02_code_usage_matrix.md) i [`00_brief.md`](00_brief.md).

---

## Sesja 8 — Zamknięcie fazy

1. Przejrzeć `02_code_usage_matrix.md` — czy nie ma otwartych „nie znaleziono” dla krytycznych pól?
2. Uzupełnić `04_decisions_log.md`.
3. Zaktualizować [`player_rulebook/00_outline_and_tone.md`](player_rulebook/00_outline_and_tone.md) — rozdziały muszą odzwierciedlać **tylko** uchwały (nie przyszłe marzenia).

**Wykonano (2026-05-02):** Uchwała **[S8]**; macierz — nota o Sesji 8; outline przepisany (spis treści z mapowaniem na **[S0]–[S7]** / **[S8]**); kryterium ukończenia w [`00_brief.md`](00_brief.md).

---

## Checklista przed następną fazą implementacji

- [x] Broń: kierunek **[S1]** (finesse / 2h jako skill / typ / zasięg — wdrożenie w kodzie później).
- [x] Remis w konfrontacji — obrońca (**[S1c]**).
- [x] Przegląd luk — lista robocza **[AUDIT]** w [`06_schema_gaps.md`](06_schema_gaps.md) (domknięcie przy migracjach).
- [x] Przedmioty: JSON jako standard + LLM dla admina + pancerz w liczeniu + klasy/magia — **[S2]**.
- [x] Statystyki: LLM tylko przy istniejących cechach; nowa stat = wersja zasad — **[S3]**.
- [x] Umiejętności: sufit 5, XP, kara bez umiejętności, pierwszy wykup +1 — **[S4]** (zsynchronizować kod `dice.py` przy implementacji).
- [x] `linked_stat` w bazie = jedyne źródło prawdy dla cechy przy teście umiejętności — **[S4b]** (refactor `dice.py` przy implementacji).
- [x] DC — **[S5]** (słowa LLM, liczba z `game_config_dc`; łatwy/trudny dopiero gdy jest rzut); opisy skilli + LLM — **[S5a]**; wrogowie vs karta gracza — **[S5b]** (proposed, do późniejszej sesji).
- [x] Warunki + konsumable — **[S6]** (wspólny JSON z rozróżnieniem stan vs bonus przedmiotu; §2 zasada ogólna planowania stanów złożonych / tabel; ilustracja przerażenie; jeden typ rekordu dla zużywalnych; jeden `item_key` wszędzie).
- [x] Sesja 6b — konsolidacja [`06_schema_gaps.md`](06_schema_gaps.md) względem **[AUDIT]** i uchwał **[S1]–[S6]** (lista robocza uzupełniona; domknięcie AUDIT przy zamknięciu fazy / migracjach).
- [x] Eksport/import konfiguracji — **[S7]** + **[S7a]** (API jako wejście dla LLM; backup z retencją — do wdrożenia; jedna baza; snapshot dla pełnego katalogu; `config_version` bez podnoszenia przy każdej zmianie).
- [x] Player rulebook outline — **[S8]**; [`player_rulebook/00_outline_and_tone.md`](player_rulebook/00_outline_and_tone.md).

---

## Następny etap planowania (2026-05) — po **[S9]**, **[S10]–[S10c]**, **[S11]**

**Cel tego etapu:** przejść od **uchwał** do **konkretnych decyzji wdrożeniowych** (co budujemy w jakiej kolejności, jakie pola w DB, jakie API), bez rozrostu na „cały silnik naraz”.

**Wejście:** [`06_schema_gaps.md`](06_schema_gaps.md) (wiersze Kampania/LLM, XP grant MG, ewent. staty za XP); [`04_decisions_log.md`](04_decisions_log.md) **[S11]** (kierunek bez schematu).

### Blok A — Kampania i pamięć LLM (**[S11]**)

**Status (2026-05-03 / doprecyzowanie 2026-05-01):** MVP w kodzie — **[S11a]**. **Wizja i ustalenia szczegółowe** — **[S11b]** (m.in. timing planu po postaci, notatnik = tylko narracja, SoT = `campaign_turns`, dwa rekordy rollupu, cooldown multiplayer, W1/W2/W3, PATCH tylko admin/debug). **Do implementacji / strojenia:** automatyczny rollup (N tur), dywergencja LLM poza MVP, wybór **W1 vs W2**, flagi błędu rollupu w UI.

| Temat | Pytanie robocze | Wyjście |
|--------|------------------|---------|
| **Model danych** | Gdzie żyje roadmapa: `campaigns` JSON, osobna tabela, rozszerzenie istniejących flag? | **[S11a]** + **[S11b]**: plan w `gm_plan_json` (prywatny względem API gracza); rollup **dwa rekordy**; opcjonalnie tabela beatów (**W2**) |
| **Granica odcinka** | Czy **znacznik końca sceny** jest przyciskiem w UI, komendą gracza, oboma? | Zachowanie produktowe + ewent. pole `scene_id` / timestamp |
| **Rolling summary** | Kiedy generować: co N tur, po walce, na żądanie MG? Kto płaci tokeny (job vs sync)? | Model rollupu bez zmiany filozofii; cooldown w multiplayer (**[S11b]**); koszty — strojenie |
| **Dywergencja** | Minimum na start: tylko **tekst w promptcie** („plan mówił o X, gracz idzie w Y”) vs osobny krok LLM? | MVP **[S11a]**; rework planu przy silnym odejściu — **[S11b]**; heurystyka / drugi LLM — backlog **[S11]** |

### Blok B — XP w operacji (**[S10b]**, **[S10c]**)

**Status (2026-05-03):** MVP **[S10d]** — tabela `character_xp_grants`, `POST …/xp/grant-mg`, `GET …/xp/grant-log`, wyłącznie owner kampanii; LLM nie zapisuje XP. **Do decyzji później:** osobna rola GM, limity kwotowe w kodzie, LLM tylko „sugestia → akceptacja” w UI.

| Temat | Pytanie robocze | Wyjście |
|--------|------------------|---------|
| **Grant MG** | Endpoint admin / rola GM: kto może przyznać, czy zawsze `reason` + log w DB? | Spec API + ewent. migracja `xp_grant_log` |
| **LLM a XP** | Czy model **kiedykolwiek** sam dodaje XP, czy tylko **sugeruje** MG do zatwierdzenia? | Jedno zdanie w uchwale / brief |
| **Meta podpowiedzi** | Czy seedować `xp_award_guidelines` (JSON) w `game_config_meta` dla panelu — tak/nie? | Decyzja; opcjonalnie ticket |

### Blok C — Kolejność implementacji (MVP → kolejne fale)

**Status (2026-05-03):** uchwała **[IMPL]** — fale 1–7 (skrót w [`00_brief.md`](00_brief.md)); szczegół i uzasadnienie w [`04_decisions_log.md`](04_decisions_log.md).

Ustalić **nazwaną kolejkę** (np. 1. domknięcie **[S11]** pamięci w promptcie, 2. grant XP MG, 3. walidacja JSON przedmiotów **[S2]**, …) — żeby nie rywalizowały ze sobą dwa duże tematy bez priorytetu.

**Wyjście:** ~~krótka lista w [`00_brief.md`](00_brief.md) lub osobny akapit na końcu `04_decisions_log.md` („**[IMPL]** Kolejność fazy 9C”), **albo** tabela w `02_code_usage_matrix.md`~~ — **zrobione:** **[IMPL]** + brief.

### Blok D — Dokumentacja gracza (lekko)

Po zamknięciu bloków A–B: rozdział **„Awans / XP”** w [`player_rulebook/`](player_rulebook/) (nie szerzej niż **[S10b]** + **[S10c]** — bez obiecywania UI, którego nie ma).

### Sugerowana kolejność spotkań (60–90 min)

1. **Blok A** — bez implementacji SQL w trakcie spotkania; wynik = uchwała + zaktualizowany `06_schema_gaps`.
2. **Blok B** — krótszy; można połączyć z **Blokiem C** (pół sesji + pół).
3. **Blok C** — jedna sesja decyzyjna.
4. **Blok D** — redakcja asynchronicznie lub krótka sesja.

**Zasada:** każda zamknięta porcja → wpis w [`04_decisions_log.md`](04_decisions_log.md) (nawet krótki **[S11a]**, **[IMPL]**).

---

## Rozszerzone projektowanie (2026-05) — **`07_extended_design_spec.md`**

**Cel:** Zanim ruszą kolejne migracje, zamknąć **projektowo** luki z [`06_schema_gaps.md`](06_schema_gaps.md) (magia/AOE, JSON efektów, wróg vs PC, import, AC, kampania, XP statów).

**Wyjście:** przegląd → uchwały **[S12]–[S18]** ze statusem **accepted** (lub poprawka draftu); aktualizacja [`01_schema_inventory.md`](01_schema_inventory.md) po zmianie kolumn. *(**[S17]–[S18]** — accepted 2026-05-01.)*

---

## Sesja 9c — Admin UX vs SQL (krótka, 30–45 min)

**Cel:** Nie mylić **widoku w panelu** z **modelem bazy** — ustalić, co idzie na **[S15]** (accepted).

**Stan (2026-05-01):** **[S15]** → **accepted** w [`04_decisions_log.md`](04_decisions_log.md). Skrót: jedna tabela jeśli wystarcza; bez osobnej tabeli czarów; zakładki raczej stałe lecz łatwo rozszerzalne w UI; **ta sama mechanika** listy (edycja, sort, szukanie); brak widoku „cała tabela bez filtra”. Pancerz / items — nadal **[S2]** (zakładka = filtr na `game_config_items`).

### Pytania do uchwały

1. Czy lista **zakładek** katalogu (Czary / Broń / Pancerze / Zużywalne / …) jest **zamrożonym** zestawiem na MVP, czy tylko **presetami filtrów** na `weapon_type` / `item_type`?
2. Czy **pancerz** zawsze jest **`game_config_items`** z `item_type` + `ac_bonus`, a zakładka „Zbroje” tylko filtrem — zgodnie z **[S2]**?
3. Kiedy (jeśli w ogóle) dopuszczacie **drugą tabelę SQL** dla treści — według checklisty z §10 w [`07_extended_design_spec.md`](07_extended_design_spec.md)?

**Wyjście:** **[S15]** → **accepted** (2026-05-01); szczegóły w **[S15]**.

---

## Sesja 10 — Przebudowa klienta, design system, Figma (**[S16]**)

**Cel:** Uzgodnić **że** robicie przebudowę UI teraz + **jak** (stack, repo, milestone’y), tak aby zakładki admina (**[S15]**) były częścią **jednego** planu makiet, nie osobnego prototypu.

**Stan (2026-05-01):** **[S16]** → **accepted** w [`04_decisions_log.md`](04_decisions_log.md). Skrót: **1:1 z Figmą**; **Figma = źródło komponentów**; skok na nowy framework (**React** typowo przy Code Connect); **najpierw UI gracza**, admin może **legacy**; API **zamrażalne**; **nie** czekamy na pełne **[IMPL]** — start po stabilnym MVP kontraktu gracza; repo mono vs osobno — przy implementacji.

**Kolejność (dopisek):** implementacja nowego frontu / Figmy **na końcu** planu — nauka: [`09_figma_to_code_workflow.md`](09_figma_to_code_workflow.md).

### Pytania

1. **Framework i repo:** mono-repo z backendem vs osobny front — kryteria (deploy, zespół, CI).
2. **Figma:** Code Connect / inny proces — minimalny zestaw stron na MVP (gra solo + admin katalogów).
3. **Kolejność:** pierwszy „vertical slice” (np. tylko lista + edycja jednej tabeli + zakładki puste) zanim pełny redesign czatu?
4. **Powiązanie z [IMPL]:** która fala backendu może iść **równolegle**, co musi zostać dopiero po stabilnym API?

**Wyjście:** **[S16]** → **accepted** (2026-05-01); szczegóły §11 w [`07_extended_design_spec.md`](07_extended_design_spec.md).

---

## Sesja 11 — Azure OpenAI (**[S17]**) + centralizacja LLM (**[S18]**)

**Cel:** Domknąć konfigurację dostawcy chmurowego **oraz** zasadę **jednego miejsca** na źródło LLM (koniec rozproszenia: front, admin, testy).

**Stan (2026-05-01):** **[S17]** i **[S18]** → **accepted** w [`04_decisions_log.md`](04_decisions_log.md). Skrót: dev = **wspólny** endpoint; prod docelowo **własny** endpoint gracza po epiku **profil konta**; klucz **nie** przepisywany przy każdej sesji (zapis serwer + maska + zmiana przy rotacji); UI **Default vs Custom** (Custom wygrywa); **testy/CI** na mocku / env testowym. Implementacja w kodzie — osobne ticket’y.

### Pytania ([S17])

1. Format URL Azure (deployment + `api-version`) vs jedno pole „OpenAI-compatible base URL”.
2. Gdzie żyją sekrety (env-only vs przyszły Key Vault).
3. Czy kampanie mogą mieć **różne** deploymenty modeli — czy jeden globalny na środowisko na start?

### Pytania ([S18])

4. Czy **kampania** dostaje kiedykolwiek własny model — jeśli tak, pole w `campaigns` vs tylko dziedziczenie po użytkowniku?
5. Kolejność merge hierarchii (env → user → campaign) — jawna tabela w dokumentacji API.
6. Które istniejące pliki / endpointy dziś duplikują ustawienia — checklista refaktora.

**Wyjście:** **[S17]** i **[S18]** → **accepted** (2026-05-01); ticket’y: sterownik Azure, resolver LLM, UX klucza, testy z mockiem.

---

## Następna runda tematów do dyskusji (kolejność sugerowana)

Po zamknięciu **Sesji 9c–11** warto wrócić do mechaniki według **[IMPL]**:

| # | Temat | Powiązanie |
|---|--------|------------|
| 1 | Automat **`history/summary/ensure`** (fala 1 **[IMPL]**) | Kampania, koszt LLM |
| 2 | **[S12]** accepted → migracja `game_config_weapons` (`targeting`, …) | Magia / AOE |
| 3 | **[S13]** + walidator `effect_json` | Przedmioty, warunki |
| 4 | **[S7]** — dokumentacja „jednej ścieżki importu” w panelu | Operacje |
| 5 | Dywergencja **[S11]** v0 (heurystyka słów) | Prompt |

**Równolegle (nie blokuje mechaniki):** implementacja **[S17]** gdy środowisko Azure gotowe; **[S16]** według uzgodnionego timeline’u.

---

## Sesja 9d (opcjonalnie) — Widok „wszystkie rekordy” w adminie

**Cel:** Czy potrzebny jest **surowy** widok listy bez filtra (debug treści) obok zakładek **[S15]**?

**Wyjście:** tak/nie + kto ma uprawnienia (tylko admin globalny).
