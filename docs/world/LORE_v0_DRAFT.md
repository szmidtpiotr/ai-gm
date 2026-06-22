# LORE v0 — SZKIC FUNDAMENTU ŚWIATA

> **Status:** szkic roboczy (v0). NIE jest kanonem. Czeka na decyzje Piotra (sekcja na końcu).
> **Cel:** spójny fundament lore zasilający dział „Świat" wizytówki (#905 / W4). Zadanie #911 (W10).
> **Zasada nadrzędna:** ten dokument OPISUJE świat, który **już istnieje w grze** (lokacje, wrogowie, NPC, zaklęcia, prose Księgi Zasad). Nie wymyśla rzeczy sprzecznych z grą. Każda sekcja oznacza wyraźnie:
> - 🟢 **[GRA]** — fakt zakotwiczony w istniejącej zawartości (DB, system_prompt, Księga Zasad),
> - 🟡 **[NOWE]** — propozycja Claude'a spajająca fakty w całość (do akceptacji/odrzucenia).

---

## ŹRÓDŁA, NA KTÓRYCH OPARTO TEN SZKIC

Świat zbudowano **wyłącznie** z tego, co jest już w grze:

- **`backend/prompts/system_prompt.txt`** — ton: „mroczny, brudny świat fantasy", przemoc ma konsekwencje, NPC mają motywacje. Jedyna waluta: **Złote Monety (GP / dukaty)**. Magia: arkana (Uczony), kondycje (klątwa, błogosławieństwo, furia, krwotok…).
- **Księga Zasad** (`frontend/front/rules/index.html`) — kanoniczny ton wprost: *„Świat jest stary, mokry i nieżyczliwy. Imperium trzyma się kupą strachu i podatków; na jego skraju prawo jest tym, co zdoła wyegzekwować najbliższy człowiek z mieczem. To nie kraina herosów w lśniących zbrojach — lecz ludzi, którzy próbują dożyć do rana."* Bohater-archetyp: **Mizel** złodziej, gospoda „Pod Złamanym Rogiem", Marta karczmarka, zleceniodawca z sygnetem.
- **`knowledge_book`** (lore) — **Vilnograd** stolica regionu, siedziba króla; trzy nieformalne siły: gildie kupieckie, świątynia Światła, dzielnica złodziei; legendarna **Rada Czterech** (anonimowi mecenasi). **Pradawni** — zaawansowana cywilizacja sprzed setek lat; ruiny pełne pułapek i nieumarłych; *„opanowali moc rdzenia i to zniszczyło ich cywilizację"*.
- **`game_locations`** (~30 kanonicznych makro-lokacji z opisami i atmosferą) — patrz pełna lista poniżej.
- **`npcs`** (~38 NPC z imionami i rolami) — kowale, zielarki, sołtysi, kapitanowie, komendanci, mnisi.
- **`game_config_enemies`** (~58 wrogów) — od kobolda/goblina po Lisza, Pana Demonów, Smoka; mocny wątek **nieumarłych** i **mrocznych kultów**.
- **`game_config_spells`** (37 zaklęć) — szkoła arkany Uczonego (ogień/mróz/błyskawica/nekromancja/przywołania).
- **`game_config_archetypes`** — Wojownik, Uczony (mag), Łotrzyk.

---

## 1. TON I MOTYWY  🟢 [GRA]

To **mroczne fantasy w odcieniu „grimdark z iskrą"** — nie czysty grimdark beznadziei, ale też nie heroiczna epika. Kanoniczna teza świata (cytat z Księgi Zasad): *„To nie kraina herosów w lśniących zbrojach — lecz ludzi, którzy próbują dożyć do rana i czasem, raz na jakiś czas, zrobić coś, co ma znaczenie."*

Filary tonalne (wszystkie potwierdzone w grze):
- **Brud i bieda zamiast splendoru.** Błotniste miasteczka, kwaśne piwo, torfowy dym, podatki. Bohaterowie to najemnicy, złodzieje, ocaleńcy — nie wybrańcy.
- **Przemoc ma cenę.** Silnik liczy rany, krwotoki, wyczerpanie, śmierć. Świat nie wybacza pochopności.
- **Złoto rządzi.** Jedyna waluta to dukat. Lojalność, milczenie i pomoc kupuje się monetą (system_prompt: usługi mają twarde ceny; NPC pamiętają przysługi i zniewagi).
- **Mrok nadnaturalny czai się na obrzeżach.** Im dalej od miast i traktów, tym gęściej: nieumarli, kulty, klątwy, pradawne ruiny.
- **Nadzieja jest mała, ale realna.** Świątynia Światła, błogosławieństwo, klasztory uzdrowicieli — dobro istnieje, lecz jest kruche i kosztowne.

**Motyw przewodni (propozycja spinająca):** 🟡 [NOWE] *„Cywilizacja na cofającej się fali"* — ludzkie Imperium kurczy się, a w pustkę po nim wraca to, co stare i głodne (nieumarli, bestie, kulty pradawnych). Każda przygoda to jeden mały bój o utrzymanie światła w jednym oknie.

---

## 2. GEOGRAFIA / KRAINY  🟢 [GRA] + 🟡 [NOWE] (grupowanie)

Świat ma jedną spójną mapę regionu (~30 nazwanych makro-lokacji w bazie). Poniżej pogrupowane w **6 krain** — same lokacje są 🟢 [GRA]; podział na regiony i ich nazwy zbiorcze to 🟡 [NOWE] propozycja porządkująca.

### A. Serce Królestwa (rdzeń cywilizacji) 🟢
- **Vilnograd, Stolica** — kamienne miasto króla, szare dachy, czarny dym kuźni. Trzy siły: gildie, świątynia Światła, dzielnica złodziei; w cieniu **Rada Czterech**.
- **Volhynia, Miasto Kupieckie** — skrzyżowanie czterech traktów, magazyny pękają od towaru.
- **Klasztor Iskry, Centrum Wiary** — białe mury widoczne z 20 mil, mnisi w szarych habitach. Ośrodek świątyni Światła.
> Charakter: porządek, handel, podatki, intrygi. Najbezpieczniej — i najwięcej noży w plecach.

### B. Pogranicze i wsie (codzienność i strach) 🟢
- **Cieszowice** (miód i kradzież kur), **Brzezino** (drwale, blisko Boru Zmarłych), **Wolanka** (wioska górnicza), **Most Czarnej Rzeki** (poborcy myta), **Karczma Pod Trzema Krukami** (skrzyżowanie, plotki i ukrywający się), **Pustelnia Świętego Marcina**, **Zgliszcza** (spalona wieś).
- **Strażyn, Twierdza Graniczna** — kamienna forteca, od 200 lat strzeże traktu przed wschodnimi barbarzyńcami.
> Charakter: zwykli ludzie na granicy mroku. Tu zaczyna się większość historii (zob. otwarcie Mizela).

### C. Mroczne ostępy (las i bagno) 🟢
- **Bór Zmarłych** / **Las Czarnych Drzew** — lasy nawiedzone, cienie wstają po zmroku, pnie czarne jak smoła.
- **Bagienna Knieja**, **Trzęsawiska Mgieł** — mokradła, utopce, mgła pożerająca wędrowców.
- **Step Wilków** — bezkresny step, watahy, 50 mil traktu.
> Charakter: dzicz, w której znika się bez śladu. Dom wilkołaków, harpii, jaszczuroludzi, watah.

### D. Korona Gór i mrozu (północ/wyżyny) 🟢
- **Krzyż Gór** (najwyższe pasmo), **Lodowy Pas** („Tron Białej Bogini"), **Tundra Wiecznego Mrozu**, **Czarne Skały, Wulkan** (siarka, popiół), **Kopalnia Czarnego Hutmana** (przeklęta srebrna kopalnia, krasnoludy odeszły).
> Charakter: surowa północ, wymarłe kopalnie, „Biała Bogini" tubylców. Krasnoludy = ślad po nich, nie żywa frakcja.

### E. Wybrzeże Łez (morze i bezprawie) 🟢
- **Czarnogród, Port** (smolisty, kontrabanda), **Zatoka Topielców** (pirackie miasto bez prawa), **Wybrzeże Łez** (sztormy łamią statki, po burzy znajduje się ciała).
> Charakter: morze jako żywioł i grób. Piraci, przemytnicy, coś dużego pod wodą (wątek Dziadka Floriana).

### F. Pustkowia i pradawne ruiny (zapomniana epoka) 🟢
- **Pustkowie Solne** (biała równina soli, brak wody), **Świątynia Pradawnych** („wnętrze martwego boga"), **Ruiny Pradawnego Klasztoru**, **Krypta Krwawego Hrabiego** (wampir), **Twierdza Bezimiennego** (klątwa, nikt nie wrócił).
> Charakter: tu mieszka przeszłość, która powinna umrzeć. Dungeony, nieumarli, klątwy, moc „rdzenia" pradawnych.

---

## 3. FRAKCJE / SIŁY

### 🟢 [GRA] — potwierdzone w grze
- **Korona / Imperium** — król w Vilnogradzie, straż królewska (Kapitan Henryk Miecław werbuje najemników), twierdze graniczne (Komendant Bożena Groźna w Strażynie). Trzyma się „strachu i podatków".
- **Świątynia Światła** — wiara dominująca; Klasztor Iskry (Matka Urszula, przeorysza), uzdrowiciele (Brat Kazimierz, Brat Tomasz Kronikarz zbierający relikwie). Mechanicznie: błogosławieństwo, święte światło, leczenie.
- **Gildie kupieckie** — Volhynia/Vilnograd; Brat Aleksy Złotnik (gildmistrz) płaci za szlaki i eliminację konkurencji.
- **Dzielnica złodziei** — trzecia siła Vilnogradu (świat Mizela: złodzieje, zleceniodawcy z sygnetem).
- **Rada Czterech** — anonimowi mecenasi, „prawdziwa władza" za tronem (lore knowledge_book). Idealny hak intryg.
- **Mroczne kulty** — Mroczny Kapłan, Kapłan Mrocznego Kultu, kultiści, Mroczni Czarodzieje; przyzywają demony (Pan Demonów „przyzwany przez szalony kult").
- **Plaga nieumarłych** — Lisz, wampiry (Mistrz Wampirów, Krwawy Hrabia), nieumarli mistrzowie, ghule, widma, duchy. Najgęściej w ruinach i Borze Zmarłych.
- **Piractwo / bezprawie** — Zatoka Topielców jako miasto-twierdza bez prawa.
- **Dzicz / bestie** — orkowie (Wódz Orków, szamani), gobliny, trolle, wilkołaki.

### 🟡 [NOWE] — proponowane napięcia spajające (do akceptacji)
- **Korona vs Rada Czterech** — jawna władza króla kontra ukryta władza pieniądza.
- **Światło vs Kulty** — kościelna ortodoksja kontra rozprzestrzeniające się kulty mroku/demonów; oba walczą o dusze pogranicza.
- **Cywilizacja vs powracający mrok** — wspólny wróg wszystkich frakcji (nieumarli, pradawne ruiny), który mimo to nie potrafi ich zjednoczyć.

---

## 4. PANTEON / SIŁY WYŻSZE

### 🟢 [GRA] — zakotwiczone
- **Światło** — bóstwo/zasada wiary państwowej (świątynia Światła, błogosławieństwo, „święte światło ostawia bohatera na 1 HP" — mechanika `blessed`).
- **Mrok / mroczne bóstwa** — realnie czczone przez kulty; nekrotyczna moc kapłanów płynie „przez symbol ich boga"; demony są przyzywalne (Pan Demonów, impy).
- **Biała Bogini** — tubylcze bóstwo północy (Lodowy Pas = „Tron Białej Bogini").
- **Pradawni** — wyższe istoty z czasów przed-ludzkich; Świątynia Pradawnych to „wnętrze martwego boga". Opanowali „moc rdzenia", co ich zniszczyło.
- **Arkana** — magia Uczonego: nie boska, lecz wiedza/energia. 5 tierów, szkoły ognia/mrozu/błyskawicy/nekromancji/przywołań. Mistrzostwo przez praktykę; miscast karze przy Nat 1.

### 🟡 [NOWE] — propozycja spójności metafizycznej
**„Rdzeń" jako oś metafizyki świata.** Pradawni czerpali z **Rdzenia** — pierwotnego źródła mocy pod światem. Nadużycie go zniszczyło ich cywilizację i „popękało" granicę między światem żywych a tym, co za nią (stąd nieumarli i demony przeciekają w ruinach). Arkana Uczonego to ostrożne, okruchowe czerpanie z tego samego źródła — dlatego miscast jest groźny. Światło i mroczne bóstwa byłyby wtedy dwoma sposobami radzenia sobie z pękniętą rzeczywistością: jeden ją łata, drugi ją poszerza.
> To **otwarte pytanie projektowe** — patrz DECYZJE (czy bogowie są realni, czy to wiara/Rdzeń).

---

## 5. HISTORIA ŚWIATA (epoki)

### 🟢 [GRA] — fakty z gry
1. **Epoka Pradawnych** — przed-ludzka cywilizacja, „zaawansowana", opanowała moc rdzenia → samozagłada. Zostawiła ruiny pełne pułapek i nieumarłych.
2. **Powstanie Imperium ludzi i Korony** — król w Vilnogradzie, świątynia Światła jako wiara państwowa.
3. **200 lat wojen granicznych** — Strażyn strzeże traktu „od dwustu lat" przed wschodnimi barbarzyńcami (twardy fakt z opisu twierdzy).
4. **Teraźniejszość — cofanie się porządku** — wsie palone (Zgliszcza, rok temu), kopalnie porzucane (Czarny Hutman, 20 lat temu krasnoludy odeszły), las umarłych się rozrasta.

### 🟡 [NOWE] — propozycja narracji łączącej epoki
- **Wielkie Pęknięcie** — moment, gdy Pradawni nadużyli Rdzenia; granica światów pękła, mrok zaczął przeciekać. To „grzech pierworodny" świata.
- **Era Latarni** — ludzkie Imperium wzniosło się jako „latarnia" porządku po Pęknięciu; świątynia Światła powstała by trzymać mrok w ryzach.
- **Zmierzch Latarni (teraz)** — Imperium słabnie, podatki rosną, granice się cofają; mrok wraca tam, skąd go wyparto. Era bohaterów-najemników, bo Korony nie stać już na regularne armie wszędzie.

---

## 6. LEGENDY / HAKI PRZYGODOWE

### 🟢 [GRA] — gotowe haki już w bazie (NPC quest-giverzy)
1. **Coś pod wodą** — Dziadek Florian (Zatoka) widział „coś dużego" pod falami i szuka śmiałka.
2. **Drwale, którzy nie wracają** — Sołtys Benedykt (Brzezino) martwi się o ludzi ginących w Borze Zmarłych.
3. **Stukanie w martwej kopalni** — Starszy Konrad (Wolanka): krasnoludy odeszły, ale „coś" wciąż stuka w Czarnym Hutmanie.
4. **Niepokój w Cieszowicach** — Sołtys Wiktor: „coś niepokoi wioskę od tygodni".
5. **Relikwie dla Kronikarza** — Brat Tomasz płaci za każdy artefakt pradawnych (pretekst do dungeon-crawlu po ruinach).
6. **Robota dla Korony** — Kapitan Miecław / Komendant Groźna werbują do dyskretnych zadań na pograniczu.

### 🟡 [NOWE] — mityczne miejsca i tajemnice spajające świat
1. **Tron Białej Bogini** (Lodowy Pas) — czy „Biała Bogini" to martwa Pradawna, śpiąca pod lodem? Legenda mówi, że kto wejdzie najwyżej, usłyszy jej głos.
2. **Krwawy Hrabia** — wampir z krypty był niegdyś rycerzem Korony; jego klątwa to ostrzeżenie, co spotyka tych, którzy targują się z mrokiem.
3. **Twierdza Bezimiennego** — „nikt z tych, co weszli, nie wrócił". Czołowy dungeon-mit świata; co strzeże nienaruszonych murów?
4. **Sekret Rady Czterech** — kim są mecenasi rządzący zza tronu? Hak intrygi miejskiej dla Vilnogradu.
5. **Rdzeń pod Świątynią Pradawnych** — „wnętrze martwego boga"; źródło mocy, które zniszczyło Pradawnych — i które ktoś mógłby chcieć obudzić.

---

## DECYZJE DLA PIOTRA

Te punkty rozstrzygają kierunek świata — Claude ich **nie przesądza sam**. Każdy ma warianty:

### D1. Ton — jak ciemno?
**A)** Pełny grimdark (beznadzieja, bohaterowie też są szarzy). **B)** „Grimdark z iskrą" — mrok dominuje, ale dobro/nadzieja są realne, choć kosztowne (obecny ton Księgi Zasad). **C)** Heroic-dark — mroczna sceneria, ale bohaterowie wyraźnie po jasnej stronie.
*Rekomendacja Claude'a: B (zgodne z istniejącą prozą).*

### D2. Czy bogowie są realni?
**A)** Bogowie istnieją obiektywnie (Światło, mroczne bóstwa działają realnie). **B)** To tylko wiara + jeden mechanizm (Rdzeń) — „cuda" i „klątwy" to różne czerpania z tego samego źródła. **C)** Celowa niejednoznaczność — gra nigdy nie potwierdza.

### D3. Jedna mapa świata czy multiwers kampanii?
**A)** Jeden spójny kontynent — wszystkie kampanie dzieją się w tym samym regionie (sprzyja reużyciu lokacji, mapie heksowej). **B)** Multiwers — każda kampania to osobny świat, lore to tylko domyślny szablon. **C)** Jeden rdzeń + „dalekie krainy" generowane per kampania.
*Uwaga techniczna: system reużycia lokacji i mapa heksowa sugerują A.*

### D4. Czym był/jest „Rdzeń"?
**A)** Akceptuję „Rdzeń + Pęknięcie" jako oś metafizyki (sekcja 4/5). **B)** Wolę inny pomysł na to, czemu pradawni upadli. **C)** Zostawmy to tajemnicą, bez wyjaśnienia w lore wizytówki.

### D5. Czy nazwy 6 krain (Serce Królestwa, Korona Gór, Wybrzeże Łez…) wchodzą do kanonu?
**A)** Tak, używamy ich jako oficjalnych regionów. **B)** Tylko jako nieformalne grupowanie na wizytówce. **C)** Chcę inne nazwy / inny podział.

### D6. Rola krasnoludów / elfów / nieludzi?
W grze: krasnoludy = „odeszli" (ślad, nie frakcja), mroczne elfy/dark elf jako wrogowie, brak żywych dobrych nieludzi. **A)** Świat ludzi — nieludzie to relikt/wróg/dzicz (obecny stan). **B)** Dodać żywe frakcje nieludzi (grywalne/sojusznicze). **C)** Tylko ludzie + bestie, reszta to legendy.

### D7. Główne napięcie świata na wizytówce?
Co ma być „pierwszym zdaniem" działu Świat? **A)** Korona vs Rada Czterech (intryga). **B)** Światło vs Kulty (religia/mrok). **C)** Cywilizacja vs powracający mrok (kosmiczne zagrożenie). **D)** „Zwykli ludzie próbują dożyć do rana" (kameralny, jak Księga Zasad).

### D8. Status archetypów w lore
Wojownik / Uczony / Łotrzyk — **A)** to po prostu role mechaniczne, bez osadzenia w lore. **B)** każdy ma miejsce w świecie (np. Uczeni = cech/akademia arkany, Łotrzycy = gildie złodziei z Vilnogradu, Wojownicy = najemnicy/straż). **C)** rozbudować później, teraz pominąć.

---

*Koniec szkicu v0. Po decyzjach Piotra → v1 (kanon) → zasilenie działu „Świat" wizytówki (#905).*
