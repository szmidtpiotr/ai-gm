# CZARNOBÓR — rozdział krainy (baza wiedzy świata)

> **Status:** design w trakcie domykania (dyskusja z Piotrem 2026-07-20). Zatwierdzone: oś „Bór milknie", hub **Szept Koron**, smaczki (próchno+dziegieć), konflikt drwali. Otwarte: **[DO WYBORU]** imiona elfów, **[DO AKCEPTACJI]** doprecyzowane Czarne Serce.
> Rozwija LORE_v1_KANON.md (sekcja 3C). Kraina rasy: **elf leśny** (#1474 — mechanika NIEwdrożona; seedowanie krainy i wdrożenie rasy pójdą w przybliżeniu równolegle, gdy przyjdzie etap wykonawczy; teraz TYLKO planowanie).

---

## 1. Charakter krainy

Dzicz, w której znika się bez śladu. Las tak stary, że pamięta czasy przed Imperium — i tak głęboki, że słońce dochodzi tylko do połowy. Kraina elfów: strażników, którzy od wieków trzymają w ryzach to, co pęka pod korzeniami. **Filar klimatu:** bór nie jest tłem — jest stroną w grze. Słucha, odpowiada i coraz częściej milczy.

## 2. Historia (rozbudowa kanonu)

1. **Stare granice.** Na długo przed Imperium elfy nastroiły sieć **stróżowych drzew** — żywych wardów trzymających pęknięcia Rdzenia w borze. Strojenie (magia elfów — patrz #1474 Uczony-Stroiciel) to nie władza nad lasem, lecz nieustanna pielęgnacja: pieśń podtrzymywana pokoleniami.
2. **Czarne drzewa = wygasłe wardy.** Pień stróżowego drzewa, które zgasło albo zostało przestrojone, czernieje jak smoła. **Bór Zmarłych i Las Czarnych Drzew** to pierwszy wygasły okręg sieci — dlatego czarny las się rozrasta (kanon 🟢).
3. **Schizma.** Część elfów uznała strojenie za niewolę wobec pęknięć — zaczęli je rozdzierać, by wziąć moc wprost. To dzisiejsze **mroczne elfy** (wrogowie w grze 🟢). Odeszli w głąb boru i na południe, ku Martwym Pustkowiom.
4. **Dziś: BÓR MILKNIE.** Stróżowe drzewa gasną jedno po drugim, coraz szybciej. Przyczyna nieznana — mroczne elfy? coś z Pustkowi? — celowo nierozstrzygnięta (tajemnica krainy).

## 3. Napięcia krainy

1. **Krąg Starszych vs zwiadowcy** — zamknąć się i cierpliwie stroić, czy otworzyć i szukać przyczyny na zewnątrz? (Lustro konfliktu rodów krasnoludzkich, inny smak.)
2. **Elfy vs drwale** — ludzie z zachodniego skraju wycinają las; nieświadomie ścięli już stróżowe drzewa. Dla elfów świętokradztwo, dla drwali chleb. **Konflikt bez złoczyńcy** — zatwierdzony jako drugi silnik questów.
3. **Bór vs wszyscy** — czarny las rośnie; kto nie ucieka, ten się cofa.

## 4. Lokacje

### Zasiedlone

| Lokacja | Typ | Opis |
|---|---|---|
| **Szept Koron** | osada w koronach drzew, **hub elfów** | Ludzkie tłumaczenie elfickiej nazwy. Sub-lokacje: Krąg Starszych, Pieśniarnia, Łukodzielnia, **Gościnne Drzewo** (jedyne miejsce, gdzie obcy mogą nocować), Targ Wymienny. |
| **Ostęp Graniczny** | osada wymiany (zachód) | Jedyne stałe okno handlu elfy↔ludzie; kupcy z Kresów. |
| **Obóz Drwali** | ludzki obóz, skraj zachodni | Silnik konfliktu wycinki; starosta z rodzinami do wykarmienia. |
| **Smolarnia na Palach** | osada bagienna | Ludzcy smolarze — dziegieć (ekonomia regionu). |
| **Stanica Wilcza** | step | Sezonowi łowcy wilków z Kresów; futra. |

### Istniejące POI (z pliku seedu — zostają, typy do naprawy)

Bór Zmarłych · Knieja Czarnych Drzew · Trzęsawiska Mgieł · Bagienna Knieja · Step Wilków.

### Miejsca opuszczone / zapomniane

| Lokacja | Opis |
|---|---|
| **Milczące Drzewa** (3-4 rozsiane) | Wygasłe stróżowe drzewa — każde z własną historią; mini-questy (analog Wyssanych Hołdów z Grań). |
| **Stare Gniazdo** | Pierwsza osada elfów — dziś w sercu Boru Zmarłych; opuszczona, gdy drzewa sczerniały. Dungeon questowy. |
| **Utopiona Wieś** | Ludzka wieś pochłonięta przez trzęsawisko; utopce — **farmowalny dungeon seed**. |
| **Polana Schizmy** | Miejsce rozłamu; elfy tam nie chodzą; trawa rośnie czarna. |
| **Kurhan Wilczego Króla** | Step; przedelficki kurhan — wilki go okrążają, ale nigdy nie wchodzą. |
| **Zarośnięty Trakt** | Stary imperialny trakt na południe ku Pustkowiom, zjedzony przez las. Czemu Imperium porzuciło drogę? |
| **Czarne Serce** | Patrz §7 — mit krainy. |

## 5. Teren + geografia

Pasy: **zachód** = zwykły las + trakt z Kresów + Ostęp Graniczny/drwale; **płd-zachód** = `czarny_las` (Bór Zmarłych — rozrasta się ku Kresom, po tamtej stronie granicy siedzi Birkenwald); **centrum** = głęboka knieja + Szept Koron; **południe** = bagna + `trzesawisko` → przejście ku Martwym Pustkowiom; **wschód/płn-wschód** = `step` (Step Wilków, kraniec kontynentu).

**Nowe typy terenu (kafle FLUX .170):** `czarny_las` (smoliste pnie), `trzesawisko` (mgła nad wodą), `step` (trawy po horyzont).

**Budżet** (plik seedu: 2500 hexów, 94% forest): forest ~1300 · step ~350 · czarny_las ~250 · trzesawisko ~200 · swamp ~200 · polany heath ~150 · oczka wodne i strumienie. Uwaga wykonawcza: DB nie zawiera hexów Czarnoboru — pierwszy seed pójdzie z przerobionego pliku, nie z DB.

## 6. Smaczki mechaniczne **[ZATWIERDZONE]** — niemagiczne, istniejące silniki

| Przedmiot | Działanie | Silnik |
|---|---|---|
| **Próchno świetlne** | Zimne światło z próchna czarnodrzewu. Pochodnia nocą w borze PODBIJA szansę spotkań (światło przyciąga) — próchno nie. Wybór: widzę lepiej vs jestem widoczny. | light-flag #1397 + encounter modifier |
| **Dziegieć czarnodrzewny** | Smarowidło maskujące zapach: bonus do skradania / mniejsza szansa spotkań z bestiami na hexach leśnych, 1 dzień. | kondycje/consumables |

Ekonomia regionu: **dziegieć + futra + drewno** (lustro soli i srebra Grań). Przy implementacji: wpis do **Księgi Zasad** i **wizytówki** (dział Świat) — jak sól.

## 7. Czarne Serce **[DO AKCEPTACJI — doprecyzowane]**

**Czym jest:** miejsce, gdzie rosło **Pradrzewo** — pierwsze i najgłębiej nastrojone stróżowe drzewo, kotwica całej sieci. Gdy zgasło (pokolenia temu), sczerniał cały okręg wokół — tak powstał Bór Zmarłych. Pod martwymi korzeniami Pradrzewa zieje największe pęknięcie Rdzenia w krainie.

**Czego nikt nie wie:** DLACZEGO zgasło. Samo? Przestrojone przez pierwszych zdrajców? A może wygasło od środka — i wtedy cała wiedza elfów o strojeniu stoi na kłamstwie. I drugie pytanie: co dziś mieszka w pęknięciu pod korzeniami.

**Różnica wobec Lodowej Bramy (Granie):** Brama = niewiadoma całkowita (nikt nie wie, CO za nią jest). Czarne Serce = wiadomo CO tam jest, nie wiadomo DLACZEGO i CO Z TEGO WYROSŁO. Tajemnica przyczyny, nie zawartości.

**Funkcja w grze:**
1. **Grawitacja narracyjna** — wszystkie wątki krainy (gasnące wardy, mroczne elfy, rozrost czarnego lasu) wskazują w jego stronę; narrator może się nim straszyć i kusić.
2. **Endgame krainy** — finał dużej kampanii Czarnoboru może tam prowadzić (analog Hutmana dla Grań).
3. **NIE farmowalny dungeon, NIE otwierany pojedynczym questem** — na mapie hex-lokacja z opisem atmosferycznym; wejście zamknięte narracyjnie (bór nie wpuszcza: ścieżki zawracają, strach narasta). Otwarcie = osobna przyszła decyzja Piotra (kampania finałowa wątku).

## 8. Obsada krainy — NPC-ikony

Ludzie **[ZATWIERDZENI]**: **Bartel** (kupiec, Ostęp Graniczny) · **Hagen** (starosta drwali — antagonista-nie-złoczyńca) · **Wolfram** (łowca, Stanica Wilcza).

Elfy **[DO WYBORU — styl Władcy Pierścieni]**: brzmienia miękkie, śpiewne (ae/th/-ion/-el/-wen), wymawialne po polsku, bez kopiowania imion Tolkiena:

| Rola | Propozycja | Alternatywy |
|---|---|---|
| Starsza Kręgu (twarz zamknięcia) | **Elowen** | Nimriel, Aerlin |
| Przywódca zwiadowców (twarz otwarcia) | **Thalion** | Cathel, Sylvar |
| Mistrzyni strojenia, opiekunka wardów | **Loriel** | Erethil, Aerlin |
| Łukmistrz Łukodzielni | **Faelor** | Cathel, Sylvar |
| Wygnaniec na skraju boru (szary informator o mrocznych elfach) | **Morvael** | Erethil |

Nazwy miejsc elfich: elfy mają własne (niezapisywane) nazwy; ludzkie nazwy na mapie („Szept Koron") to tłumaczenia — smaczek narracyjny.

## 9. Start elfa (po wdrożeniu #1474)

Whitelist startowa krainy: default **Gościnne Drzewo** (Szept Koron); wariant: Ostęp Graniczny. Haki startowe: Loriel — „kolejne drzewo zgasło, zbadaj"; Thalion vs Elowen — dwie strony werbują gracza do swojej wizji. Do tego czasu Czarnobór działa jako zwykła kraina dla wszystkich ras (elf startuje po swojej fali wdrożeniowej).

---

*Rozdział = źródło prawdy lore krainy. Zmiany wyłącznie przez commit po dyskusji z Piotrem. Mapa: `data/regions/region_czarnobor.json` (surowy plik generatora — do przerobienia w fali seedowania; DB pusta).*
