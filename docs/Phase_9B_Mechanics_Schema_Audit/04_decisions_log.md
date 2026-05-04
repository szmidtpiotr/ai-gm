# Log uchwał (decisions log)

**Zasada:** jedna sekcja na uchwałę. Po spotkaniu dopisz datę i uczestników (opcjonalnie). Nie usuwaj starych wpisów — tylko dopisuj nowe, jeśli decyzja się zmienia, z odniesieniem do poprzedniej.

---

## Szablon wpisu

```markdown
### [SKRÓT] Tytuł uchwały — YYYY-MM-DD

**Status:** proposed | accepted | superseded

**Kontekst:** …

**Uchwała:** …

**Konsekwencje dla schematu / API / dokumentacji gracza:** …

**Powiązane pliki / tabele:** …
```

---

### [PROC] Tryb pracy dyskusji — 2026-05-02

**Status:** accepted

**Kontekst:** Ustalenia co do sposobu prowadzenia audytu z udziałem człowieka.

**Uchwała:** Przechodzimy tematy **punkt po punkcie** wg [`03_discussion_agenda.md`](03_discussion_agenda.md); uczestnik odpowiada i zadaje pytania; asystent stawia pytania pomocnicze i przedstawia **sugestie** wyraźnie je oznaczając. Wszystkie wiążące ustalenia dokumentujemy w `04_decisions_log.md`; definicje słownikowe w [`00_brief.md`](00_brief.md); macierz kodu w [`02_code_usage_matrix.md`](02_code_usage_matrix.md); outline gracza zgodnie z uchwałami w [`player_rulebook/00_outline_and_tone.md`](player_rulebook/00_outline_and_tone.md).

**Konsekwencje:** Brak zmian w kodzie w ramach samego trybu — tylko dyscyplina dokumentacji.

**Powiązane pliki:** [`00_brief.md`](00_brief.md) (sekcja „Tryb pracy zespołowej”)

---

### [S0] Definicja „używane w grze” dla `game_config_*` — 2026-05-02

**Status:** accepted

**Kontekst:** Sesja 0 — ustalenie słownika przed audytem kolumn.

**Uchwała:** `game_config_*` jest **używane w grze**, gdy służy **twardym zasadom mechaniki** albo **dostarcza LLM twardych danych** (żeby nie halucynował). Np. miecz przyznawany ze sklepu, z questu lub z łupu musi opierać się na rekordzie w bazie z konkretnymi statystykami / kluczem, a nie na wolnym opisie bez powiązania z katalogiem.

**Konsekwencje dla schematu / API / dokumentacji gracza:** Macierz [`02_code_usage_matrix.md`](02_code_usage_matrix.md) powinna dla każdej kolumny dać się zmapować na „mechanika / twardy kontekst LLM / ani jedno ani drugie (kandydat do uporządkowania)”. Tekst dla gracza opisuje **skutki** uchwalonych zasad, nie zachowanie modelu bez kotwicy w bazie.

**Powiązane pliki / tabele:** [`00_brief.md`](00_brief.md) (sekcja definicji); wszystkie `game_config_*`.

---

### [S1] Broń — kierunek mechaniki obrażeń, typ, zasięg, dwuręczność — 2026-05-02

**Status:** accepted (kierunek projektowy; szczegółowe liczby przy balansie)

**Kontekst:** Sesja 1 — ustalenia gracza/projektanta; faza developerska: projektować teraz, wdrożyć potem.

**Uchwała:**

1. **Obrażenia:** rzut kością broni + modyfikator cechy + bonusy. **STR** dla typowej broni wręcz (np. topór, miecz). **DEX** dla łuku, kuszy, bicza i podobnej broni dystansowej. (Mapowanie na pola w bazie / `linked_stat` przy implementacji.)
2. **Dwuręczność:** jako **umiejętność (skill)** — z umiejętnością dodatnie modyfikatory do broni 2H; **bez** umiejętności kary (ujemne modyfikatory; doprecyzowanie: do ataku vs obrażeń przy kodzie — **nie** mylić z DC jako progiem testu). **Tarcza lub broń w off-hand** wyklucza używanie dużego miecza 2H w ustalonym sensie.
3. **Typ broni** musi **pasować** do rodzaju ataku: wręcz (pięści, miecz, topór…), dystans (łuk, kusza, dmuchawka…), magia — w tym przypadek **pojedynczy cel** lub **AOE** (do zapisu w konfiguracji).
4. **Zasięg (`range_m`):** na ten moment **tylko** sprawdzanie, czy strzał/magia **doleciała** do celu (czy cel w zasięgu), bez pełnej taktyki.
5. **Kolejność implementacji w kodzie** nie jest ustalana — **wszystkie** te elementy mają finalnie trafić do produktu.

**Konsekwencje:** Dokumentacja gracza i LLM muszą trzymać się katalogu broni; przyszła implementacja: umiejętność „dwuręczność”, zgodność typu ataku z bronią, prosty model zasięgu. Przykłady liczb: [`player_rulebook/draft_formulas_and_examples.md`](player_rulebook/draft_formulas_and_examples.md).

**Powiązane tabele:** `game_config_weapons`; później `game_config_skills` (dwuręczność).

---

### [S1b] Trafienie vs obrona oraz testy przeciwstawne — 2026-05-02

**Status:** proposed → **część accepted** (kierunek), szczegóły procedury — **do dopracowania**

**Kontekst:** Pytanie uzupełniające: jedna mechanika trafienia dla wszystkich rodzajów ataku; testy np. skradanie vs percepcja/słuch.

**Uchwała (kierunek):**

- **Trafienie / obrona:** dążyć do **jednej czytelnej procedury** dla wręcz, dystansu i magii (żeby gracz nie uczył się trzech systemów). Dokładna formuła (np. atak vs jedna liczba obrony, reguły remisu) — **następna runda projektowa**; opis **stanu obecnego kodu** (unik wroga vs suma ataku) jest w szkicu przykładów. **Warianty typów rozstrzygnięć** (trafienie vs unik, czar vs counter itd.) — **[S1e]**.
- **Konfrontacje (np. skradanie vs wypatrywanie/słuch):** model **dwóch rzutów** (aktywny vs pasywny / obie strony) z porównaniem wyników.
- **Remis w konfrontacji dwurzutowej:** **[S1c]** — **korzyść obrońcy**. **Remis przy pojedynczym rzucie** (atak vs AC itd., poza pełną konfrontacją dwurzutową) — **[S1d]** (przerzut).

**Konsekwencje:** Rozdział w przyszłej instrukcji o walki i rozdział o konfrontacjach; opis remisu w [`player_rulebook/draft_formulas_and_examples.md`](player_rulebook/draft_formulas_and_examples.md).

**Powiązane pliki:** [`player_rulebook/draft_formulas_and_examples.md`](player_rulebook/draft_formulas_and_examples.md) (sekcje 6–7).

---

### [S1c] Remis w konfrontacji — zawsze obrońca — 2026-05-02

**Status:** accepted

**Kontekst:** Doprecyzowanie po ustaleniach [S1b].

**Uchwała:** Gdy wyniki obu stron są **równe**, rozstrzygnięcie **zawsze na korzyść obrońcy** (pasywnej / wykrywającej strony).

**Konsekwencje:** Jedna linia w instrukcji gracza i spójne zasady w kodzie przy implementacji konfrontacji.

**Powiązane pliki:** [`player_rulebook/draft_formulas_and_examples.md`](player_rulebook/draft_formulas_and_examples.md).

---

### [S1d] Remis przy pojedynczym rzucie (atak vs obrona / unik) — poza konfrontacją dwurzutową — 2026-05-03

**Status:** accepted (uzupełnia **[S1b]**; nie zmienia **[S1c]** dla konfrontacji dwóch rzutów)

**Kontekst:** **[S1c]** dotyczy **remisu w konfrontacji** (dwa rzuty, strona pasywna). Osobno: remis przy **jednym** rzucie rozstrzygającym vs liczbą obronną (np. trafienie vs AC), bez pełnej pary przeciwstawnych rzutów w tej samej procedurze.

**Uchwała:** W takiej sytuacji **dopuszcza się powtórzenie rzutu** (szczegół: który rzut się powtarza — atak, obrona czy oba — **instrukcja gracza + implementacja**). **Konfrontacje** dwustronne nadal według **[S1c]** (korzyść obrońcy przy remisie).

**Konsekwencje:** Aktualizacja [`player_rulebook/draft_formulas_and_examples.md`](player_rulebook/draft_formulas_and_examples.md) (walka); kod `combat_service` / `dice` — przy wdrożeniu taktyki.

---

### [S1e] Warianty rozstrzygnięć (trafienie vs unik, czar vs counter itd.) — 2026-05-03

**Status:** accepted (kierunek produktowy; mapowanie na kod — iteracja)

**Kontekst:** Użytkownik: nie jedna sztywna para dla wszystkich sytuacji — m.in. **trafienie vs unik**, **czar vs counterspell** itd. powinny mieć **rozróżnione** procedury tam, gdzie zasady tego wymagają.

**Uchwała:** Docelowo **kilka nazwanych ścieżek** rozstrzygnięcia (klucz typu sytuacji → procedura: co się rzuca, czym porównujemy, czy konfrontacja, czy DC). Szczegół tabeli / enum w kodzie i w katalogu — przy implementacji **[S1b]** bez **sztucznego** szycia wszystkiego do jednej formuły, jeśli zasady fabularne i balans wymagają rozdziału.

**Konsekwencje:** Rozbudowa macierzy w [`02_code_usage_matrix.md`](02_code_usage_matrix.md); dokumentacja gracza — sekcja „rodzaje testów / rozstrzygnięć”.

---

### [AUDIT] Luki w kolumnach — przedmioty, umiejętności, czary — 2026-05-02

**Status:** **closed (proces T11, 2026-05-04)** — lista w [`06_schema_gaps.md`](06_schema_gaps.md) **zsynchronizowana** z repozytorium: każdy wiersz ma kolumnę **T11** (zgodne / częściowo / otwarte z odnośnikiem do backlogu **T12** lub fal **[IMPL]** **T16–T19**). **Wersja katalogu w runtime:** `game_config_meta.config_version` (seed **1.0.0**); numeracja **łańcucha migracji** = kolejność w [`migrations_admin.py`](../../backend/app/migrations_admin.py) / bootstrap w [`main.py`](../../backend/app/main.py).

**Kontekst:** Przed migracjami trzeba ustalić, czy w schemacie **nie brakuje pól** potrzebnych do opisanych mechanik (np. statystyki powiązane z typami przedmiotów, dodatkowe atrybuty umiejętności, pola pod czary / AOE / szkoły magii).

**Uchwała:** Przeprowadzić **przegląd** w oparciu o [`01_schema_inventory.md`](01_schema_inventory.md), [`02_code_usage_matrix.md`](02_code_usage_matrix.md) oraz uchwały (aktualnie **[S1]–[S6]**); wypisać **listę braków lub nadmiarów** (kolumna nieużywana vs brak kolumny pod planowaną mechanikę). Wynik zapisać w [`06_schema_gaps.md`](06_schema_gaps.md).

**Konsekwencje:** **Przegląd zamknięty** — nierozwiązane punkty są **jawnie oznaczone** w [`06_schema_gaps.md`](06_schema_gaps.md) (nie zakładamy „braku luk”, jeśli kod ich nie realizuje). Migracje produktowe nadal wg kolejki [`11_MASTER_TASK_QUEUE_AND_PROMPTS.md`](11_MASTER_TASK_QUEUE_AND_PROMPTS.md).

**Powiązane tabele (start):** `game_config_items`, `game_config_skills`, bronie (`game_config_weapons`), `game_config_conditions`, `game_config_dc`, ewentualnie osobna tabela czarów jeśli powstanie.

---

### [S2] Przedmioty — JSON jako standard mechaniki, walidacja, pancerz, klasy — 2026-05-02

**Status:** accepted (kierunek produktowy; szczegół schematu JSON i UI — następna faza)

**Kontekst:** Sesja 2 — ustalenia dotyczące zapisu efektów przedmiotów, roli pancerza i ograniczeń klasowych.

**Uchwała:**

1. **Standaryzacja mechaniki w JSON:** Docelowo **jeden sposób** opisu mechaniki przedmiotu przez **`effect_json`** (lub równoważne pole) według **ustalonego schematu** — łatwiej utrzymać spójność niż równoległe „proste kolumny” i JSON. *(Migracja istniejących danych z `effect_type` / `effect_dice` / … — przy implementacji.)*

2. **Problem ręcznego wpisywania dla admina:** Ryzyko błędów składni / semantyki. **Propozycja produktowa (zaakceptowana jako kierunek):** mały **generator formuł JSON wspomagany przez LLM** — administrator opisuje **po polsku**, co przedmiot ma robić (np. mikstura: przywraca X HP **i** zmienia rodzaj ran z krytycznych na ciężkie, z ciężkich na lekkie); system **generuje** wstępną formułę w poprawnym schemacie; admin **weryfikuje** i wkleja do pola. *(Implementacja: osobna funkcja / endpoint / panel.)*

3. **Spójność:** Tak — **ważne**, żeby wszystko było zgodne ze schematem i walidowane (patrz pkt 2 i walidacja przy zapisie).

4. **Pancerz i rzuty:** Pancerz ma być **uwzględniany w procesie liczenia** (obrona / trafienie — dokładna formuła w kolejnej rundzie projektu walki). **Na teraz:** można modelować np. skórzaną zbroję jako **+1 do obrony „wszędzie”** (jedna liczba), **mając na uwadze rozwój:** później **podział na lokacje** (tułów, L/P noga, L/P ręka, głowa), **deklaracja ataku** w konkretną część, **modyfikatory szans** na traf w strefę — to **osobna dyskusja**, nie blokuje dzisiejszego uproszczenia.

5. **Klasy, magia, broń (użycie przedmiotu vs styl postaci):**
   - Postać **bez magii** (np. typowy wojownik) **nie może użyć** magicznego przedmiotu, który **wymaga użycia magii** do aktywacji.
   - **Mag** raczej nie będzie walczył **ciężkim toporem** w stylu wojownika — to kwestia **fabuły i profilu**, ale **kusza** (broń dystansowa) **może** być użyta; **czy trafi** — rozstrzyga **osobny rzut / mechanika**, nie zakaz klasy.
   - Rozróżnienie: **twarde blokady** (magia wymagana) vs **narracja / preferencja** (topór u maga) vs **trafienie** (osobno).

**Konsekwencje:** Należy zaprojektować **schemat JSON** + walidator; zaplanować **asystenta LLM** dla admina; w kodzie docelowo **parsowanie** efektów z JSON przy rozdziale na lokacje — etapami. Dokumentacja: [`player_rulebook/draft_formulas_and_examples.md`](player_rulebook/draft_formulas_and_examples.md) (sekcja uzupełniona).

**Powiązane tabele:** `game_config_items` (`effect_json`, `ac_bonus`, `allowed_classes`, …).

---

### [S3] Statystyki — LLM tylko w oparciu o istniejące cechy; nowa stat = nowa wersja zasad — 2026-05-02

**Status:** accepted

**Kontekst:** Sesja 3 — jak łączyć kreatywność LLM z twardą listą cech w konfiguracji.

**Uchwała:**

1. **LLM może wymyślać** ostateczne nazwy, opisy, etykiety umiejętności itd. — **pod warunkiem**, że **mechanicznie** wszystko jest **przypięte do już istniejącej statystyki** z konfiguracji (`game_config_stats` / klucze na karcie). Model **nie wprowadza** nowego **mechanicznego** atrybutu spoza listy — tylko **mapuje narrację** na ustalone filary (np. „Zimna krew” → nadal liczy się jako modyfikator od **DEX** lub **WIS**, zgodnie z projektem).

2. **Nowa statystyka w systemie** (nowy filar liczbowy) **zawsze** przechodzi jako **nowa wersja zasad** — jawna aktualizacja konfiguracji, ewentualnie kodu i dokumentacji. **Brak** dopisywania nowych statów „z halucynacji LLM” bez tego procesu.

**Konsekwencje:** Walidacja zapisu karty / promptów: odrzucenie lub mapowanie propozycji, które nie pasują do kluczy statów; pipeline wersjonowania zasad przy rozszerzeniu `game_config_stats`.

**Powiązane tabele:** `game_config_stats`; arkusz postaci; prompty LLM.

---

### [S4] Umiejętności — rangi, sufit 5, XP, kara za brak umiejętności, pierwszy wykup — 2026-05-02

**Status:** accepted (kierunek mechaniki; dokładne liczby bonusów i kosztów XP — balans / implementacja)

**Kontekst:** Sesja 4 — odpowiedzi na modele rang i kar.

**Uchwała:**

1. **Sufit rangi:** Najwyższy poziom umiejętności to **5** (`rank_ceiling` = 5 w konfiguracji jako górne ograniczenie).

2. **Poziom 5 vs bonusy i XP:** Najwyższy poziom ma dawać **większy bonus niż +5** (w sensie **modyfikatora z samej rangi umiejętności** — dokładna skala przy balansie), przy czym **wykup** tego poziomu ma **kosztować znacznie więcej punktów XP** niż niższe stopnie.

3. **Deklaracja umiejętności bez posiadania:** Gracz, który **deklaruje** użycie umiejętności (np. skradania), **nie posiadając** jej na karcie, otrzymuje **ujemne modyfikatory** do testu („udaje, że umie”).

4. **Brak „poziomu 0” de facto:** W praktyce nie ma neutralnego „rang 0”; albo jest **kara** (brak umiejętności przy deklaracji / próba bez treningu), albo **pozytywne rangi** **1, 2, 3, …** aż do **5**. *(Mapowanie na zapis w arkuszu: uniknąć sytuacji „0” jako pełnoprawnej rangi z zerowym bonusem — doprecyzowanie przy implementacji UI.)*

5. **Pierwszy wykup:** Gdy umiejętność zostaje **wykupiona** (pierwszy raz), **bazowo** daje **+1** do testów z nią związanych (pierwsza ranga = +1 jako punkt wyjścia — kolejne rangi według tabeli balansu).

**Uwaga odniesienia do kodu:** Obecny silnik rzutów (`dice.py`) może używać innej skali (np. inna reguła „proficiency”) — **należy zsynchronizować** przy wdrożeniu z tą uchwałą.

**Konsekwencje:** Tabela bonusów rang 1–5, krzywa kosztów XP, walidacja „nie masz umiejętności → kara”; aktualizacja `game_config_skills` i logiki postaci. Szkic przykładów: [`player_rulebook/draft_formulas_and_examples.md`](player_rulebook/draft_formulas_and_examples.md).

**Powiązane tabele:** `game_config_skills` (`rank_ceiling`, `linked_stat`); arkusz postaci (`skills`); przyszła tabela / pola kosztów XP jeśli powstaną.

---

### [S4b] Umiejętności — `linked_stat` w bazie jako jedyne źródło prawdy — 2026-05-02

**Status:** accepted

**Kontekst:** Domknięcie Sesji 4 — pytanie: czy konfiguracja w bazie ma decydować, która **cecha** dodaje się do rzutu przy danej umiejętności.

**Uchwała:** **Tak.** Pole **`linked_stat`** w `game_config_skills` jest **źródłem prawdy**: przy rozstrzyganiu testu umiejętności program ma **czytać powiązanie cecha ↔ umiejętność z bazy** (lub z runtime config ładowanego z bazy), a **nie** polegać na osobnej, ręcznie utrzymywanej mapie w kodzie, która mogłaby się rozjechać z panelem admina.

**Konsekwencje:** Refactor `dice.py` (np. `SKILL_STAT_MAP`) tak, by **dynamicznie** korzystać z `game_config_skills` albo by mapa była **generowana / walidowana** przy buildzie z eksportu DB; testy regresji po zmianie `linked_stat` w adminie.

**Powiązane pliki kodu:** [`backend/app/services/dice.py`](../../backend/app/services/dice.py); [`backend/app/services/config_service.py`](../../backend/app/services/config_service.py); [`game_config_skills`](../../backend/app/migrations_admin.py).

---

### [S5] DC (`game_config_dc`) — słowa od LLM, liczba z jednej tabeli — 2026-05-01

**Status:** accepted

**Kontekst:** Sesja 5 — kiedy używać poziomów łatwy / średni / trudny i skąd bierze się **konkretna liczba** DC.

**Uchwała:**

1. **Jedno wspólne miejsce w systemie:** Wartości liczbowe progów (np. łatwy = X, trudny = Y) żyją **wyłącznie** w konfiguracji **`game_config_dc`** (`key` → `value`). Zmiana w panelu admina ma **propagować** się wszędzie tam, gdzie mechanika odwołuje się do **tego samego** klucza (np. `hard`), a nie do „wpisanej na sztywno” liczby w wielu tekstach.

2. **LLM mówi po ludzku, silnik bierze liczbę z tabeli:** Gdy Mistrz Gry (model) uzna, że sytuacja jest **trudna** (a nie łatwa), **narracja** może używać słów („trudny test na Skradanie”, opis światła i żwiru). **Mechanika** przy faktycznym rzucie **musi** rozwiązać **trudny** → **konkretne `value`** z wiersza `hard` (lub odpowiedniego klucza) w `game_config_dc`. **Zabronione** jest wymyślanie nowej liczby DC przez model zamiast odwołania do tej tabeli — zgodnie z duchem **[S0]** i **[S3]** (brak halucynacji twardych liczb).

3. **Kiedy w ogóle używamy łatwy / trudny:** Etykiety DC mają znaczenie **dopiero wtedy**, gdy **odbywa się rzut** — czyli gdy LLM (lub procedura) uzna, że **potrzebny jest test**. Jeśli akcja zostaje **czystą narracją** bez testu, **nie** mapujemy jej na poziom DC.

**Konsekwencje:** Pipeline rozstrzygania akcji: (a) czy to test? → jeśli tak, (b) który **klucz DC** (łatwy/średni/trudny/…) → (c) podstawienie **`value`** z `game_config_dc` do `resolve_roll` / równoważnej ścieżki. Dokumentacja i prompty: model **nie zastępuje** tabeli własną liczbą.

**Powiązane tabele:** `game_config_dc`; [`02_code_usage_matrix.md`](02_code_usage_matrix.md) (sekcja DC).

---

### [S5a] Umiejętności — `description` + katalog w kontekście LLM (test vs sama opowieść) — 2026-05-01

**Status:** accepted (kierunek produktowy; szczegół promptów — przy implementacji)

**Kontekst:** Pytanie, czy samo pole **`description`** (wraz z innymi polami rekordu umiejętności) wystarczy, żeby (1) gracz rozumiał, **co robi umiejętność**, oraz (2) LLM wiedział, **kiedy** zastosować test oparty o umiejętność z bazy (z **`linked_stat`** itd.) zamiast samej narracji bez rzutu.

**Uchwała:**

1. **Cel:** Przy deklaracji akcji przez gracza system ma **rozróżniać** „wymaga testu (umiejętność z katalogu)” vs „tylko narracja” — przy czym **lista umiejętności i ich opisy** pochodzą z **`game_config_skills`** (min. `key`, `label`, `description`, `linked_stat`), ładowane do **runtime config** i **dostarczane do kontekstu LLM** (oraz do UI / instrukcji gracza). **Nie** opieramy się na „pamięci” modelu bez kotwicy w bazie.

2. **Rola `description`:** Jest **głównym** tekstem wyjaśniającym **charakter** umiejętności — zarówno dla gracza, jak i jako materiał dla Mistrza Gry do decyzji „czy ten katalogowy test pasuje do sytuacji”. Redakcja opisów w adminie jest **częścią projektu zasad**, nie tylko ozdobnikiem.

3. **Rezerwa:** Jeśli w praktyce okaże się, że sam `description` jest niewystarczający (np. brak jednoznacznych **wskazówek kiedy** testować), **następna iteracja** może dodać pole pomocnicze (np. „typowe zastosowania / kiedy rzucać”) albo **szablon promptu** łączący katalog z procedurą — **bez** wprowadzania nowych „umiejętności” poza bazą.

**Konsekwencje:** Implementacja: zawsze **wstrzykiwać** aktualny wycinek `game_config_skills` (lub ekwiwalent) do promptów decyzyjnych; traktować **`description`** jako pole do utrzymania pod kątem LLM + gracza. Ewentualne luki — wpisać w [`06_schema_gaps.md`](06_schema_gaps.md) po testach.

**Powiązane tabele:** `game_config_skills`; prompty / `config_service`.

---

### [S5b] Wrogowie — ta sama „logika karty” co gracz? Generator z opisu? — 2026-05-01

**Status:** superseded — szczegóły zamykające w **[S14]** (**accepted**, 2026-05-01).

**Kontekst:** Pytanie, czy tabela **`game_config_enemies`** (lub model wroga w grze) powinna być **zbudowana jak uproszczona karta postaci** (te same pola / konwencje), żeby **łatwiej testować** i utrzymywać spójność — oraz czy **generator** wroga z opisu tekstowego (admin + LLM, analogicznie do pomysłu z przedmiotami w **[S2]**) jest pożądany.

**Uchwała (historyczna — przed [S14]):** **Na razie nie zamykamy.** Kierunek do **przeanalizowania** przy projekcie walki i narzędzi admina: (1) **standaryzacja** pól wroga względem karty gracza tam, gdzie to ma sens (HP, obrona, atak, cechy pomocnicze); (2) **narzędzie** „z opisu → szkic wroga” jako **opcjonalny** workflow — **po** ustaleniu minimalnego kontraktu danych i testów regresji.

**Konsekwencje (aktualne):** Patrz **[S14]** oraz [`07_extended_design_spec.md`](07_extended_design_spec.md) §5.

**Powiązane tabele:** `game_config_enemies`; arkusz postaci; generator admin (**[S20]**).

---

### [S6] Warunki (`effect_json`) i konsumable — wspólny język JSON, rozróżnienie stan vs bonus przedmiotu; jeden katalog przedmiotów — 2026-05-01

**Status:** accepted (kierunek projektowy; szczegół schematu JSON — przy implementacji razem z **[S2]**)

**Kontekst:** Sesja 6 — jak powiązać **stany** (podpalenie, strach, trucizna…) z **przedmiotami** i **miksturami**, oraz czy **jedna** ścieżka katalogowa dla zużywalnych rzeczy.

**Uchwała:**

1. **Wspólna „rodzina” formatu z przedmiotami ([S2]), ale nie mylić pojęć:** Efekty zapisane w **`game_config_conditions.effect_json`** powinny korzystać z **tego samego ogólnego schematu / słownika efektów** co **`game_config_items.effect_json`** (jeden walidator, jeden zestaw typów działań), **z zastrzeżeniem:** przedmiot może dawać np. **+3 do STR** jako **bonus wyposażenia / efektu trwałego** — to **nie jest** ten sam rodzaj rzeczy co **stan** („pod wpływem trucizny”), choć oba mogą być zapisane w **tym samym języku JSON**. W konfiguracji i w kodzie rozróżnia się **kategorię** (stan na postaci vs modyfikator z przedmiotu / buff).

2. **Zasada ogólna — konstrukcja rozwiązania i planowanie tabel / JSON:** Dla **wielu** różnych stanów (nie wyłącznie jednego przykładu) przyjmujemy **ten sam wzorzec projektowy**: stan złożony może wymagać **powtarzalnych testów**, odwołań do **poziomów DC z tabeli** (**[S5]**), **ograniczenia swobody deklaracji** gracza z **narracją LLM** oraz **warunków zdjęcia** stanu. **Schemat bazy** i **słownik typów w `effect_json`** planuje się tak, by te wzorce były **parametryzowalne** — jeden spójny język opisu, **wiele** wariantów zachowań — i żeby **unikać** osobnej kolumny SQL na każdą nazwę stanu, jeśli da się to wyrazić jako typ efektu + parametry w JSON-ie. Ta zasada obowiązuje przy **każdym** podobnym stanie (strach, szaleństwo, urok przymusu, itd. — według potrzeb zasad).

3. **Ilustracja (nie wyczerpuje listy) — przerażenie:** m.in. rzut **co rundę** na wybraną cechę; DC z poziomu **trudny** (**[S5]**); przy **niepowodzeniu** narracja LLM (np. ucieczka, utrata pełnej kontroli nad deklaracjami); **powrót kontroli** przez kolejny trudny test na tę cechę lub inną uzgodnioną procedurę; dopóki stan trwa, Mistrz Gry może prowadzić postać zgodnie z opisem. Szczegół rund i liczb — **balans i implementacja**; punkt §2 określa **jak** takie przypadki wpisywać do planu tabel, nie tylko ten jeden.

4. **Konsumable — jeden rodzaj rekordu:** Docelowo **wszystkie** zużywalne rzeczy (mikstury itd.) są **przedmiotami** w **`game_config_items`** z odpowiednim **`item_type`** (np. `consumable`). Osobna tabela **`game_config_consumables`** traktowana jako **legacy** — do **wygaszenia** po migracji danych i odwołań (loot, sklep, ekwipunek).

5. **Jeden klucz (`key`) wszędzie:** Ten sam przedmiot musi być **identyfikowany jednym kluczem** niezależnie od źródła — **łup, sklep, quest, nagroda** — żeby nie powstały duplikaty „ta sama mikstura pod dwoma nazwami”.

**Konsekwencje:** Rozbudowa **jednego schematu JSON** o typy efektów (w tym **parametryzowalne** stany złożone wg §2) dla warunków i przedmiotów; pole **`effect_category`** lub równoważne rozróżnienie w JSON / meta — przy implementacji. Migracja **`game_config_consumables` → `game_config_items`**; aktualizacja `loot_entries`, sklepów, questów do jednego **`item_key`**. Dokumentacja gracza: rozdział o stanach i o zużywalnych — [`player_rulebook/draft_formulas_and_examples.md`](player_rulebook/draft_formulas_and_examples.md).

**Powiązane tabele:** `game_config_conditions`; `game_config_items`; `game_config_consumables` (legacy); `game_config_loot_entries`; por. **[S2]**, **[S5]**.

---

### [S7] Eksport / import konfiguracji, snapshot katalogu dla LLM, backup — 2026-05-02

**Status:** accepted (kierunek produktowy i bezpieczeństwa; szczegół endpointów — przy implementacji)

**Kontekst:** Sesja 7 — po czym przenosi się świat gry między środowiskami; jak pracuje **zewnętrzny LLM** tworzący treści (przedmioty, wrogowie, lokacje); czy osobna baza; merge vs pełny replace.

**Uchwała — treść merytoryczna:**

1. **`export_catalog_snapshot` jako główny nośnik dla LLM:** Eksport **pełnego katalogu** (JSON ze spójnym zestawem tabel) służy **przede wszystkim** do **wymiany kontekstu z innym LLM / generatorem treści** (przedmioty, wrogowie, lokacje — z powiązaniami). Docelowo **generator LLM** po stronie admina **ograniczy** ręczne obchodzenie eksportów. **`export_config` / `import_config`** pozostają **węższą** ścieżką (rdzeń: stats, skills, dc, opcjonalnie broń, wrogowie, warunki — **bez** m.in. pełnego zestawu przedmiotów i lootu w standardowym polu `tables`).

2. **Eksport i import razem:** Przy generowaniu treści (np. lokacje odnoszące się do NPC i ich przedmiotów) **zazwyczaj** przekazujecie **spójny pakiet** eksport → obróbka → import / merge, żeby **nie rozjeżdżały się klucze i FK** między tabelami.

3. **`config_version`:** **Nie** podnosicie numeru wersji przy każdej drobnej zmianie treści — uchwała utrwala tę politykę (inne śledzenie zmian może iść przez git eksportów / audyt / datę eksportu).

4. **Merge vs kasowanie vs pełny rebuild:** Nie ma **jednej** sztywnej reguły na zawsze — zależy od sytuacji: czasem **uzupełnianie** brakujących kolumn przez eksport → LLM → **merge** z powrotem; czasem **usunięcie** wierszy lub **odtworzenie** całej bazy „od zera” po awarii — **akceptowalne** jako świadomy koszt operacyjny. Implementacja ma umożliwiać **obe scenariusze** stopniowo (walidacja, dry-run, snapshot przed importem).

5. **Ścieżka „kanoniczna” dla pełnego katalogu treści:** Przy wdrażaniu **kompletu** definicji (zgodnie z **[S2]**, **[S6]** — przedmioty, loot, bronie z pełnym zestawem kolumn) **źródłem prawdy dla importu** jest **`import_catalog_snapshot`** (dynamiczny INSERT wg kolumn z migracji), **nie** wąski `import_config`, który przy broni **uciąć może** nowsze pola — patrz [`06_schema_gaps.md`](06_schema_gaps.md). `import_config` traktować jako **ostrożnie**: szybki rdzeń lub legacy, dopóki INSERT-y nie zostaną zsynchronizowane z pełnym schematem.

**Sugestie architektoniczne (do decyzji implementacyjnej — nie zastępują osobnego projektu bezpieczeństwa):**

- **Nie udostępniać LLM bezpośredniego SQL ani konta z prawem DELETE na całej bazie.** Model dostaje **plik JSON** (+ instrukcja), a zapisanie odbywa się przez **API / narzędzie**, które: waliduje JSON (schemat **[S2]**), sprawdza FK, oferuje **dry-run**, opcjonalnie **podgląd diff**, i dopiero wtedy **transakcję** atomową.
- **Osobna baza SQLite tylko dla „treści”** jest **opcjonalna**: izoluje się od `characters` / sesji, ale **komplikuje** wdrożenie (dwa pliki, synchronizacja). Praktyczna alternatywa przy jednym pliku: **tylko tabele `game_config_*`** dotykane przez import katalogu + **backup pliku** przed każdym masowym importem + snapshot JSON w `admin_audit` / na dysku (kod już robi **pre-import snapshot** przy części ścieżek).
- **Backup:** Obowiązkowy **zrzut pliku bazy** lub `sqlite3 .backup` **przed** importem katalogu z pipeline’u LLM; plus okresowe kopie — minimalny zestaw na wypadek halucynacji niszczących dane.
- **Uprawnienia „generatora”:** Profil **content-only** (tylko wybrane endpointy `game_config_*`), bez dostępu do kont użytkowników i bez surowego SQL.

**Konsekwencje:** Dokumentacja operacyjna (krótka notka w [`00_brief.md`](00_brief.md)); rozszerzenie macierzy [`02_code_usage_matrix.md`](02_code_usage_matrix.md); przy kodzie: rozważyć **ostrzeżenie w panelu** przy `import_config` jeśli brakuje tabel z pełnym katalogiem; roadmapa generatora LLM z **[S2]**.

**Powiązane pliki:** [`backend/app/services/admin_config_transfer.py`](../../backend/app/services/admin_config_transfer.py).

---

### [S7a] Doprecyzowanie [S7] — API dla LLM, backup z retencją, jedna baza — 2026-05-02

**Status:** accepted

**Kontekst:** Akceptacja konkretnych kierunków po propozycjach z **[S7]** (sugestie architektoniczne).

**Uchwała:**

1. **API jako jedyny punkt wejścia dla LLM** przy zapisie treści z katalogu — **zaakceptowane** jako **obowiązujący** kierunek produktowy (model **nie** trzyma surowego SQL; zapis przez endpointy z walidacją / dry-run / transakcją — zgodnie z duchem **[S7]**).

2. **Backup przed importem + retencja:** Wdrożyć **funkcjonalność** tworzenia kopii bezpieczeństwa bazy (lub równoważny zrzut) powiązaną z importem katalogu, z **możliwością ustawienia retencji** (np. liczba ostatnich kopii, maks. wiek plików, ewent. limit miejsca — szczegóły przy implementacji / panelu admin).

3. **Jedna baza:** Zostajecie przy **jednym** pliku SQLite z tabelami `game_config_*` i resztą systemu — **nie** wprowadzacie na ten moment **osobnej** bazy tylko na treść (uproszczenie operacyjne, zgodnie z uzasadnieniem w **[S7]**).

**Konsekwencje:** Zadania **poza** samą fazą 9B dokumentacji — implementacja w backendzie / konfiguracji środowiska; wpis w backlogu produktu.

**Powiązane:** **[S7]**; [`backend/app/services/admin_config_transfer.py`](../../backend/app/services/admin_config_transfer.py).

---

### [S8] Zamknięcie fazy 9B (dokumentacja) — 2026-05-02

**Status:** accepted

**Kontekst:** Sesja 8 — domknięcie audytu schematu vs mechanika **w warstwie dokumentów** (bez merge’u kodu w tej fazie).

**Uchwała:**

1. **Macierz [`02_code_usage_matrix.md`](02_code_usage_matrix.md):** Przejrzana pod kątem uchwał **[S0]–[S7a]**; znane **luki wdrożeniowe** (np. `SKILL_STAT_MAP` vs **[S4b]**, wąski `import_config` vs **[S7]**) pozostają **jawnie opisane** w macierzy i w [`06_schema_gaps.md`](06_schema_gaps.md), nie jako „cicho zapomniane”.

2. **Log decyzji:** Uznaje się za **kompletny na zamknięcie fazy 9B** z punktu widzenia ustaleń zespołu (łącznie z **[S5b]** jako *proposed* dla wrogów vs karta gracza).

3. **Książka gracza — outline:** [`player_rulebook/00_outline_and_tone.md`](player_rulebook/00_outline_and_tone.md) zaktualizowany tak, by **spis treści i zasady redakcyjne** odzwierciedlały **wyłącznie** uchwały z `04_decisions_log.md`, z odesłaniem do **[S5b]** jako otwartego tematu bez obiecywania wdrożenia.

**Konsekwencje:** **Następna faza** = implementacja w kodzie + migracje według [`06_schema_gaps.md`](06_schema_gaps.md) i logu; redakcja pełnego tekstu podręcznika gracza poza minimalnym outline — według sekcji „Następne kroki” w outline.

**Powiązane pliki:** [`03_discussion_agenda.md`](03_discussion_agenda.md) (Sesja 8); [`00_brief.md`](00_brief.md).

---

### [S9] DC — rozwiązanie klucza poziomu do liczby w komendzie `/roll` (implementacja) — 2026-05-03

**Status:** accepted

**Kontekst:** **[S5]** — liczbowe DC z `game_config_dc`, nie z halucynacji LLM; komenda gracza powinna móc użyć **etykiety poziomu** (np. `hard`) zamiast `dc 16`.

**Uchwała (wdrożenie):**

1. **`resolve_dc_for_roll`** w [`dice.py`](../../backend/app/services/dice.py): argument `dc` może być `int`, **albo** **kluczem** tieru (`easy`, `medium`, `hard`, `extreme`, `legendary`) — wartość pobierana z **`get_runtime_config()["dc_tiers"]`** (DB przy `USE_DB_CONFIG`).

2. **`parse_roll_command`:** Po opcjonalnym suffiksie `dc 15` obsługiwany jest **trailing** poziom angielskim kluczem z tabeli, np. `/roll Stealth hard` — zgodnie z kluczami w `game_config_dc`.

3. **`turns.py`:** Przed `resolve_roll` DC jest **zawsze** przepuszczane przez `resolve_dc_for_roll`.

**Konsekwencje:** Rozszerzenie aliasów (np. polskie słowa z `label`) — opcjonalnie później; LLM orchestracja nadal powinna podawać klucz lub liczbę zgodnie z **[S5]**.

---

### [S10] Progresja postaci — XP: zdobywanie, magazyn, wydatki (kierunek produktowy) — 2026-05-03

**Status:** accepted (kierunek; szczegół liczb i UI — kolejna iteracja)

**Kontekst:** **[S4]** przewiduje rangi umiejętności, koszty XP dla wyższych poziomów i sufit 5 — bez zamrożonej tabeli XP w `game_config_*` trzeba ustalić **gdzie** żyją punkty i **jak** się je wydaje.

**Uchwała:**

1. **Źródła XP (najpierw proste):** Nagroda z **`game_config_enemies.xp_award`** przy pokonaniu wroga (jeśli silnik już to nalicza — podpiąć pod jedną ścieżkę); opcjonalnie **ręczny przyznawacz** (GM / endpoint admin) na sesyjne bonusy; questy — **później**.

2. **Magazyn na karcie:** Pole w **`characters.sheet_json`** (np. `xp_available` lub `xp` + ewentualnie `xp_lifetime` dla statystyk) — **jedna** jawna liczba „do wydania”, bez rozproszenia po wielu miejscach bez dokumentacji.

3. **Wydatki — pierwsza kolejność:** **Rangi umiejętności** (klucz = `game_config_skills.key`, limit **`rank_ceiling`**); **podnoszenie bazowych statystyk za XP** — **dopiero po osobnej decyzji balansu** ([**S3]**: nowy stat globalnie = wersja zasad — więc na start **nie** obiecywać „kup STR za XP” bez tabeli).

4. **Koszty:** Tabela kosztów rang / poziomów jako **`game_config_meta`** (JSON, np. `xp_skill_rank_costs`) **albo** dedykowana tabela `game_config_xp_*` przy migracji — do wyboru przy implementacji; musi być **edytowalna w adminie**.

5. **Walidacja:** Przy zapisie awansu — **`rank_ceiling`** z `game_config_skills`; **brak** wyboru umiejętności spoza katalogu.

**Konsekwencje:** Następny ticket implementacyjny: migracja/meta + endpoint `PATCH` karty z operacją „wydaj XP na rangę” + audyt; dokumentacja gracza — rozdział „Awans” po ustaleniu liczb.

---

### [S10a] XP — wydatki bez wymuszonej kolejności, koszty w konfiguracji, brak „LVL” postaci — 2026-05-03

**Status:** accepted (zastępuje **wyłącznie punkt 3** uchwały **[S10]** co do kolejności wydatków; reszta **[S10]** bez zmian)

**Kontekst:** doprecyzowanie po dyskusji: gracz ma **pulę XP** i **sam wybiera**, na co ją wydać; **nie** stosujemy sztywnej kolejności „najpierw umiejętności, potem cechy”. Osobno: **poziom postaci (LVL)** nie jest potrzebny do progresji i **nie daje** bonusów.

**Uchwała:**

1. **Brak wymuszonej kolejności wydatków:** Z puli `xp_available` gracz (przez UI / API) wydaje XP na **dowolny** dozwolony awans, o ile spełnia reguły (katalog, sufity, koszt). **Kolejność** między np. podbiciem cechy a rangą umiejętności **nie** jest narzucana przez zasady — tylko **dostępność** mechaniki (np. cechy za XP dopiero gdy istnieje tabela kosztów i zgoda **[S3]**).

2. **Gdzie siedzą koszty XP (żeby było „jedno miejsce prawdy”):**
   - **Rangi umiejętności:** koszt przejścia na rangę *n* — **`game_config_meta`** (np. klucz `xp_skill_rank_costs`, JSON `{"1":…,"2":…,…}`), **edytowalne w adminie**; walidacja **`rank_ceiling`** z `game_config_skills`.
   - **Bazowe statystyki za XP (gdy powstaną):** osobna tabela w meta (np. `xp_stat_increase_costs` / per-stat) **lub** ustalona w **[S3]** — **nie** rozrzucać kosztów po opisach tekstowych bez wpisu w konfiguracji.

3. **Brak poziomu postaci (LVL):** Nie wprowadzamy **poziomu** jako mechaniki, od której zależą modyfikatory. Progresja to **cechy, umiejętności (rangi) i ewentualne inne wykupy z puli** zgodnie z katalogiem. *Ewentualne pole techniczne „poziom” tylko do statystyk/osiągnięć — poza uchwałą, bez bonusów do rzutów.*

4. **Przyznawanie XP — ustalone źródła:** Zobacz tabelę poniżej; **konkretne widełki liczb** — uchwała **[S10b]**.

   | Źródło | Opis | Uwagi implementacyjne |
   |--------|------|-------------------------|
   | **Pokonanie wroga** | XP z **`game_config_enemies.xp_award`** za zabity wróg w silniku walki | Wdrożone w ścieżce combat; widełki dla MG przy ustawianiu pól — **[S10b]** |
   | **Decyzja MG / narzędzie** | Bonus za cel fabularny / scenę, dobry opis, rozwiązanie zagadki — **ręczny grant** (endpoint admin / GM) | `grant_character_xp(reason=…)` + audyt; widełki wg **odcinka gry** — **[S10b]**, **[S10c]** |
   | **Fabuła / quest** | Nagroda za domknięcie wątku | Gdy model questów — **[S10b]** pkt 4 + osobna uchwała |
   | **inne (np. eksploracja)** | Tylko jeśli dopisane do zasad i do konfiguracji | Unikać „XP za wszystko” bez kategorii |

   **Zasada:** przyznawanie **zwiększa** pulę (`xp_available`, opcjonalnie `xp_lifetime_earned`); **wydanie** zgodnie z **tablicą kosztów** w meta / DB — nie „na oko” w promptcie LLM bez spięcia z konfiguracją.

**Konsekwencje:** Dokumentacja gracza i admina: **nie** obiecują kolejności wydatków; UI pokazuje **koszt** przy każdej opcji upgrade z konfiguracji. Implementacja: ewentualny endpoint podnoszenia statów za XP dopiero z wpisem kosztów w **`game_config_meta`** (lub tabela po migracji).

---

### [S10b] XP — widełki liczbowe (balans startowy) — 2026-05-03

**Status:** accepted (liczby **startowe**; balans w produkcji — przez zmianę `xp_award`, meta kosztów i polityki MG, bez zmiany struktury zasad **[S10a]**)

**Kontekst:** Ustalenie **konkretnych rzędów wielkości** dla przyznawania XP, spójnych z domyślną krzywą kosztów rang (**`xp_skill_rank_costs`**: 50 / 100 / 200 / 400 / 1200 XP na kolejne rangi umiejętności) i typowymi nagrodami z walki (`game_config_enemies.xp_award`). **Miara czasu / fabuły** — patrz **[S10c]** (nie używamy „sesji” w sensie logowania).

**Uchwała — przyznawanie:**

1. **Wrogowie (`xp_award` w katalogu):** Wartość **per pokonany** wróg (ścieżka combat). MG dobiera liczbę do **klasy zagrożenia**, nie do „punktów życia” dosłownie. **Szkielet widełek:**
   - **Puszczalny / tło** (np. szczur, słaby szkielet): **2–5 XP**
   - **Standardowy napastnik** (np. goblin, bandyta): **5–12 XP**
   - **Twardszy przeciwnik / veterán**: **12–25 XP**
   - **Elita / mały boss**: **25–50 XP**
   - **Boss / wyjątkowe zagrożenie**: **50–120 XP** (rzadko; uzasadnione fabularnie)

   *Przykład spójny z bazą:* goblin **3 XP** mieści się w paśmie „standardowy napastnik”.

2. **Mistrz Gry — grant ręczny** (poza automatyczną walką): Jednorazowe przyznanie przez narzędzie / endpoint z polem **`reason`** (audyt). **Szkielet widełek na jeden „odcinek gry”** (**[S10c]**):
   - **Drobny plus** (dobry post, zabawny moment, drobna łamigłówka): **3–8 XP**
   - **Mini-cel z roadmapy** / wyraźny postęp sceny: **5–15 XP**
   - **Istotny przełom** (domknięcie pod-wątku bez silnika questów): **15–35 XP** — typowo **nie więcej niż jedna** taka nagroda **na odcinek**
   - **Wybitny sukces fabularny** (rzadko): **35–60 XP**

3. **Limit miękki (granty MG):** Sumarycznie z punktu 2 celować w ok. **60–100 XP** **na odcinek gry**; powyżej tylko przy **wyraźnym** uzasadnieniu (np. długi odcinek, finał arcu). **Gdy gra jest mocno asynchroniczna** i granice odcinków **nie da się** sensownie rozstrzygnąć — **ten sam sufit** stosować **łącznie na tydzień kalendarzowy** (jako praktyczny substytut). **Nie** sumuje się z limitem walki — XP z wrogów jest osobno.

4. **Questy / silnik fabularny (później):** Gdy powstanie mechanika questów, szacunkowo: **10–25 XP** za mały wątek, **40–100 XP** za główny cel kampanii — **osobna uchwała** po modelu danych.

**Uchwała — wydatki (przypomnienie, już w meta):** Koszt wejścia na rangę *n* umiejętności = wartość **`n`** w JSON **`xp_skill_rank_costs`** (domyślnie **50, 100, 200, 400, 1200** dla rang **1→5**). Zmiana tych liczb **wymaga** zsynchronizowania widełek przyznawania (żeby np. jedna standardowa walka nadal „czuła się” jak postęp).

**Konsekwencje:** Admin ustawia `xp_award` per wróg zgodnie z pasmami z pkt 1; MG szkoli się na widełkach z pkt 2–3. Opcjonalnie później: kopia wytycznych w **`game_config_meta`** (np. `xp_award_guidelines` jako JSON tylko do podpowiedzi w UI), **bez** obowiązkowego egzekwowania w silniku.

**Powiązane:** [`player_rulebook/draft_formulas_and_examples.md`](player_rulebook/draft_formulas_and_examples.md) sekcja **0g**.

---

### [S10c] Terminologia — „odcinek gry” zamiast „sesji gracza” (gra asynchroniczna) — 2026-05-03

**Status:** accepted (doprecyzowanie **terminów** z **[S10b]**; nie zmienia liczb)

**Kontekst:** Z perspektywy gracza **„sesja”** rozumiana jako **czas od zalogowania do wylogowania** jest **złym miernikiem**: można zalogować się, wysłać **jedną** narrację i wrócić następnego dnia. Widełki XP dla grantów MG **nie** mogą być oparte na takim oknie.

**Uchwała:**

1. **„Odcinek gry”** (termin roboczy w dokumentacji mechaniki XP i grantów MG): fragment kampanii od **jednej wyraźnej granicy fabularnej** do **następnej**. Granice mogą być np.: **długi odpoczynek**, **planowana zmiana lokacji** (z roadmapy), **koniec walki** i przejście do eksploracji / rozmowy, **zamknięcie konfliktu**, albo **oznaczenie przez MG** w narzędziu („koniec sceny”). **Nie** jest to „jedno logowanie” ani „jedna wiadomość dziennie”.

2. **Gdy granice odcinka są niejasne** (ciągłe pisanie asynchroniczne bez wyraźnych zwrotów): granty MG liczyć **łącznie na tydzień kalendarzowy** — ten sam rząd wielkości co limit „na odcinek” z **[S10b]** pkt 3, jako **praktyczny substytut**, aż do istnienia w produkcie jawnego **znacznika sceny** w UI.

3. **„Sesja” w innych uchwałach** (np. **[S11]** „cele sesji”) oznacza **plan sesyjny / spotkanie przy stole** lub **zaplanowany blok fabuły w roadmapie**, a **nie** techniczne okno logowania — przy wdrożeniu UI rozważyć zmianę etykiety na np. **„cel sceny / odcinka”**, żeby nie mylić z kontem użytkownika.

**Konsekwencje:** Teksty dla gracza i MG używają **„odcinka”** lub **„sceny”** tam, gdzie chodziło o **[S10b]**; unikać „sesji” w znaczeniu „jedno siadanie przy komputerze”, chyba że kontekst jest jasny.

---

### [S10d] XP — grant Mistrza Gry, audyt, rola LLM (operacja) — 2026-05-03

**Status:** accepted (MVP w kodzie: tabela + API; rola admina z pełnym GM — później)

**Kontekst:** **[S10b]** przewiduje granty MG poza walką; potrzebny jest **kanał techniczny** i **ślad audytu**. W środowisku bez cennych danych produkcyjnych **dopuszczalna jest migracja / czystka bazy** przy zmianach schematu.

**Uchwała:**

1. **Kto przyznaje XP poza `xp_award`:** Wyłącznie **decyzja uwierzytelniona** — na MVP **właściciel kampanii** (`campaigns.owner_user_id`) wywołuje endpoint grantu dla postaci w tej kampanii. **LLM nie zapisuje** przyrostu XP w bazie samodzielnie.

2. **LLM a XP:** Model może **opisać** nagrodę narracyjnie; **nie** jest źródłem prawdy dla liczb — dopóki MG (człowiek) lub przyszły panel **nie zatwierdzi** grantu przez API / narzędzie, pula na karcie **nie** rośnie z powodu samej odpowiedzi modelu.

3. **Audyt:** Każdy grant MG → wiersz w **`character_xp_grants`** (`amount`, `reason`, `granted_by_user_id`, `campaign_id`, `created_at`; opcjonalnie `meta_json`).

4. **API (MVP):** `POST /api/characters/{id}/xp/grant-mg` (body: `amount`, `reason`; query: `user_id` = owner), `GET …/xp/grant-log` — zgodnie z implementacją w [`characters.py`](../../backend/app/api/characters.py).

**Konsekwencje:** Migracja tworząca `character_xp_grants`; restart API. Rozszerzenie na rolę **admin** lub **dedykowany token MG** — osobna iteracja.

**Doprecyzowanie (2026-05-03):**

1. **Kto fabularnie przyznaje XP:** wyłącznie **MG** — **nie** ma osobnej roli uczestnika kampanii z uprawnieniem grantu obok MG. **Technicznie (MVP):** endpoint grantu pozostaje u **właściciela kampanii** jako jedynego kanału „decyzji MG”; **LLM nie zapisuje** XP (**pkt 2** uchwały bez zmian).

2. **Katalog „ile XP za co”:** patrz **[S10e]** — tabela / rekordy konfiguracyjne zamiast „na oko” wyłącznie w prompcie.

---

### [S10e] XP — tabela konfiguracyjna nagród (kategorie zdarzeń → punkty) — 2026-05-03

**Status:** accepted (kierunek; nazwa tabeli i kolumny — przy migracji)

**Kontekst:** Obok **`xp_award`** per wróg i grantów MG potrzebna jest **jedna czytelna tabela prawdy** typu: słaby wróg → **3 XP**, quest główny → **15 XP** itd. (liczby edytowalne w adminie), żeby silnik i audyt nie polegały na halucynacji LLM.

**Uchwała:**

1. Wprowadzić **konfiguracyjny** zapis nagród XP według **kategorii zdarzenia** (np. klasa wroga / typ questa / milestone fabularny — dokładna lista kluczy przy projekcie schematu), z **wartością liczbową** i opcjonalnym opisem dla panelu.

2. **Silnik** (walka, quest, skrypt) **czyta** punkty z tej tabeli / z meta zgodnie z typem zdarzenia; **LLM** może narracyjnie ogłosić nagrodę, ale **liczba** wchodząca do puli musi pochodzić z **zapisu w DB** po walidacji — spójnie z **[S10d]** pkt 2.

3. Współistnienie z **[S10b]:** widełki w uchwale **[S10b]** pozostają **wytycznymi balansu**; konkretne liczby w grze **wiążą** wpisy w konfiguracji + `game_config_enemies.xp_award` tam, gdzie dotyczy wroga.

**Konsekwencje:** Migracja (nowa tabela lub rozszerzenie `game_config_meta` z ustrukturyzowanym JSON — **wybór przy implementacji**); panel admina; powiązanie z przyszłym modelem questów (**[S11b]** pkt 14).

---

### [S11] Kampania — roadmap od MG, pamięć fabularna ponad krótką historię tur, dywergencja gracza — 2026-05-03

**Status:** accepted (kierunek produktowy i architektury; szczegół pól DB i promptów — iteracja)

**Kontekst:** Narracja LLM buduje kontekst m.in. z **ostatnich kilku tur narracyjnych** (w kodzie: `loadrecentturns` z limitem, obecnie **8** — [`game_engine.build_narrative_messages`](../../backend/app/services/game_engine.py)). Przy **dłuższej walce** (wiele tur) lub **długiej sekwencji tur bez podsumowania** model może **zgubić wątek** kampanii. Potrzebny jest sposób, by **MG (człowiek lub zdefiniowany plan)** ustalał **roadmapę** kampanii (cele fabularne, nie „okno logowania” — **[S10c]**) i by system **wspierał** trzymanie się kierunku przy jednoczesnej **improwizacji**, gdy gracz **odbiega** od planu.

**Uchwała:**

1. **Tworzenie i prowadzenie kampanii przez MG:** Przy tworzeniu / edycji kampanii musi być **miejsce na zapis** planu przez MG: np. **cele sceny / odcinka** (sens **[S10c]**), **haki fabularne**, **NPC / lokacje kluczowe**, **oczekiwany łuk** (roadmapa — nie sztywny skrypt). Cel: jeden **kanoniczny zapis** w stanie kampanii (do wyboru: JSON na `campaigns`, rozszerzenie `session_flags`, osobna tabela — decyzja implementacyjna), **czytelny w panelu** i **wstrzykiwany do kontekstu LLM**.

2. **Pamięć dłuższa niż ostatnie tury:** Oprócz krótkiego okna tur (walka, dialog) LLM musi dostawać **stabilny skrót**: roadmapa + **rolling summary** / „co już wiemy o kampanii” (możliwość wykorzystania lub rozszerzenia [`history_summary_service`](../../backend/app/services/history_summary_service.py) / okresowe podsumowanie), tak aby **wiele tur walki** nie usuwało z promptu **celu** kampanii.

3. **Dywergencja gracza:** System (heurystyka + LLM lub tylko wzbogacony prompt) **ocenia**, czy akcja gracza **istotnie** zmienia kierunek względem **zadeklarowanej** roadmapy. Wynik ma **nie blokować** gry na sztywno, lecz:
   - **informować** model („gracz schodzi z osi fabularnej X”) oraz
   - pozwalać MG na **korektę** planu w UI.

4. **Improwizacja LLM:** Gdy gracz robi coś **nieplanowanego**, Mistrz Gry (model) **dostosowuje narrację** i konsekwencje **w ramach** twardych reguł silnika (walka, rzuty, DB); **nie** wymyśla bonusów mechanicznych bez kotwicy w konfiguracji (**[S0]**, **[S5]**).

**Konsekwencje:** Ticket(y): pole/schema „campaign roadmap / cele sceny”; wpięcie do `buildmessages` lub system prompt; ewentualny job **aktualizacji streszczenia** kampanii; testy: walka wieloturowa nadal widzi **cel odcinka / sceny** w system message.

**Powiązane pliki (stan na dziś):** [`game_engine.py`](../../backend/app/services/game_engine.py) (`loadrecentturns`, limit); [`turn_engine.py`](../../backend/app/core/turn_engine.py) (`buildmessages`); [`history_summary_service.py`](../../backend/app/services/history_summary_service.py).

---

### [S11a] Kampania — MVP wdrożenia (plan MG w DB, skrót fabuły w prompcie, koniec odcinka) — 2026-05-03

**Status:** accepted (implementacja **minimalna**; rozszerzenia — kolejne uchwały)

**Kontekst:** **[S11]** bez konkretnego miejsca w DB; w kodzie **już istniało** archiwum podsumowań (**`campaign_ai_summaries`** + [`campaign_history.py`](../../backend/app/api/campaign_history.py)). Brakowało **planu MG** w kanonie oraz **wpięcia** planu + ostatniego skrótu do **jednego** komunikatu systemowego przy narracji.

**Uchwała:**

1. **Plan MG:** Kolumna **`campaigns.gm_plan_json`** (`TEXT`, domyślnie `'{}'`), edytowalna przez **PATCH** `/api/campaigns/{id}/gm-plan` (merge płytki kluczy), wyłącznie **owner** kampanii. Zalecany szkielet JSON:
   - `schema_version` (int),
   - `roadmap` (string — markdown lub czysty tekst),
   - `scene_goals` (lista stringów),
   - `hooks` (opcjonalnie `{ "npcs": [], "locations": [] }`),
   - `current_scene_ordinal` (int, utrzymywany przez endpoint „advance scene”),
   - `scene_log` (lista wpisów `{ ordinal, ended_at, through_turn, note? }`).

2. **Skrót fabuły:** **Bez** duplikowania treści — nadal kanonicznie z **`campaign_ai_summaries`** (ostatni wiersz przez `fetch_latest_saved_summary`). Przy każdej turze narracji silnik **dokleja** do promptu: sformatowany **`gm_plan_json`** + **ostatnie zapisane** podsumowanie (jeśli jest).

3. **Koniec odcinka / sceny:** **POST** `/api/campaigns/{id}/gm-plan/advance-scene` (owner) — zwiększa licznik odcinka, dopisuje wpis do `scene_log` z czasem UTC i **`through_turn`** = `MAX(turn_number)` tur narracyjnych; opcjonalny `note` w query.

4. **Dywergencja:** MVP **bez** osobnego kroku LLM — model widzi plan i skrót w **system message**; osobna heurystyka (**[S11]** pkt 3) **później**.

**Konsekwencje:** Migracja startowa (`RAW_MIGRATIONS` / `ADMIN_MIGRATIONS`); po wdrożeniu **restart API**. Lista kampanii może **nie** zwracać `gm_plan_json` (rozmiar); szczegół w **GET** pojedynczej kampanii.

---

### [S11b] Wizja fabularna — haki z postaci, scenariusz od GM (LLM), notatnik gracza, kampania bez twardego końca — 2026-05-01

**Status:** accepted (wizja produktowa; realizacja w fazach — bez wymogu daty)

**Kontekst:** Uzupełnia **[S11]** / **[S11a]** o oczekiwania użytkownika co do **roli MG (modelu)** i **edycji planu** przez człowieka.

**Uchwała (kierunek):**

1. **Haki z postaci:** Opis stworzony przez gracza = **pierwszy** materiał dla MG; **drugi** — ustrukturyzowany opis „jak wygląda, mocne i słabe strony” (generowany LLM przy tworzeniu postaci). To są **kotwice** do dalszej fabuły.

2. **Scenariusz kampanii:** MG (LLM) **wymyśla** konspekt (wątki, problemy, postacie, tło) i wynik ma trafić do **zapisu w stanie kampanii** (docelowo w **tym samym** kanale co `gm_plan_json` / rozszerzenie schematu — **implementacja**). Stamtąd system czyta **elementy** do tego, czy gracz idzie w sensownym kierunku; **fakty** (kogo pokonał, co zrobił, pod XP) — **dopisywalne** do tego zapisu lub powiązanego logu w miarę rozwoju kodu.

3. **Podsumowanie / historia:** Wykorzystać istniejącą ścieżkę **historii / `campaign_ai_summaries`**; **część** treści może być **jawna dla gracza** (notatnik, skrót), **część** tylko jako kontekst dla MG (szersza wiedza). **Technicznie** — np. dwa pola lub dwa rodzaje wpisu (do decyzji przy implementacji). Parametry **N** tur / wymuszenie ręczne / koszt tokenów — **do testów** (pomijalne na etapie projektu).

4. **Widok gracza — notatnik read-only:** Gracz widzi **uproszczony** widok: ważne postacie, zadania, zdarzenia — **tylko do czytania** (automatyczny notatnik). Dziś w kliencie jest m.in. modal **„Podsumowanie kampanii”** (tekst z API); rozbudowa na sekcje / karty to **kolejna fala UI** (po **[S16]**). **Nie** zakładamy, że gracz **edytuje** głęboki plan fabularny — to rola **MG (LLM)** w narracji.

5. **Kto edytuje „plan”?** **Edycja ręczna przez człowieka** (**PATCH** `gm_plan_json`) pozostaje **narzędziem opcjonalnym** (korekta, testy, narzędzia autorskie) — **nie** jest celem gry. **Docelowo** plan i jego aktualizacje mogą pochodzić z **wygenerowania LLM** (np. po stworzeniu postaci, po zamknięciu odcinka). Gracz **nie musi** pisać roadmapy jak w Excelu.

6. **Dywergencja — możliwości techniczne (prosty przegląd):**  
   - **(a)** Tylko tekst w **system prompt** (plan + skrót) — model sam „czuje” odległość od założeń (**najtańsze**, MVP).  
   - **(b)** **Heurystyka** bez LLM: porównanie słów z akcji gracza z listą `scene_goals` — dopisanie jednej linii do promptu.  
   - **(c)** Drugi, mały **wywołanie LLM** tylko „czy odbiegamy?” — droższe, dokładniejsze.  
   - **(d)** Ekstrakcja **faktów** z tur do struktury w DB — potem reguły na strukturze.

7. **Koniec „głównej” kampanii:** Nie chcemy **sztywnego końca**, gdy skończy się pierwszy konspekt. Preferencja: **fabularna kontynuacja w tej samej kampanii** — MG **dokłada** nowe wątki i etapy (aktualizacja zapisu stanu kampanii przez LLM / narzędzia). **Alternatywa produktowa:** jawna **„Nowa kampania”** z tą samą postacią i **nowym** generowanym tłem — osobny rekord kampanii, ciągłość fabularna przez narrację, nie przez jeden przycisk „sequel”. Wybór proporcjacji **fałd fabularnych vs nowy rekord** — do backlogu; **preferencja zapisana:** unikać uczucia „gra się skończyła”, jeśli gracz chce grać dalej.

**Doprecyzowanie (Q&A, 2026-05-01):**

1. **Kiedy pierwszy konspekt / plan fabularny:** po **zapisaniu postaci**, **przed** pierwszym promptem MG w czacie narracyjnym (pierwsza narracja może już oprzeć się na wygenerowanym planie).

2. **Co widzi gracz w „planie” / notatniku:** wyłącznie to, co **mógł wywnioskować** z narracji MG **do tej pory** — **nic więcej, nic mniej**. To **podsumowanie tego, co się wydarzyło** (rolling recap), a **nie** podgląd ukrytych założeń fabularnych.

3. **Realizacja vs dywergencja:** MG **dąży** do realizacji planu; gdy gracz **usilnie** schodzi z zadań realizujących plan, MG **reaguje fabularnie** i **przerabia plan kampanii** pod faktyczny kierunek gry (zapis po stronie backendu — w miarę implementacji).

4. **Czy MG może planować kolejne łuki zanim gracz skończy pierwszy?** — **produktowo tak** (nic nie zabrania); **technicznie** wybór między wariantami **W1 / W2** w § „Opcje techniczne” poniżej (decyzja przy kodzie).

5. **Wymuszenie odświeżenia podsumowania:** w **multiplayer** każdy uczestnik sesji może wymusić rollup; dopuszczalny **cooldown** (np. nie częściej niż co **20 rund** od ostatniego udanego odświeżenia) — parametr konfiguracyjny do strojenia.

6. **Obecna ścieżka „historia / podsumowanie”:** filozofia **zostaje** — transkrypt → LLM → zapis; **nie zmieniamy** modelu działania, tylko **rozdzielamy** zapis jawny vs MG-only (**pkt 7**).

7. **Jawne vs MG-only w DB:** **dwa osobne rekordy** (np. dwa wiersze w `campaign_ai_summaries` z rozróżnieniem `kind` / `audience`, albo **osobna tabela** na skrót tylko dla MG) — łatwiejszy podgląd, kontrola uprawnień API, **mniejsze ryzyko wycieku**.

8. **„Zepsucie” podsumowania:** gracz **nie psuje** rollupu — podsumowanie to **stan świata do momentu** wygenerowania; kolejne akcje to **nowe tury** widoczne przy następnym odświeżeniu.

9. **Długość / forma tekstu podsumowania:** **jak obecnie** (modal, prompt, UX — bez zmiany „na siłę”).

10. **Source of truth:** **kanon** to **trwale zapisane tury narracyjne** w **`campaign_turns`** (`route = narrative`); z nich [`history_summary_service`](../../backend/app/services/history_summary_service.py) buduje transkrypt. **Podsumowanie** to **pochodna** (LLM), nie równoległy kanon treści.

11. **Błąd rollupu LLM:** UI pokazuje stan **„wymaga odświeżenia”** (szczegół: ostatnia dobra wersja vs brak — przy implementacji).

12. **Gdzie trzymać treść tylko dla MG (żeby nie trafiła do historii gracza):** **nie** łączyć z polem zwracanym graczowi. **Rekomendacja:** strukturalny plan w **`campaigns.gm_plan_json`** (albo osobna tabela `campaign_gm_private_*`, jeśli rozmiar/narzędzia tego wymagają) — **GET** kampanii dla gracza **bez** tego pola; czytają **tylko** silnik narracji + ścieżki admin/debug. Osobny zapis **tekstowego** skrótu wiedzy MG: drugi rekord / tabela (**pkt 7**), **osobny endpoint** lub filtr `audience`.

13. **Kontynuacja fabularna bez „nowej kampanii”:** preferencja jak w §7 powyżej; warianty techniczne — **W1 / W2 / W3** poniżej.

14. **Questy / XP:** dla gracza forma obojętna; dla systemu **struktura w DB** (np. lista celów z kluczami i statusem, powiązanie z grantami XP) **ułatwia** nagradzanie i audyt — przy implementacji planu kampanii.

15. **PATCH `gm_plan_json` z panelu:** **admin + debug**; docelowo gra ma działać **bez potrzeby** ręcznej korekty planu.

**Opcje techniczne — plan „z wyprzedzeniem” i kolejne łuki (pkt 4 i 13):**

- **W1 — Jeden `campaign_id`, mutujący `gm_plan_json`:** LLM **merge**uje plan (np. sekcja `planned_beats` / `next_arc_sketch` **niewidoczna** w API gracza). Można dopisywać kolejne etapy **zanim** gracz domknie pierwszy łuk.

- **W2 — Kolejka łuków w tabeli:** np. `campaign_story_beats` (kolejność, status `planned` | `active` | `resolved`) — jawne miejsce na **wcześniej** przygotowany następny łuk; tylko backend + prompt czytają `planned`.

- **W3 — Nowy rekord `campaigns`:** jawny „sequel” z tą samą postacią — **nie** preferowany dla ciągłości fabularnej; zostaje jako **świadomy** wariant produktowy, jeśli kiedyś go wybierzecie.

**Decyzja przy kodzie:** **W1** na MVP; **W2** wyłącznie jako **rozbudowa**, jeśli W1 przestaje wystarczać (rozmiar planu, złożoność beatów). **Kolejka realizacji + prompty w jednym pliku:** [`11_MASTER_TASK_QUEUE_AND_PROMPTS.md`](11_MASTER_TASK_QUEUE_AND_PROMPTS.md) (T06, T14, …); [`10_agent_implementation_plan.md`](10_agent_implementation_plan.md) przekierowuje do mastera.

**Doprecyzowanie (T14 — W2 `campaign_story_beats`, 2026-05-04):**

1. **Ocena W1:** W bieżącym zakresie produktu i kodu (T06) **jeden JSON** `gm_plan_json` na kampanii jest **wystarczający** — bez osobnej tabeli `campaign_story_beats` w tej iteracji.
2. **Uzasadnienie i kryteria ponownej oceny:** [`ADR_T14_W2_story_beats_deferred.md`](ADR_T14_W2_story_beats_deferred.md). **Migracji W2 nie wykonujemy** przy zamykaniu T14; nowy ADR przed ewentualną implementacją W2.

**Konsekwencje:** Ticket’y: pipeline „postacie zapisane → generacja planu → pierwsza narracja”; rozdzielenie rollupu **player** vs **gm** w DB i API; cooldown odświeżenia w multiplayer; rozbudowa `gm_plan_json` (**W1**); tabela beatów (**W2** — świadomie odłożona przy T14; patrz ADR powyżej); flaga błędu rollupu w UI; strukturalne cele pod XP — bez zmiany filozofii `campaign_turns` jako kanonu.

**Doprecyzowanie (runda 2 — Q&A, 2026-05-03):**

1. **Pierwsza generacja planu — „do skutku”:** pierwsza narracja MG **nie startuje**, dopóki zapis planu (LLM → `gm_plan_json` lub równoważny krok) **nie zakończy się sukcesem** — **retry** / kolejka, bez gry z pustym planem.

2. **Jeden vs dwa wywołania LLM (rollup):** **najpierw test** (jakość JSON/tekstu, halucynacje, stabilność) — zobacz [`11_MASTER_TASK_QUEUE_AND_PROMPTS.md`](11_MASTER_TASK_QUEUE_AND_PROMPTS.md) §2 (**T01**). **Preferencja produktowa:** jeśli **jeden prompt** spełnia kryteria → wdrożyć **wariant A** (mniej ścieżek = mniej miejsc na pomyłkę). **Wariant B** (dwa requesty) tylko gdy test wykaże, że A jest niewystarczające.

3. **Podsumowanie / notatnik gracza — tylko z transkryptu (propozycja techniczna):**
   - **Prompt:** twarda reguła: „**Wypisz wyłącznie** fakty i postacie **występujące w transkrypcie** poniżej; **nie** dopisuj niczego z zewnętrznej wiedzy ani z planu MG.”
   - **Źródło kontekstu dla tego calla:** **tylko** złożony transkrypt z `campaign_turns` — **bez** dołączania `gm_plan_json` do promptu generującego **wersję dla gracza**.
   - **Opcjonalnie (MVP+):** prosta **weryfikacja heurystyczna** po stronie serwera (np. porównanie listy własnych imion wyciągniętych z transkryptu z tokenami w podsumowaniu → tylko **log / ostrzeżenie** dla operatora), bez ciężkiego NLP.
   - **Wersja MG-only** może nadal korzystać z planu + transkryptu — **osobny** pipeline / rekord (**[S11b]** pkt 7).

4. **Cooldown odświeżenia rollupu (multiplayer):** licznik **per `campaign_id`** (wspólny dla wszystkich graczy w tej kampanii).

5. **W1 / W2 / W3 — obrazkowo:** **W1** — **jeden zeszyt** (`campaign_id`): dopisujesz i zmieniasz plan w tym samym miejscu (JSON na kampanii). **W2** — **osobna kartka na każdy beat** (tabela wierszy: zaplanowany / aktywny / zakończony). **W3** — **nowy zeszyt** (nowy rekord kampanii). Preferencja: **nie W3** dla ciągłości; **W1 jeśli wystarcza**; **W2 ewentualnie** jako rozbudowa, gdy W1 nie starczy — w masterze §6 (**T06**) i §15 (**T14**): [`11_MASTER_TASK_QUEUE_AND_PROMPTS.md`](11_MASTER_TASK_QUEUE_AND_PROMPTS.md).

6. **„Nowy akt” bez nowej kampanii:** **Tak** — to jest **ta sama kampania** (`campaign_id` bez zmiany). Gdy spełnione są **warunki zakończenia głównego questa** (wykrycie w narracji + ewentualnie stan w DB), uruchamiany jest **ten sam typ kroku LLM** co przy **początku** (generacja / merge planu fabularnego), a narracja **łączy** dotychczasową historię z nowym łukiem. **`campaign_turns`:** **ciągła numeracja tur**, jeden łańcuch historii; notatnik gracza = rollup **z całego** transkryptu do danego momentu (bez „zerowania” świata). **Nie** wymaga się osobnego rekordu `campaigns` dla fabularnego „sequelu”.

   **Doprecyzowanie (T15 — wdrożenie, 2026-05-04):** „Główny quest” = klucz obecny w `quests_completed`, który jest **równy** `gm_plan_json.engine_private.main_quest_key` (domyślnie **`main_quest`**). Wykrycie: przejście z „**nie** było w `quests_completed`” na „**jest**”, przy zapisie **`sheet_json`** (np. `PATCH …/characters/{id}/sheet`) lub admin **`quest complete`**. Efekt: **merge** nowego łuku (`act_N`) w W1 + jedna **nowa tura** `campaign_turns` z krótką narracją spinającą (`route=narrative`) — **bez** nowego `campaign_id`. Szczegóły: [`11_MASTER_TASK_QUEUE_AND_PROMPTS.md`](11_MASTER_TASK_QUEUE_AND_PROMPTS.md) §16.

**Wyjaśnienie [AUDIT] z przykładem:** **[AUDIT]** to **nie** jednorazowy przycisk — to **proces zamknięcia listy luk** w [`06_schema_gaps.md`](06_schema_gaps.md). **Przykład:** Przed migracją magii wiersz mówi „brak kolumn `targeting` / `aoe_radius_m`” → po migracji SQL + deployu backendu zmieniasz status na **wdrożone** albo usuwasz wiersz; opcjonalnie wpis w `04`: „**[AUDIT]** zamknięty na schemat po migracji X”. **Domknięcie** = brak otwartych luk **albo** jawna notka „świadomie odłożone poza MVP”. **Lista zadań wdrożeniowych i raportów** — [`11_MASTER_TASK_QUEUE_AND_PROMPTS.md`](11_MASTER_TASK_QUEUE_AND_PROMPTS.md) (m.in. **T11** AUDIT).

---

### [IMPL] Kolejność wdrożeń po audycie 9B (fale priorytetu) — 2026-05-03

**Status:** accepted (kolejka robocza; aktualizuj przy zmianie ryzyk — bez usuwania historii, dopisuj **supersedes** jeśli odwrócisz kolejność)

**Kontekst:** Zamknięte są m.in. **[S11a]** (plan + skrót w prompcie), **[S10d]** (grant MG + audyt), **[S9]** (DC), część **[S10]** (pula, spend, `xp_award`). Trzeba **uporządkować resztę prac**, żeby nie równolegle „wszystko naraz”.

**Uchwała — fale (od najbliższej):**

| # | Fala | Zakres (uchwały / obszar) | Uwagi |
|---|------|---------------------------|--------|
| **1** | **Pamięć fabularna operacyjnie** | Domyślne lub cronowe **`POST …/history/summary/ensure`** (albo wywołanie z UI po prog tur), żeby `campaign_ai_summaries` nie zatykały się; opcjonalnie job nocny | Bez tego plan MG działa, ale **skrót** bywa przestarzały |
| **2** | **Broń i atak vs konfiguracja** | **[S1]** — mapowanie `weapon_type` ↔ rodzaj ataku w kodzie; finesse / dwuręczność jako umiejętność — przyrostowy rollout | Zależy od tego walka + narracja |
| **3** | **Przedmioty i efekty JSON** | **[S2]** + **[S6]** — jeden schemat `effect_json`, walidacja przy zapisie admina; AC z `ac_bonus` gdy obrona liczona automatycznie | Przed pełnym stanami złożonymi |
| **4** | **Warunki i konsumable endgame** | **[S6]** §2 typy efektów w JSON; migracja **jednego `item_key`** (loot / consumables) | Po stabilnym JSON przedmiotów |
| **5** | **Import / środowiska** | **[S7]** — jedna zalecana ścieżka (`catalog_snapshot` vs `import_config`), dokumentacja ryzyk **ucięcia** kolumn | Gdy katalog rośnie między dev a prod |
| **6** | **Kampania — inteligencja** | **[S11]** dywergencja (heurystyka / drugi krok LLM); **UI** edycji `gm_plan_json` | Po tym, gdy podstawowa pętla gry jest stabilna |
| **7** | **Progres cech** | Meta kosztów statów + endpoint spend, gdy **[S3]** + balans | Zależność od tabeli XP statów |

**Zasada:** w obrębie jednej fali **nie** otwieraj drugiego dużego tematu (np. JSON przedmiotów + import na raz), chyba że są **twarde** zależności techniczne.

**Konsekwencje:** [`00_brief.md`](00_brief.md) — skrót listy; [`03_discussion_agenda.md`](03_discussion_agenda.md) — Blok C domknięty; kolejne PR-y według numerów fal (z tolerancją ±1 przy odkryciu blokera).

---

### [S12] Magia — cel pojedynczy vs AOE, bez osobnej tabeli czarów — 2026-05-03

**Status:** accepted (**uzgodnienie produktowe:** 2026-05-01). Migracja kolumn i kod taktyki — osobne ticket’y.

**Kontekst:** **[S1]** — magia w jednym ze ścieżek broni; **[S15]** — osobna **zakładka** „Czary” w panelu przy **tej samej** tabeli SQL.

**Uchwała:**

1. **Jedna tabela SQL:** Czary jako rekordy **`game_config_weapons`** z `weapon_type = 'spell'`. **Bez** osobnej tabeli czarów na MVP.

2. **Panel admina:** **Inna zakładka** („Czary”) niż ogólna broń — to **tylko widok UI** (filtr + formularz), **nie** druga tabela w bazie — **[S15]**.

3. **MVP — dwa tryby zasięgu:** **`single`** (jeden cel) oraz **`aoe_radius`** (obszar w kształcie **kuli**, promień w **`aoe_radius_m`**). **Stożek, linia, tylko siebie** i inne kształty — **nie** w pierwszej wersji produktu (możliwy dopisek w przyszłości bez zmiany filozofii „jedna tabela”).

4. **`magic_school`:** Na początek **wyłącznie etykieta** (filtry w adminie, kontekst dla LLM) — **bez** automatycznego wpływu na liczenie obrażeń.

5. **AOE w grze (pierwsza wersja):** Wystarcza **prosta** spójność: katalog + opis + **`aoe_radius_m`** tak, aby narracja i MG (AI) **nie zaprzeczały** zapisowi. **Kogo dokładnie trafiło** w walce programowej — **bez** wymogu mapy / siatki na MVP; **mapa i pełna taktyka** — później.

**Konsekwencje:** Migracja: `targeting`, `aoe_radius_m`, `magic_school` (nullable); walidacja wartości `targeting` dla MVP (`single` \| `aoe_radius`). Import pełnych kolumn przez **`import_catalog_snapshot`**; aktualizacja [`01_schema_inventory.md`](01_schema_inventory.md). Szczegóły pól: [`07_extended_design_spec.md`](07_extended_design_spec.md) §1. Zakres „mapy” i taktyki — **[S19]**.

---

### [S13] `effect_json` — szkielet wersji 0 wspólny dla przedmiotów i warunków — 2026-05-03

**Status:** accepted (**uzgodnienie produktowe:** 2026-05-01). Walidator + ewent. asystent LLM w adminie — implementacja osobno.

**Kontekst:** **[S2]** / **[S6]** — jeden język efektów dla przedmiotów i warunków.

**Uchwała:**

1. **Jeden wspólny format JSON** (top-level: m.in. `schema_version`, `effect_category`, tablica `effects[]`) dla **`game_config_items`** i **`game_config_conditions`** — szczegóły pól w [`07_extended_design_spec.md`](07_extended_design_spec.md) §3.

2. **LLM w panelu:** Zgodnie z kierunkiem **[S2]** — opis użytkownika / MG może być **przetworzony przez LLM** do **propozycji** poprawnego `effect_json`, którą admin **akceptuje lub poprawia** (nadzorowany zapis, nie „czarna skrzynka” bez walidacji). Szerszy produktowy zakres **konwersacyjnego asystenta** dla całej sekcji Game design i katalogów — **[S20]**.

3. **Walidacja obowiązkowa:** Przed **zapisem** rekordu do bazy oraz przy **imporcie** katalogu — JSON musi przejść walidację schematu (wersji v0); **śmieć nie wpada** do produkcyjnej konfiguracji.

4. **Lista typów efektów (`type` / enum):** Na start **krótka**, świadomie — lista **będzie rozszerzana** w kolejnych iteracjach (bez zamrażania „na zawsze” pierwszego zestawu).

5. **Stare płaskie kolumny `effect_*`:** **Nie** utrzymujemy migracji treści ze starej bazy ani długiego okresu „dual read”. Dopuszczalny **czysty start:** **porzucenie** starych rekordów opartych o płaskie pola, **kilka rekordów wzorcowych** w JSON jako szablony; ścieżka bez konieczności zachowania starej zawartości (**nie potrzebujemy starej bazy** pod ten cel).

**Konsekwencje:** Jedna funkcja walidacji w backendzie; usuwanie lub deprecacja kolumn `effect_*` w migracji schematu zgodnie z implementacją; dokumentacja listy typów i rozszerzania; powiązanie z importem (**[S7]** — walidacja przy imporcie).

---

### [S14] Wrogowie — jedna tabela, struktura jak karta bohatera (rzadka), generator z opisu — 2026-05-03

**Status:** accepted (**uzgodnienie produktowe:** 2026-05-01). Migracja `skills_json` i podłączenie do rzutów — implementacja osobno.

**Kontekst:** **[S5b]** (superseded); **[S1b]** (konfrontacje); **[S20]** (asystent LLM).

**Uchwała:**

1. **Jedna tabela SQL:** **`game_config_enemies`** pozostaje **jedynym** katalogiem szablonów wrogów — **bez** osobnej tabeli „jak `characters`”.

2. **Zgodność struktury z arkuszem bohatera (implementacja):** Przyjmujemy **tę samą ideę co przy postaci** — pola mają **znaczenia zgodne z kartą gracza** (HP, obrona, atak, obrażenia, modyfikatory…), **nie wszystkie rekordy muszą mieć wszystkie pola wypełnione** (**sparse** / domyślne zera lub NULL tam, gdzie sensowne). Ułatwia to kod i UI; **nie** oznacza duplikacji osobnej tabeli stanu sesji — to nadal **wiersz katalogu**. **Cel produktowy długoterminowy:** w przyszłości rozbudować system walki **na tych samych danych wejściowych** co u gracza (rozszerzanie **tego** wiersza katalogu / JSON-ów, migracje kolumn), **bez** mnożenia nowych tabel tylko dlatego, że „brakuje pól” — unikamy drugiego modelu danych dla wroga.

2a. **„Pełna karta” vs jedna tabela:** **Nie** tworzymy osobnej tabeli „jak `characters`” dla wrogów. **Pełność danych** = **wypełnienie** tych samych pól (i ewent. **`skills_json` / przyszłe rozszerzenia** w jednym rekordzie), gdy produkt będzie wymagał głębszej taktyki — wciąż **jeden** katalog `game_config_enemies`.

3. **Stan na dziś (audyt kodu walki):** Istniejące kolumny **`game_config_enemies`** (**`hp_base`**, **`ac_base`**, **`attack_bonus`**, **`damage_die`**, **`dex_modifier`**, XP, łupy itd.) **pokrywają ścieżkę walki** w `combat_service`. To **wystarcza na MVP walki**.

4. **Konfrontacje / umiejętności NPC ([S1b]):** Żeby **deterministycznie** rozstrzygać np. skradanie vs percepcja **po kluczach** jak u gracza (**[S4b]**), należy **dodać** opcjonalne pole **`skills_json` TEXT** (nullable): mapa **`{ "skill_key": ranga_lub_bonus }`** przy kluczach jak w **`game_config_skills`**. Do migracji — konfrontacje mogą nadal opierać się na narracji; po polu — jedna ścieżka kodu z arkuszem.

5. **Generator ([S20]):** Admin opisuje cel (np. „bandzita z kuszą”) → LLM **proponuje** rekord (statystyki + sensowne **`skills_json`** / kontekst broni) → **walidacja** → zapis. Ten sam nadzór co przy **`effect_json` ([S13])**.

**Konsekwencje:** Migracja `skills_json`; aktualizacja admina / importu (**[S7]**); **`01_schema_inventory`**; doprecyzowanie **`dice.py`** przy podłączeniu umiejętności wroga. **[S5b]** → superseded.

**Uwaga (produkcyjna rekomendacja z przeglądu kodu):** Exchange „czy obecny stan wystarczy?” — **walka tak**; **skill check po kluczach** — **po dodaniu `skills_json`** lub równoważnym mapowaniu; do tego momentu LLM może **wspierać** narracyjnie bez pełnej deterministyki.

---

### [S15] Panel admina — zakładki katalogów vs osobne tabele SQL — 2026-05-03

**Status:** accepted (**uzgodnienie produktowe:** 2026-05-01)

**Kontekst:** Pytanie, czy np. czary czy pancerze „powinny” mieć **osobną tabelę**, żeby admin miał porządek.

**Uchwała:**

1. **Rozdzielenie pojęć:** **Zakładki / sekcje w panelu** (Czary, Zbroje, Mikstury…) realizują **ludzką logikę** i **filtry** na wspólnym katalogu — **nie wymagają** osobnej tabeli SQL na każdą zakładkę.

2. **Minimalna liczba tabel:** Stosujemy **jedną tabelę**, gdy wystarcza do zapisu mechaniki. **Wielu tabel nie tworzymy**, jeśli nie jest to **absolutnie konieczne** — osobną tabelę SQL rozważamy **wyłącznie** przy uzasadnieniu modelem (inne FK, cykl życia, import, uprawnienia, kolizje kluczy), nie przy wygody menu.

3. **Czary:** **Nie** przewidujemy osobnej tabeli SQL tylko dla czarów. Rekord czaru w **`game_config_weapons`**, zakładka „Czary” w adminie (`weapon_type = spell` + formularz) — spójnie z **[S12]**.

4. **Zakładki — lista i rozszerzalność:** Zestaw zakładek jest **raczej stały** w danym etapie, przy czym **ważne jest łatwe dokładanie kolejnych zakładek** w UI bez zmiany filozofii pracy. **Nadrzędny priorytet:** **mechaniczna spójność** — ten sam wzorzec **edycji, sortowania, wyszukiwania** (i równoważnych operacji listy) na wszystkich zakładkach.

5. **Podgląd „wszystkie rekordy”:** Osobnego widoku surowej listy bez filtra (debug całej tabeli) **nie** przewidujemy — wystarczają zakładki.

**Konsekwencje:** Specyfikacja UI admina: mapowanie zakładek na filtry (`WHERE` / typ); implementacja pod **[S16]** jako jedna rodzina ekranów katalogu. Bez nowej tabeli dla czarów. Szczegóły UX vs model: [`07_extended_design_spec.md`](07_extended_design_spec.md) §10.

---

### [S16] Architektura klienta — przebudowa pod Figma 1:1, nowy framework, gra przed adminem — 2026-05-03

**Status:** accepted (**uzgodnienie produktowe:** 2026-05-01). Wybór dokładnego frameworka i struktura repo — przy starcie implementacji.

**Kontekst:** Projekt wizualny w Figmie ma być wdrażany **jak najbliżej 1:1**; próby adaptacji przez **Figma Make** nie przyniosły zamierzonego efektu — **oficjalna ścieżka**: **tokeny + biblioteka komponentów w kodzie** + mapowanie z Figmy (np. Code Connect / równoważny proces), a nie „magiczny eksport całej aplikacji” z narzędzia typu Make.

**Uwaga techniczna (Figma ≠ jeden framework Twojej gry):** Sam produkt **Figma** (aplikacja przeglądarkowa) **nie jest** „Twoją grą w React” — nie ma pojęcia „framework Figma” dla repo **ai-gm**. **Code Connect** i typowe przepływy design-to-code w ekosystemie Figma **często** używają **Reactu** w przykładach i pluginach, ale to **wybór integracji**, nie prawo fizyki. Decyzja brzmi: stack **zgodny z możliwością mapowania komponentów z Figmy** (typowo **React** lub **Vue** — do wyboru przy setupie), z **design tokenami** zsynchronizowanymi z plikiem Figmy.

**Uchwała:**

1. **Cel 1:1:** Priorytetem jest **wierność wizualna i komponentowa** projektowi z Figmy (**bez** narzucenia osobnego „adaptacji w nieznanym frameworku z Figmy”) — **źródło komponentów i układów = Figma**, kod utrzymuje **behawiorystykę** i podłączenie API.

2. **Skok na nowy framework:** Świadome **jednorazowe** przejście z obecnego frontu (HTML/JS moduły) na **nowoczesny framework** uzgodniony z handoffem z Figmy (najczęściej **React** w stacku z Code Connect — **ostateczny wybór** w ticket’ie startowym). Celem jest **minimalizacja rozjazdu** między projektem a produktem, nie „dopasowanie do wewnętrznego stacku aplikacji Figma jako produktu”.

3. **Figma = źródło komponentów** (biblioteka w Figmie → komponenty w repo; tokeny nazwane spójnie).

4. **Kolejność wdrożenia UI:** **Najpierw warstwa gracza** — wszystko, co **widzi gracz** (czat, walka, karta, UI sesji). **Panel admina / Game design** może **pozostać na starym froncie** do czasu osobnego etapu — **nie** blokuje wdrożenia nowego klienta gry.

5. **Priorytet:** **Ekran gry** > przebudowa admina w tej fazie.

6. **API:** Dopuszczalne **zamrożenie kontraktu** API pod wdrożenie frontu gry; kolejne pola — **wersjonowanie** lub rozszerzenia bez łamania istniejących klientów.

7. **Kiedy wdrażać nowy front — nie „po wszystkich funkcjach”:** **Nie** czekamy na domknięcie **wszystkich** fal **[IMPL]**. Start **nowego frontu gry** możliwy, gdy **stabilny jest MVP kontraktu** dla przepływów gracza (narracja / tury / podstawowa walka lub ich uzgodniony podzbiór). Backend może nadal rosnąć **równolegle** po zamrożonym rdzeniu API; pełna lista funkcji technicznych **nie** jest warunkiem wstępnym dla pierwszego wdrożenia UI — inaczej front wiecznie czeka.

8. **Repo (mono vs osobny front):** Do decyzji przy implementacji — uchwała nie narzuca; kryteria: CI, deploy, rozmiar zespołu.

**Konsekwencje:** Blueprint projektu frontowego; backlog komponentów zsynchronizowany z Figmą; osobna fala „admin v2” później. Szczegóły: [`07_extended_design_spec.md`](07_extended_design_spec.md) §11.

**Kolejność operacyjna (uzgodnienie 2026-05-01):** **Przeniesienie nowego frontu i pracy z Figmą odkładamy na sam koniec** bieżącego bloku priorytetów — zespół **najpierw** ma **zrozumieć** workflow i **nauczyć się** (materiał: [`09_figma_to_code_workflow.md`](09_figma_to_code_workflow.md); praktyka we własnym tempie). To **nie** unieważnia **[S16]** (nadal: 1:1 z Figmą, nowy framework, gra przed adminem, API); zmienia się wyłącznie **moment startu** implementacji: **na końcu** planu, nie równolegle z teraz. Do tego czasu **utrzymujecie** obecny front.

---

### [S17] Integracja Azure OpenAI jako dostawcy LLM — 2026-05-03

**Status:** accepted (**uzgodnienie produktowe:** 2026-05-01). Implementacja techniczna (sterownik, pola env, testy z mockiem) — osobne ticket’y.

**Kontekst:** Backend ma już ścieżkę **OpenAI-compatible** (`/v1/chat/completions`) w [`llm_service`](../../backend/app/services/llm_service.py); Azure OpenAI używa tego samego protokołu z **innym URL** (deployment, `api-version`) i kluczem z Azure.

**Uchwała:**

1. **Wsparcie pierwszej klasy:** Konfiguracja **`provider = azure_openai`** (lub równoważny znacznik) z polami: **`azure_endpoint`**, **`deployment_name`**, **`api_version`**, **`api_key`** (nigdy w logach); mapowanie na jeden sterownik wywołań typu OpenAI chat completions.

2. **Faza developmentu:** Wszyscy korzystają z **tego samego** endpointu / deploymentu (np. jedno ustawienie środowiska lub jeden wspólny profil) — **bez** konieczności **klikania i wpisywania** u każdego developera przy każdej sesji (minimalny tarcie pracy).

3. **Faza produkcji (docelowo):** Możliwość, żeby **gracz podłączył własny endpoint / klucz** — **po osobnym etapie projektowym:** **profil konta gracza**, w którym zarządza swoim kontem i preferencjami (w tym LLM). Do tego momentu traktujemy to jako **backlog**, nie wymóg MVP **[S17]**.

4. **Długi klucz API — UX (problem z przepisywaniem):** Nie oczekujemy, że użytkownik **za każdym razem** wkleja pełny klucz. **Kierunek:** klucz **trzymany po stronie serwera** (nie jako jedyna kopia w przeglądarce); użytkownik **wprowadza raz** (oraz przy **rotacji** / zmianie); w UI **maska** (np. `sk-...xxxx`) + akcja „**zmień klucz**”. Szczegół techniczny (szyfrowanie at rest, ewent. menedżer sekretów) — przy implementacji.

5. **Środowisko serwera:** Sekrety domyślne środowiska z **`LLM_*` / env** lub menedżera sekretów w prod; **`.env.example`** bez prawdziwych wartości.

6. **Fallback:** Dev nadal może **Ollama** bez Azure; **testy automatyczne** nie wymagają prawdziwego Azure — patrz **[S18]** (mock / env testowy).

**Konsekwencje:** `llm_service` + rozszerzenie ustawień użytkownika; test z mockiem Azure; macierz [`02_code_usage_matrix.md`](02_code_usage_matrix.md). Profil gracza + „bring your own key” — osobna epik po MVP konta.

---

### [S18] Konfiguracja LLM — jedno centralne miejsce w systemie — 2026-05-03

**Status:** accepted (**uzgodnienie produktowe:** 2026-05-01). Refaktor kodu — osobny ticket.

**Kontekst:** Źródło modelu / endpointu nie może być rozproszone bez hierarchii (**frontend**, admin, testy, env).

**Uchwała:**

1. **Źródło prawdy:** Efektywna konfiguracja wywołań LLM **rozstrzyga się w backendzie** w jednym pipeline’ie (jedna funkcja „resolve effective LLM config”). **Hierarchia (MVP ustaleń):**  
   - Jeśli użytkownik ma ustawione **Custom** — wygrywa **to** (własny endpoint / model zapisany w profilu ustawień LLM).  
   - Jeśli **Default** — obowiązuje **domyślna konfiguracja środowiska** (to, co **admin / serwer** ustawia jako standard, np. przez `LLM_*` lub przyszły panel operatora).  
   - (**Na później**, jeśli wrócimy do pomysłu): opcjonalne nadpisanie **per kampania** — tylko jako jawny wpis i osobna uchwała.

2. **Tryb w UI (gracz):** Dwie wyraźne opcje: **Default** (= korzystaj z ustawień serwera / admina) oraz **Custom** (= własny wybór); przy Custom **użytkownik** wygrywa z defaultem serwera.

3. **Żadnego równorzężnego drugiego konfiguratora:** Front gry, panel admina, CLI — **jedno API** ustawień; testy — **jeden** mechanizm env/fixture zgodny z dokumentacją.

4. **Testy / CI („co to znaczy”):** **Automatyczne testy** (pytest, CI po pushu) mają iść na **mock LLM** lub **fałszywy adres** z **env testowego**, żeby **nie wymagać** prawdziwego klucza Azure u każdego developera i żeby CI nie łączyło się z chmurą. Test integracyjny „prawdziwy Azure” — tylko **świadomie** (oznaczony, opcjonalny, z sekretem w CI).

5. **Audyt:** Provider i **anonimowy** identyfikator deploymentu (bez kluczy) w logach kontekstu — jedna ścieżka po resolverze.

**Konsekwencje:** Refaktor `llm_service` i routerów; jeden dokument „jak ustawić LLM”; powiązanie z **[S17]**.

---

### [S19] Mapa bitwy i taktyka — fazy (MVP vs przyszłość) — 2026-05-03

**Status:** accepted (**uzgodnienie produktowe:** 2026-05-01). Uzupełnia **[S12]** (AOE bez mapy na MVP).

**Kontekst:** Żeby „mapa później” nie było pustym hasłem — potrzebna jest **minimalna ram faz**, bez projektowania siatki w tym dokumencie.

**Uchwała:**

1. **MVP — brak mapy taktycznej w silniku:** Nie przewidujemy w tej fazie **planszy** (siatka heksów/kwadratów), **tokenów** na mapie w bazie ani **solvera geometrii** obliczającego automatycznie „kto stoi w promieniu” czaru. Liczby **`range_m`** i **`aoe_radius_m`** (**[S12]**) są **kotwicą zasad i narracji** — żeby LLM / gracz / katalog mówili jednym głosem o metrażu.

2. **Kto jest w zasięgu / w obszarze (MVP):** Rozstrzygane **narracyjnie** (opis sytuacji, uzgodnienie z MG/AI), **nie** przez automat liczący z pozycji na siatce.

3. **Faza późniejsza:** **Taktyka na mapie** (np. strefy abstrakcyjne, hex, tokeny, automatyczne AOE, integracja z zewnętrznym narzędziem) — **osobna uchwała i backlog**, po MVP walki/narracji; nie blokuje prac nad **[S12]** w katalogu.

**Konsekwencje:** Produkt i książka gracza **nie obiecują** ekranu mapy do czasu osobnej decyzji; implementacja silnika bez modelu pozycji w DB w MVP.

---

### [S20] Panel admin — asystent konwersacyjny LLM dla Game design i katalogów — 2026-05-03

**Status:** accepted (**uzgodnienie produktowe:** 2026-05-01). Implementacja UI + API — osobne ticket’y (**[S16]**).

**Kontekst:** **[S13]** przewiduje LLM pomagający złożyć poprawny `effect_json`. Produktowo **ten sam model pracy** ma obejmować **cały obszar**, który dziś jest realizowany jako moduł **Game design** w panelu ([`game_design.js`](../../frontend/admin_panel/sections/game_design.js) i spójne zakładki **[S15]**), nie tylko jedno pole JSON.

**Uchwała:**

1. **Generator konwersacyjny:** Dla sekcji **Game design** oraz — **tym samym wzorcem UX** — dla pozostałych **zakładek katalogu** z edycją podłączoną do **schematu** (bronie, przedmioty, warunki, DC, umiejętności itd., wg kolejności wdrożenia) ma być dostępny **asystent LLM w formie rozmowy**: admin opisuje **jaki efekt / rekord** chce osiągnąć → model **proponuje** dane strukturalne (JSON lub pola rekordu zgodne z API), które **najpierw** przechodzą **walidację** (**[S13]**, import **[S7]**), potem **akceptację lub ręczną korektę** przez admina.

2. **Nie zastępuje edycji ręcznej:** Asystent **wspiera** i przyspiesza; zapis treści nadzorowany.

3. **Konfiguracja LLM:** Wywołania przez **centralny resolver** (**[S18]**); asystent admina może mieć **inny profil** (koszty, timeout, model) niż narracja gracza — do rozdzielenia przy implementacji.

4. **Spójność z Figmą / przebudową:** **[S16]** — jedna rodzina komponentów „asystent + podgląd + walidacja” zamiast osobnych prototypów per zakładka.

**Konsekwencje:** Backlog: endpoint(y) asystenta, kontekst systemowy ze schematem kolumn / JSON Schema per zakładka; dokumentacja dla operatorów; testy z mockiem LLM (**[S18]**).

---

### [DESIGN] Faza rozszerzonego projektowania — 2026-05-03

**Status:** informational (nie jest uchwałą mechaniki — organizacja pracy)

**Treść:** Pakiet **`07_extended_design_spec.md`** zbiera projekt pod **[S12]–[S20]** oraz sekcje pomocnicze (AC, import, kampania, XP statów, Figma/stack, Azure, **centralny LLM §12**, **mapa §1.1**, **asystent admin §10**). **Następny krok zespołu:** przegląd → zmiana **proposed** → **accepted** w osobnych commitach lub jednej sesji.

---

## Wpis startowy — brak uchwał (stan początkowy)

### [INIT] Rozpoczęcie fazy 9B — 2026-05-01

**Status:** accepted

**Kontekst:** Faza audytu rozpoczęta; dokumentacja w [`00_brief.md`](00_brief.md) i macierz w [`02_code_usage_matrix.md`](02_code_usage_matrix.md) opisują **stan wyjściowy kodu**, nie przyszłe wymagania.

**Uchwała:** Do czasu pierwszego spotkania wg [`03_discussion_agenda.md`](03_discussion_agenda.md) **brak wiążących decyzji** dotyczących finesse, `effect_json`, synchronizacji `game_config_skills` z `dice.py` ani automatycznego wyboru DC.

**Konsekwencje:** Książka zasad w [`player_rulebook/00_outline_and_tone.md`](player_rulebook/00_outline_and_tone.md) musi **nie obiecywać** mechanik, które nie są w `04_decisions_log.md` — do czasu ich uchwalenia opisuj wyłącznie to, co wynika z macierzy („w kodzie jest / nie ma”).

**Powiązane pliki:** [`02_code_usage_matrix.md`](02_code_usage_matrix.md)

---

## Miejsce na kolejne uchwały

_(Dodawaj poniżej, najnowsza uchwała na dole lub na górze — wybierz jedną konwencję i trzymaj się jej.)_
