# CZARNOBÓR — rozdział krainy (baza wiedzy świata)

> **Status:** ZATWIERDZONY (dyskusja z Piotrem 2026-07-20; imiona elfów i Czarne Serce domknięte).
> Rozwija LORE_v1_KANON.md (sekcja 3C). Kraina rasy: **elf leśny** (#1474 — mechanika WDROŻONA 2026-07-21; kraina zaseedowana CB-1…CB-8; kotwica startowa elfa czynna — patrz §9).
>
> **Stan wdrożenia (CB-9, 2026-07-24):** kraina domknięta i grywalna na DEV. 2500 heksów w `world_hexes` (`region='czarnobor'`, `map_level=0`), 21 lokacji makro + suby Szeptu Koron, 8 NPC-ikon, 9 wrogów regionu, 13 plotek, loch Utopiona Wieś, smaczki (próchno/dziegieć) czynne. Snapshot: `data/regions/region_czarnobor.json` (round-trip 1:1 zweryfikowany na kopii DB).

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

**Budżet — WDROŻONY** (2500 hexów w DB, snapshot `region_czarnobor.json`): forest 1185 · step 351 · swamp 256 · czarny_las 243 · trzesawisko 201 · heath 147 (polany) · road 101 (trakt z Kresów) · water 15 · village 1. Zgodne z założeniem „94% las" (forest+czarny_las+trzesawisko+swamp ≈ 75% + step/heath jako polany/kraniec). Trakt spójny od granicy z Kresami do Ostępu Granicznego; Szept Koron celowo poza siecią dróg (ścieżka kończy się na skraju kniei).

## 6. Smaczki mechaniczne **[ZATWIERDZONE]** — niemagiczne, istniejące silniki

| Przedmiot | Działanie | Silnik |
|---|---|---|
| **Próchno świetlne** (`prochno_swietlne`) | Zimne światło (`light_kind='cold'`). Pochodnia (`open_flame`) nocą w borze PODBIJA szansę spotkań ×1.5 — próchno nie (×1.0). Wybór: widzę lepiej vs jestem widoczny. Mnożnik działa TYLKO w nocnym marszu; w dzień oba = ×1.0. | `bor_survival_service.light_encounter_mult` → `hex_travel_service` (wartości startowe) |
| **Dziegieć czarnodrzewny** (`dziegiec_czarnodrzewny`) | Smarowidło maskujące zapach (`effect_category='scent_mask'`): bonus do skradania + mniejsza szansa spotkań z bestiami na hexach LEŚNYCH przez 1 dzień gry. Buff DZIENNY w `session_flags`, nie kondycja rundowa. | `bor_survival_service` scent_mask |

Ekonomia regionu: **dziegieć + futra + drewno** (lustro soli i srebra Grań). Przy implementacji: wpis do **Księgi Zasad** i **wizytówki** (dział Świat) — jak sól.

## 7. Czarne Serce **[ZATWIERDZONE]**

**Czym jest:** miejsce, gdzie rosło **Pradrzewo** — pierwsze i najgłębiej nastrojone stróżowe drzewo, kotwica całej sieci. Gdy zgasło (pokolenia temu), sczerniał cały okręg wokół — tak powstał Bór Zmarłych. Pod martwymi korzeniami Pradrzewa zieje największe pęknięcie Rdzenia w krainie.

**Czego nikt nie wie:** DLACZEGO zgasło. Samo? Przestrojone przez pierwszych zdrajców? A może wygasło od środka — i wtedy cała wiedza elfów o strojeniu stoi na kłamstwie. I drugie pytanie: co dziś mieszka w pęknięciu pod korzeniami.

**Różnica wobec Lodowej Bramy (Granie):** Brama = niewiadoma całkowita (nikt nie wie, CO za nią jest). Czarne Serce = wiadomo CO tam jest, nie wiadomo DLACZEGO i CO Z TEGO WYROSŁO. Tajemnica przyczyny, nie zawartości.

**Funkcja w grze:**
1. **Grawitacja narracyjna** — wszystkie wątki krainy (gasnące wardy, mroczne elfy, rozrost czarnego lasu) wskazują w jego stronę; narrator może się nim straszyć i kusić.
2. **Endgame krainy** — finał dużej kampanii Czarnoboru może tam prowadzić (analog Hutmana dla Grań).
3. **NIE farmowalny dungeon, NIE otwierany pojedynczym questem** — na mapie hex-lokacja z opisem atmosferycznym; wejście zamknięte narracyjnie (bór nie wpuszcza: ścieżki zawracają, strach narasta). Otwarcie = osobna przyszła decyzja Piotra (kampania finałowa wątku).

## 8. Obsada krainy — NPC-ikony

Ludzie **[ZATWIERDZENI]**: **Bartel** (kupiec, Ostęp Graniczny) · **Hagen** (starosta drwali — antagonista-nie-złoczyńca) · **Wolfram** (łowca, Stanica Wilcza).

Elfy **[ZATWIERDZONE — styl Władcy Pierścieni]** (brzmienia miękkie, śpiewne, wymawialne po polsku, bez kopiowania imion Tolkiena):

| Rola | Imię |
|---|---|
| Starsza Kręgu (twarz zamknięcia) | **Nimriel** |
| Przywódca zwiadowców (twarz otwarcia) | **Cathel** |
| Mistrzyni strojenia, opiekunka wardów | **Aerlin** |
| Łukmistrz Łukodzielni | **Sylvar** |
| Wygnaniec na skraju boru (szary informator o mrocznych elfach) | **Erethil** |

Nazwy miejsc elfich: elfy mają własne (niezapisywane) nazwy; ludzkie nazwy na mapie („Szept Koron") to tłumaczenia — smaczek narracyjny.

## 9. Start elfa (po wdrożeniu #1474)

Whitelist startowa krainy: default **Gościnne Drzewo** (`szept_goscinne_drzewo`, Szept Koron, hex 74,-12); wariant: **Ostęp Graniczny** (`ostep_graniczny`, hex 74,8). Haki startowe: Aerlin — „kolejne drzewo zgasło, zbadaj"; Cathel vs Nimriel — dwie strony werbują gracza do swojej wizji. Czarnobór działa też jako zwykła kraina dla wszystkich ras (elf ma dodatkowo kotwicę startową).

**WDROŻONE (CB-8):** `RACE_START["elf"]` + `RACE_PLAN_HINT["elf"]` w `race_start_service.py` (region `czarnobor`, default `szept_goscinne_drzewo`). Nowa kampania elfa startuje w Gościnnym Drzewie. Elf leśny nie gra Wojownikiem (blokada archetypu) — Zwiadowca/Uczony-Stroiciel.

---

*Rozdział = źródło prawdy lore krainy. Zmiany wyłącznie przez commit po dyskusji z Piotrem. Mapa: `data/regions/region_czarnobor.json` (snapshot DB, round-trip 1:1 zweryfikowany w CB-9; `location_key` przetrwa reseed). Wrogowie regionu: `cien_boru`, `dzik_borowy`, `mroczny_elf_lowca`, `topielec_mielizny`, `blotnik`, `harpia_stepowa`, `mara_czarnodrzewna`, `wilk_stepowy_herszt`, `utopiony_wojt` (boss). Loch: `utopiona_wies` (kafelkowy, utopce). Czarne Serce = hex-lokacja atmosferyczna bez wejścia (lore §7).*
