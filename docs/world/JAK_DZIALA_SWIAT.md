# Jak działa świat AI-GM

> **Dla kogo:** dla Piotra i dla każdego, kto ma podjąć decyzję projektową o świecie gry — bez czytania kodu.
> **Stan na:** 2026-07-21, po fali 4 (#1527). Liczby zmierzone na żywej bazie DEV.
> **Uwaga o liczbach:** wszystkie liczby lokacji dotyczą **kart aktywnych**. W bazie leży dodatkowo 257 kart miękko skasowanych (`is_active=0`) — wcześniejsze wydania tego dokumentu liczyły je razem z żywymi, stąd „485 lokacji, 425 floating". To był artefakt liczenia, nie nagłe skasowanie świata.
> **Status:** to jest ŹRÓDŁO PRAWDY o działaniu świata. Zastępuje `docs/V2_ARCHITECTURE/05_WORLD_BUILDER_AND_PERSISTENCE.md`, który opisuje model sprzed przebudowy #1243 i wprowadza w błąd.

---

## Część 0 — Streszczenie na jedną stronę

Świat AI-GM stoi na czterech filarach:

1. **Katalog lokacji** — spis wszystkich miejsc, jakie w grze istnieją. Jak książka telefoniczna: każde miejsce ma swoją kartę. Karta sama w sobie nie mówi, *gdzie* to miejsce leży.
2. **Mapa świata** — siatka heksów (sześciokątnych pól). To ona decyduje o geografii. Heks może wskazać jedną lokację i powiedzieć „tu stoi Vilnograd".
3. **Mapy lokalne** — mini-siatki *wewnątrz* osady. Karczma, kuźnia i rynek jednego miasteczka leżą na własnej małej mapce, a nie na mapie świata.
4. **Poczekalnia** — gdy narrator AI wymyśli w trakcie gry nowe miejsce, trafia ono do kolejki „Do zatwierdzenia" w panelu admina. Gra go używa, ale świat go jeszcze nie kanonizował.
5. **Kontrola świata** (od fali 4, #1527) — lampka kontrolna: lista rozjazdów w panelu zamiast cichego prostowania po nocach. Szczegóły w Części 6A.

Kluczowa zasada, która rządzi wszystkim (decyzja z 2026-07-05, #1243):

> **Heks jest prawdą.** Jeśli chcesz wiedzieć, gdzie leży dana lokacja — pytasz mapy, nie karty lokacji. Karta ma zapisane współrzędne, ale to tylko kopia dla wygody i może być nieaktualna.

Dlaczego tak: przy audycie okazało się, że współrzędne zapisane na kartach lokacji były zepsute (14 lokacji stało na (0,0), Brzeżyno miało wpisane (1,0), a fizycznie leżało na (39,9)). Mapa była czysta. Do tego na jednym heksie z definicji stoi jedna lokacja, więc konflikt „dwa miejsca w jednym punkcie" jest niemożliwy. Wygrała mapa.

---

## Część 1 — Z czego zbudowany jest świat

### 1.1 Lokacja (karta w katalogu)

**243 aktywne karty** w bazie DEV (80 makro + 163 sub-lokacje; obok nich 257 kart miękko skasowanych, których gra nie widzi). Każda ma:

| Co | Znaczenie |
|---|---|
| **klucz** | niezmienna nazwa techniczna, np. `trzech_krukow_wielka_izba` |
| **etykieta** | nazwa dla gracza, np. „Wielka Izba" |
| **typ** | `macro` = samodzielne miejsce na mapie świata (miasto, ruiny, most) · `sub` = wnętrze/część czegoś większego (izba w karczmie, rynek w mieście) |
| **rodzic** | do jakiego makro należy sub-lokacja |
| **podtyp** | karczma, kuźnia, kram, świątynia, stajnia, obóz… — decyduje o usługach i o tym, czy można odpocząć |
| **kraina** | Kresy, Siwe Granie, Czarnobór, Martwe Pustkowia, Koronne Niziny, Wybrzeże Łez |
| **teren dopuszczalny** | na jakich rodzajach heksa wolno tę lokację postawić (las, góry, step…) |
| **poziom (tier)** | 1–5, siła/ważność miejsca |

### 1.2 Mapa świata (heksy)

**5040 heksów** poziomu 0 (świat). Heks ma rodzaj terenu, atmosferę, szansę na spotkanie, krainę — i opcjonalnie wskazuje jedną lokację.

Tylko **40 heksów** faktycznie wskazuje jakąś lokację. Reszta to dzicz: teren, przez który się podróżuje, ale nie ma tam nazwanego miejsca.

### 1.3 Mapa lokalna (heksy wewnątrz osady)

**29 heksów** poziomu 1. Powstają dopiero, gdy osada ma **co najmniej 2 sub-lokacje** — wcześniej mini-mapa nie ma sensu. Sub-lokacje układają się w pierścień wokół centrum osady.

Sub-lokacja **nie ma własnego miejsca na mapie świata** — jej „adres" to heks jej osady-rodzica.

### 1.4 Floating vs placed — najważniejsze pojęcie do zrozumienia

- **placed (osadzona)** = lokacja stoi na konkretnym heksie mapy świata. Można do niej dojść, widać ją na mapie.
- **floating (unosząca się)** = lokacja istnieje w katalogu, ale **nie ma jeszcze przypisanego miejsca w świecie**.

**203 z 243 aktywnych lokacji jest floating** (osadzonych jest 40). To brzmi alarmująco, ale w większości jest poprawne, bo floating oznacza dwie zupełnie różne rzeczy:

1. **Sub-lokacje** — z definicji nie stoją na mapie świata (Wielka Izba nie jest osobnym punktem na mapie Kresów, tylko wnętrzem karczmy). To **163 z 203** floatingu i to jest w porządku.
2. **Zapas makro-lokacji** — **40** gotowych miejsc czekających na osadzenie. Silnik może je automatycznie postawić na pasującym pustym heksie o odpowiednim terenie. To celowy magazyn treści, nie śmieci.

Floating lokacja **nadal jest grywalna narracyjnie** — narrator może o niej opowiedzieć, gracz może w niej być. Traci tylko pinezkę na mapie świata.

---

## Część 2 — Skąd biorą się lokacje (14 wejść)

Lokacje wchodzą do świata **czternastoma różnymi wejściami**. Od fali 3 (#1526) wszystkie prowadzą przez **jedne drzwi** — funkcję `create_location()`, która stempluje flagi zawsze tak samo; poniższa lista mówi więc, *kto puka*, a nie *ile jest różnych zamków*. W grupach:

### A. Treść autorska (twoja, z gita)
1. **Seed z repozytorium** — pliki `data/seeds/content/game_locations.json`. Stempel: `seed`, kanoniczne, zatwierdzone. **To jest kanon świata.**
2. **Skrypty seedujące krainy** — np. `seed_kresy_obsada.py`.

### B. Panel admina
3. **Ręczne dodanie lokacji** — stempel `admin_manual`.
4. **Kreator AI (Smart Entry)** — stempel `admin_kreator`, oznaczone jako AI-owe.

### C. Kuźnia / szablony kampanii
5. **Lokacje z szablonu kampanii** — stempel `forge`, trafiają do **poczekalni**.
6. **Kotwica startowa kampanii** — miejsce, gdzie zaczyna bohater; osada-hub i jej sub-lokacje materializują się przy starcie kampanii (model #1212).

### D. Narrator w trakcie gry (najbardziej ryzykowna grupa)
7. **Znacznik lokacji od AI** — narrator wspomni nowe miejsce → powstaje karta, stempel `gm_runtime`, **poczekalnia**.
8. **Walidator ruchu** — gracz pisze „idę do Starej Kuźni", miejsca nie ma w bazie → jest tworzone w locie.
9. **Obozowisko** — „Rozbij obóz" tworzy lokację tymczasową, kasowaną przy odejściu.
12. **Zastępcza lokacja startowa** — gdy kampania startuje na heksie bez nazwanego miejsca.
13. **Scena otwarcia** — awaryjne miejsce dla nowej postaci.

### E. Generatory automatyczne
10. **Hub osady** — gdy gracz wejdzie na heks osady, która nie ma jeszcze karty.
11. **Sub-lokacje osady** — generator dosypuje do 4 miejsc (karczma/kuźnia/kram/świątynia). Stempel `auto_generated`.
14. **Skrypty testowe/naprawcze.**

**Rozkład na żywej bazie DEV (karty aktywne):**

| Kto stworzył | Ile | Uwaga |
|---|---|---|
| `seed` (git, kanon) | 181 | ← prawdziwy kanon świata |
| `forge` | 24 | szablony kampanii, w poczekalni |
| `gm_runtime` | 18 | twory narratora z tur |
| `auto_generated` | 15 | stuby wiosek i sub-lokacje generatora |
| `admin_manual` | 5 | ręczne wpisy z panelu |

Zmiana względem poprzedniego wydania (`admin_manual` 241 → 5) to skutek fal 0–3: masa ręcznych kart okazała się śmieciem runtime i została wygaszona, a kanon przejął stempel `seed`. Kart z nielegalnym stemplem jest dziś **0** — pilnuje tego fabryka z fali 3 i reguła lintu z fali 4.

---

## Część 3 — Życie lokacji: statusy i poczekalnia

Karta lokacji miała **siedem niezależnych przełączników**. Fala 2 (#1525) skasowała dwa z nich, zostało **pięć**:

| Przełącznik | Co znaczy | Kto go używa |
|---|---|---|
| **aktywna** | czy w ogóle istnieje; wyłączenie = miękkie skasowanie | wszystko |
| **zatwierdzona** | czy widoczna dla silnika świata | filtr treści |
| **kanoniczna** | czy to trwały element świata (a nie twór jednej kampanii) | mapa, seedy |
| **status recenzji** | `permanent` (przyjęta) · `pending_review` (poczekalnia) · `discarded` (odrzucona) | panel Świat → Oczekujące |
| **tymczasowa** | obozowisko — znika po odejściu | podróż |

Skasowane w fali 2 (#1525):

| Były przełącznik | Dlaczego zniknął |
|---|---|
| ~~**placement**~~ (`floating`/`placed`) | trzecia kopia odpowiedzi „czy stoi na mapie". Dziś liczy się ją z heksa (kanon), jednym helperem `is_location_placed`. |
| ~~**ai_generated**~~ | druga kopia odpowiedzi „kto stworzył". Została jedna: **kto stworzył** (`created_by`). Jej przemycone drugie znaczenie — „tekst już napisany, nie nadpisuj" — dostało własny przełącznik `enrichment_locked`. |

Dodatkowo status recenzji ma teraz **pilnowanego strażnika w samej bazie**: próba zapisania wartości spoza trzech legalnych kończy się błędem, zamiast po cichu wsadzać lokację w limbo.

### Ścieżka lokacji wymyślonej przez AI w trakcie gry

```
narrator wymyśla miejsce
   → karta powstaje: poczekalnia + niezatwierdzona
   → gra jej używa od razu (narracja działa)
   → panel admina: Świat → Oczekujące pokazuje ją tobie
       ├─ Zatwierdź  → przyjęta + zatwierdzona (+ opcjonalnie generuje sub-lokacje)
       ├─ Kanonizuj  → dodatkowo staje się trwałym elementem świata
       └─ Odrzuć     → oznaczona jako odrzucona (karta zostaje, gra jej nie użyje)
```

**Ważne:** zatwierdzenie musi przestawić **dwa** przełączniki naraz (status recenzji + zatwierdzona). Kiedyś przestawiało jeden — efekt był taki, że lokacja znikała silnikowi z oczu i przy następnym ruchu tworzyła się jej kopia. Stąd historyczne duplikaty w bazie.

---

## Część 4 — Jak gra czyta świat w czasie tury

### 4.1 Gdzie stoi drużyna

Pozycja ma **jednego zapisywacza** (`location_state_service`, porządek #1112 — wcześniej pisało ją pięć miejsc). Pozycja to trzy rzeczy trzymane w zgodzie:

- **lokacja** — w jakim miejscu jesteśmy (albo nigdzie = dzicz),
- **heks świata** — gdzie na mapie świata,
- **heks lokalny** — w której części osady.

### 4.2 Wejście do lokacji buduje scenę

Wejście do miejsca ładuje **obsadę sceny**: kto tu jest (NPC z tabeli przypisań) i co tu grozi (przeciwnicy, losowani wg szansy pojawienia). To zapisuje się jako stan sceny i dopiero to widzi narrator.

### 4.3 Co dostaje narrator

Dwa bloki kontekstu:
- **blok lokacji** — opis miejsca + miejsca sąsiednie (rodzic, rodzeństwo, dzieci — do 120 pozycji). Gdy drużyna jest w dziczy, wysyłany jest jawny blok „jesteście w terenie" — bez niego AI wymyślała budynki w szczerym polu.
- **blok ŚWIAT** — gdy jesteśmy w nazwanym miejscu, zaczyna się od „GRACZ JEST W:", a teren heksa schodzi na drugi plan jako „co zobaczycie po wyjściu".

### 4.4 Skąd gra wie, w jakiej krainie jesteś

Kolejność pytań: kraina zapisana na lokacji → kraina osady-rodzica → kraina heksa → domyślnie Kresy.

Środkowy krok jest kluczowy: sub-lokacje nie mają własnego heksa, więc zanim go dodano, **181 z 231 lokacji zgłaszało się jako Kresy** — psując reputację, plotki, wydarzenia świata i łupy w pozostałych krainach.

---

## Część 5 — Podróż i mapy lokalne

### 5.1 Podróż po świecie

Jedna wspólna ścieżka podróży (porządek #1244 — wcześniej trzy osobne). Gracz wskazuje cel; system wyznacza trasę heks po heksie (koniec teleportów, #1113). Trasa zapisuje się w planie podróży, więc przerwane spotkanie nie kasuje marszu — po walce można iść dalej.

Podróż drogą ma inną szansę na spotkanie niż na przełaj. Przybycie do **nazwanego** miejsca dostaje krótką scenę od AI; wejście na zwykły heks dziczy kończy się samą zieloną belką podróży.

Gracz może też podróżować **słowami** („idę do Wolanki"). Jeśli cel leży dalej niż heks, system awansuje to do prawdziwej podróży zamiast teleportu.

### 5.2 Mapa lokalna osady

- Powstaje **leniwie**: przy pierwszym wejściu do osady bez mapki system tworzy hub i dosypuje do 4 sub-lokacji.
- Próg: **2 sub-lokacje**. Poniżej — nie ma mini-mapy, jest zwykła lokacja.
- Ruch wewnątrz osady kosztuje 15 minut i jest ograniczony do sub-heksów **tej** osady (bez tej blokady dało się teleportować do cudzej osady i odpoczywać gdziekolwiek).
- Sub-lokacja przy pierwszym wejściu dostaje opis dopisywany przez AI.
- Kampania z szablonu może wystartować **wewnątrz** sub-lokacji — mapka jest gotowa od pierwszej tury (#1212).

---

## Część 6 — Co się dzieje przy każdym starcie serwera

Przy starcie backendu leci **automatyczne prostowanie świata**:

1. **Rozmazania** — jeśli ta sama lokacja jest przypisana do kilku heksów, zostaje jeden, reszta się czyści.
2. **Uzupełnienie kopii** — współrzędne na kartach lokacji są przepisywane z mapy (bo mapa jest prawdą).
3. **Czyszczenie/awans** — karta twierdząca, że stoi na heksie, którego mapa jej nie przyznaje: albo dostaje ten heks (jeśli wolny), albo **traci pinezkę i wraca do floating**.

Plus dosypywanie brakujących krain i terenów.

> ⚠️ **To jest ważne i nieoczywiste:** krok 3 potrafi *odpiąć od mapy* lokację, którą coś zapisało „na skróty". Dlatego każde miejsce ustawiane na mapie musi przechodzić przez jedną oficjalną funkcję — inaczej rano wraca floating. To była przyczyna błędu #1305.

**Od fali 4 (#1527) to prostowanie nie jest już nieme.** Wszystko, co start serwera naprawił, ląduje w **kronice napraw** (panel: Mapa → 🩺 Kontrola świata → 🕮 Historia napraw). Widzisz tam datę, regułę, czego dotyczyła naprawa i co dokładnie zrobiła.

> 🔍 **Drugi cichy uzdrowiciel — znalezisko z fali 4.** Prostowanie mapy to nie było jedyne miejsce, które sprzątało po cichu. Osobne sprzątanie w migracji startowej gasi pinezki i zwalnia heksy **wcześniej** niż opisane wyżej prostowanie — czyli rozjazd znikał, zanim ten mechanizm zdążył go zobaczyć. Skutek praktyczny: kto szuka „kto mi to zmienił", musi patrzeć na oba. Oba raportują teraz do tej samej kroniki, rozróżniane podpisem: „⚙️ start backendu" (prostowanie mapy i migracja) vs „👤 panel" (twoje kliknięcie).

---

## Część 6A — 🩺 Kontrola świata (lampka zamiast zamiatania)

Fala 4 (#1527) dołożyła w panelu zakładkę **Mapa → 🩺 Kontrola świata** (siedzi przy mapie, bo o mapie i osadzeniu lokacji mówi większość reguł). To odwrócenie logiki: zamiast po cichu prostować, system **pokazuje listę rozjazdów** i pozwala je naprawiać świadomie.

**Siedem reguł:**

| Reguła | Co łapie | Guzik „Napraw"? |
|---|---|---|
| **Usługa bez gospodarza** | karczma, kuźnia, kram, świątynia, stajnia, komora — bez ani jednego NPC. Gracz wchodzi do pustego wnętrza | nie — dosiew treści |
| **Sierota obsady** | NPC przypisany do lokacji, której już nie ma | tak |
| **Heks bez lokacji** | pole mapy wskazuje lokację, która nie istnieje | tak |
| **Pin bez kanonu** | karta twierdzi, że stoi na heksie, którego mapa jej nie przyznaje | tak |
| **Zepsuty rodzic** | sub-lokacja bez rodzica albo z połowicznym wiązaniem | tak |
| **Nielegalna flaga** | `created_by` / status recenzji spoza legalnego zbioru | tak |
| **Duplikat etykiety** | dwie lokacje o (prawie) tej samej nazwie w jednej krainie | nie — wybór, którą zostawić |

**Zasada podziału:** guzik pojawia się tylko tam, gdzie odpowiedź jest **jednoznaczna** (odpiąć pinezkę, zwolnić heks, uzupełnić rodzica, zdjąć martwe przypisanie). Tam, gdzie trzeba **decyzji treściowej**, panel pisze „decyzja człowieka" i niczego nie zgaduje — bo zgadywanie było właśnie tą chorobą.

**Bramka krain:** reguła „usługa bez gospodarza" liczy się **wyłącznie dla krain otwartych** (status `live` — dziś Kresy i Siwe Granie). Filtr stoi na statusie, nie na liście nazw, więc Czarnobór i Martwe Pustkowia wejdą do lintu **automatycznie w dniu otwarcia**, bez zmiany w kodzie. Powodem ich wyłączenia nie jest lore — kanon obu krain **ma** osady i usługi — tylko stan świata: zero heksów i brak lokacji-hubów.

**Pierwszy pomiar na żywej bazie DEV:** 45 rozjazdów, z czego 17 naprawialnych jednym kliknięciem. Licznik wisi jako plakietka przy pozycji „Mapa" w menu bocznym, więc widać go bez wchodzenia w zakładkę.

**Naprawa masowa — per reguła, nigdy globalnie.** Lista jest pogrupowana po regule, bo tak wyglądają realne dane: 14 sub-lokacji osieroconych po skasowanym szablonie to *jeden* problem powtórzony czternaście razy, a nie czternaście decyzji. Nad każdą grupą deterministyczną jest **🔧 Napraw wszystkie (N)** — jedno potwierdzenie, ale każda naprawa ląduje w kronice **osobno** (grupa nie chowa się za zbiorczym „naprawiono 14 rzeczy").

Czego celowo **nie ma**: guzika „napraw wszystko" dla całej listy. Taki guzik odtworzyłby dokładnie tę chorobę, którą fala 4 leczy — ciche zamiatanie, tylko z jednym kliknięciem zamiast po nocach. Naprawa masowa zawsze dotyczy jednej reguły, którą człowiek świadomie wskazał, i nigdy nie obejmuje reguł treściowych.

**Problemy „decyzja człowieka" — narzędzia zamiast ślepego zaułka.** To, że maszyna nie zgaduje treści, nie znaczy, że admin ma skakać po zakładkach. Wiersz „usługa bez gospodarza" ma guzik **👤 Obsadź gospodarza**: lista NPC, którzy nigdzie nie stoją (zajętych celowo nie proponujemy — przenoszenie gospodarza z innej karczmy tylko przesuwa dziurę), a pod nią formularz nowej postaci z podpowiedzią AI, która zna miejsce, krainę i rodzaj usługi. Wiersz duplikatu ma **⚖ Porównaj i rozstrzygnij**: obie karty obok siebie z faktami przesądzającymi wybór (źródło, status, obsada, wnętrza, pinezka na mapie) i decyzją „zostaw tę, wygaś drugą" plus opcją przeniesienia obsady i wnętrz. Karty stojącej na mapie nie da się wygasić — kanon heksa wymaga świadomego ruchu na Mapie.

**Konwencja nazw pilnowana po stronie kodu.** Podpowiadacz gospodarza dostaje regułę nazewniczą **tej** krainy (kanon #997 + rozdziały krain: elfy miękko i śpiewnie, krasnoludy nordycko z polskim przydomkiem, Piętnowani z brzmieniem arabskim, dwór Korony archaiczno-dworsko, wyspiarze krótko i samogłoskowo) plus imiona postaci, które **już stoją** w tej krainie. Dwa strażniki łapią typowe wpadki modelu: współczesne polskie imię („Agnieszka Kruk") i skopiowanie podanego przykładu albo NPC-ikony z kanonu (np. „Ravu" z Wybrzeża) — w obu wypadkach prosimy model o drugie podejście, zanim propozycja trafi na ekran. Reguły żyją w `backend/app/services/world_naming_service.py`; zmiana kanonu nazw = świadoma zmiana tego pliku.

**Znacznik 🩺 poza Kontrolą świata.** Wiersze w zakładkach Lokacje, ⚓ Floating i Do zatwierdzenia noszą znacznik przy nazwie (czerwony = błąd struktury, pomarańczowy = brak treści), a rodzic w drzewie pokazuje **🩺N** — ile problemów czeka w zwiniętej gałęzi. Dzięki temu pracując nad lokacjami widać chorą kartę od razu, bez przełączania się do lintu i z powrotem.

**Progi (wartości startowe, do strojenia):** podobieństwo nazw uznane za duplikat = **0.85**, limit listy = **200** pozycji.

---

## Część 7 — Znane choroby (i dlaczego temat wraca co tydzień)

Rdzeń projektu jest zdrowy. Problemy siedzą w **warstwach historycznych, których nie skasowaliśmy** po kolejnych przebudowach. Każda przebudowa dokładała nową prawdę, a stara zostawała — i nadal jest czytana przez kod.

### Choroba 1 — ta sama informacja w 2–3 miejscach

| Informacja | Ile kopii | Gdzie |
|---|---|---|
| ~~kto jest NPC w lokacji~~ | ~~**3**~~ → **1** | ✅ **naprawione w fali 1** (#1524): kanon = tabela przypisań `location_npc_assignments`; lista na karcie lokacji (`npc_keys`) to od teraz **kopia pochodna** odświeżana po każdym zapisie; legacy `npc_locations` nie jest już czytana ani zapisywana (pusta, DROP po weryfikacji). Zasada dodatkowa: **gospodarz siedzi w sub-lokacji**, makro-hub osady zostaje pusty. |
| ~~czy lokacja stoi na mapie~~ | ~~**3**~~ → **1** | ✅ **naprawione w fali 2** (#1525): kanon = wskazanie z heksa; współrzędne na karcie to jego lustro; `placement` skasowany, a wszystkie trzy równoległe testy „czy osadzona" zastąpił jeden helper. |
| kto jest rodzicem | **2** (świadomie) | numer rodzica i nazwa rodzica. Obie kolumny zostają — od fali 2 baza sama dopisuje brakującą połówkę (triggery), a od fali 4 połowiczne i zerwane wiązania **widać na liście** jako „Zepsuty rodzic" z guzikiem naprawy |
| ~~czy stworzyło AI~~ | ~~**2**~~ → **1** | ✅ **naprawione w fali 2** (#1525): zostaje `created_by` (enum zna też realnie zapisywane `forge` i `auto_generated` — koniec cichej podmiany na `gm_runtime`); `ai_generated` skasowany. |

**Dowód, że to nie teoria** — trzy pytania o to samo dawały trzy różne odpowiedzi:

```
                                    PRZED      PO fali 0    PO fali 2
lokacji z przełącznikiem "placed"     60           39         — (kolumna skasowana)
lokacji z wpisanymi współrzędnymi     56           39         40
heksów świata wskazujących lokację    54           39         40
```

Po fali 2 zostały **dwie** liczby zamiast trzech — i obie mówią to samo, bo druga jest wyłącznie lustrem pierwszej.

Rozbieżność miała konkretne twarze: 11 lokacji twierdziło, że stoi na mapie, choć żaden heks ich nie znał (w tym sub-lokacje Trzech Kruków, Wołanki i Wołchynii, które **z definicji** nie powinny być „placed"), a 3 heksy świata wskazywały skasowane obozowiska i rekord testowy.

✅ **Naprawione w fali 0** (#1528, commit `cc27fd22`). Od tej pory reconcile przy starcie backendu nie ma czego prostować (`cleared: 0, promoted: 0`).

Bug z gospodą „Pod Złamanym Rogiem" (#1524) to dokładnie ten sam mechanizm w wariancie NPC.

### Choroba 2 — czternaścioro drzwi
Każda z 14 ścieżek tworzenia stemplowała flagi po swojemu. Jedna wpisywała status recenzji, którego panel w ogóle nie zna — takie lokacje wisiały w limbo: nie w poczekalni, nie przyjęte. Kiedyś inna ścieżka wpisywała `pending` zamiast `pending_review` i **31 lokacji liczyło się do licznika, ale nie było ich na liście**.

✅ **Naprawione w fali 3** (#1526): jest **jedna funkcja** `create_location()` (`backend/app/services/location_factory.py`) i to jedyne miejsce, które wstawia lokację. Gwarantuje cztery rzeczy naraz: komplet flag wg źródła (sześć legalnych źródeł), `parent_id` **i** `parent_key` zawsze razem, wiązanie z mapą wyłącznie przez kanonicznego writera heksa, oraz idempotencję po kluczu (powtórka nie robi kopii `_2`). Nowe, bezpośrednie wpisanie lokacji z pominięciem tych drzwi **wywala test** — więc choroba nie może wrócić tylnymi drzwiami.

### Choroba 3 — samonaprawa zamiast zdrowia
Prostowanie świata przy starcie (Część 6) leczyło objawy co rano zamiast usunąć przyczynę. Leczenie bywało agresywne (kasuje pinezki), więc trzeba było dokładać kolejne łatki, żeby przed nim ochronić poprawne dane.

✅ **Naprawione w fali 4** (#1527): samonaprawa nie zniknęła — **przestała być cicha**. Wszystko, co prostuje się przy starcie, ląduje w kronice napraw, a rozjazdy, których nikt nie posprzątał, wiszą na liście w panelu (Część 6A) razem z wyjaśnieniem po polsku. Do tego doszła warstwa, której wcześniej nie było w ogóle: **kontrola jakości treści** — to ona wyłapuje karczmę bez karczmarza, czyli dokładnie ten typ problemu, który przeleżał miesiące niezauważony (#1524).

Uczciwa uwaga: to nie usuwa przyczyn, tylko przestaje je ukrywać. Przyczyny kasują fale 1–3 (jedno źródło prawdy, jedne drzwi); fala 4 jest **lampką kontrolną**, nie silnikiem.

### Choroba 4 — dokumentacja opisuje nieistniejący system
Dokument `05_WORLD_BUILDER_AND_PERSISTENCE.md` opisuje model sprzed #1243: pozycjonowanie po martwych dziś kolumnach `map_x/map_y` i tabelę terenu, której nigdy nie zbudowano. Jedyny prawdziwy opis relacji heks↔lokacja siedział **w komentarzu w kodzie**. Ten plik, który właśnie czytasz, to naprawa tej choroby.

### Choroba 5 — siedem przełączników
Większość ich kombinacji nie ma sensu. Status recenzji miał 5 realnych wartości, panel akceptuje 3.

✅ **Częściowo naprawione w fali 2** (#1525): przełączników jest pięć zamiast siedmiu, a status recenzji ma dokładnie 3 legalne wartości — pilnowane przez samą bazę, nie przez dobrą wolę czternastu ścieżek zapisu.

### Dlaczego to wygląda na „ciągłe problemy"
~60 zgłoszeń o lokacjach w historii projektu. Ale wzorzec jest wyraźny: **bugi nie dotyczą rdzenia** (heksy, podróż, mapa lokalna, model osady działają) — dotyczą **szwów między duplikatami prawdy**. To argument za sprzątaniem, nie za trzecim przepisaniem.

---

## Część 8 — Plan sprzątania (fale)

Nie przepisujemy systemu. Trzeci redesign dołożyłby czwartą warstwę do trzech istniejących.

| Fala | Co robimy | Efekt dla ciebie |
|---|---|---|
| **0** ✅ (#1528) | czysty kanon wiązań heks↔lokacja + bezpiecznik seeda | geografia przestaje ginąć przy reseedzie |
| **1** ✅ (#1524) | jeden system NPC: tabela przypisań = prawda, lista na karcie = automatyczna kopia, stara tabela skasowana | gospodarze przestają znikać i dublować się |
| **2** ✅ (#1525) | jedna prawda na informację: skasowane `placement` i `ai_generated`, 3 legalne statusy pilnowane przez bazę | zniknęły rozjazdy 60/56/54 |
| **3** ✅ (#1526) | jedne drzwi: wszystkie 14 ścieżek przez jedną funkcję stemplującą flagi tak samo | koniec lokacji w limbo |
| **4** ✅ (#1527) | lampka w panelu admina zamiast cichej samonaprawy: lista rozjazdów + guzik „napraw" + kronika napraw | widzisz problemy, zamiast systemu, który je zamiata |
| **5** ✅ | ten dokument | wiesz, jak działa twoja gra |

**Wszystkie fale zamknięte.** Co zostało jako praca **treściowa**, nie systemowa: dosiać gospodarzy do 20 usługowych lokacji, które lint pokazuje jako puste, i rozstrzygnąć 8 par podobnych nazw. Lista czeka w panelu — to już nie jest szukanie po bazie, tylko odhaczanie.

**Czego nie ruszamy, bo działa:** heks = prawda · jeden zapisywacz pozycji · jedna ścieżka podróży · model osady hub+suby · pula floating jako magazyn treści.

---

## Część 9 — Ściągawka

### Gdzie klikać w panelu
| Chcę | Gdzie |
|---|---|
| zobaczyć/edytować lokacje | `/admin/` → Świat → Lokacje |
| zatwierdzić twory AI | `/admin/` → Świat → Oczekujące |
| zobaczyć mapę świata | `/admin/` → Mapa |
| ustawić lokację na heksie | Mapa → klik w heks |
| sprawdzić zdrowie świata | `/admin/` → Mapa → **🩺 Kontrola świata** |
| zobaczyć, co system naprawił sam | Mapa → 🩺 Kontrola świata → **🕮 Historia napraw** |

### Gdzie leży prawda
| Pytanie | Odpowiedź |
|---|---|
| gdzie leży lokacja? | mapa heksów (`world_hexes.location_key`), NIE karta lokacji |
| co jest kanonem świata? | `data/seeds/content/game_locations.json` w gicie |
| kto jest w lokacji? | tabela przypisań NPC (po fali 1 — jedyna) |
| jak działa relacja heks↔lokacja? | ten dokument + `backend/app/services/hex_location_link.py` |
| co jest dziś zepsute w świecie? | Mapa → 🩺 Kontrola świata (reguły: `backend/app/services/world_lint_service.py`) |
| kto zmienił mi pinezkę w nocy? | kronika napraw — „⚙️ start backendu" = automat, „👤 panel" = człowiek |

### Zasady bezpieczeństwa danych
- **Git jest prawdą, baza jest brudnopisem.** Twoje zmiany w panelu przetrwają tylko po zrzuceniu do gita (`snapshot_world_map.py` / `snapshot_content.py`) i **zacommitowaniu**.
- ⚠️ **Snapshot zrzuca bazę taką, jaka jest — razem ze śmieciami.** Tak właśnie do kanonu Kresów trafiły obozowiska, rekord testowy i 9 lokacji roboczych Kuźni (naprawione w fali 0). Przed snapshotem sprawdź `/admin/` → Mapa, czy nie zrzucasz brudu.
- **Kanon mapy to `data/regions/region_<kraina>.json`** (pliki krain, status `live`). `docs/world/world_map_seed.json` to tylko legacy fallback — ma 0 wiązań, więc od fali 0 seed odmawia wsiania go na niepustą mapę.
- Mapa świata (`world_hexes`, poziom 0) jest **twoja** — nie ruszamy jej przy niepowiązanych zadaniach.
- Reseed treści z gita jest celowo wąski: **nie kasuje** lokacji stworzonych przez kampanie ani czekających w poczekalni.

---

*Dokument żywy. Każda fala sprzątania aktualizuje odpowiednią część.*
