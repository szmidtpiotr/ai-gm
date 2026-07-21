# Jak działa świat AI-GM

> **Dla kogo:** dla Piotra i dla każdego, kto ma podjąć decyzję projektową o świecie gry — bez czytania kodu.
> **Stan na:** 2026-07-21. Liczby zmierzone na żywej bazie DEV.
> **Status:** to jest ŹRÓDŁO PRAWDY o działaniu świata. Zastępuje `docs/V2_ARCHITECTURE/05_WORLD_BUILDER_AND_PERSISTENCE.md`, który opisuje model sprzed przebudowy #1243 i wprowadza w błąd.

---

## Część 0 — Streszczenie na jedną stronę

Świat AI-GM stoi na czterech filarach:

1. **Katalog lokacji** — spis wszystkich miejsc, jakie w grze istnieją. Jak książka telefoniczna: każde miejsce ma swoją kartę. Karta sama w sobie nie mówi, *gdzie* to miejsce leży.
2. **Mapa świata** — siatka heksów (sześciokątnych pól). To ona decyduje o geografii. Heks może wskazać jedną lokację i powiedzieć „tu stoi Vilnograd".
3. **Mapy lokalne** — mini-siatki *wewnątrz* osady. Karczma, kuźnia i rynek jednego miasteczka leżą na własnej małej mapce, a nie na mapie świata.
4. **Poczekalnia** — gdy narrator AI wymyśli w trakcie gry nowe miejsce, trafia ono do kolejki „Do zatwierdzenia" w panelu admina. Gra go używa, ale świat go jeszcze nie kanonizował.

Kluczowa zasada, która rządzi wszystkim (decyzja z 2026-07-05, #1243):

> **Heks jest prawdą.** Jeśli chcesz wiedzieć, gdzie leży dana lokacja — pytasz mapy, nie karty lokacji. Karta ma zapisane współrzędne, ale to tylko kopia dla wygody i może być nieaktualna.

Dlaczego tak: przy audycie okazało się, że współrzędne zapisane na kartach lokacji były zepsute (14 lokacji stało na (0,0), Brzeżyno miało wpisane (1,0), a fizycznie leżało na (39,9)). Mapa była czysta. Do tego na jednym heksie z definicji stoi jedna lokacja, więc konflikt „dwa miejsca w jednym punkcie" jest niemożliwy. Wygrała mapa.

---

## Część 1 — Z czego zbudowany jest świat

### 1.1 Lokacja (karta w katalogu)

**485 kart** w bazie DEV. Każda ma:

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

Tylko **54 heksy** faktycznie wskazują jakąś lokację. Reszta to dzicz: teren, przez który się podróżuje, ale nie ma tam nazwanego miejsca.

### 1.3 Mapa lokalna (heksy wewnątrz osady)

**29 heksów** poziomu 1. Powstają dopiero, gdy osada ma **co najmniej 2 sub-lokacje** — wcześniej mini-mapa nie ma sensu. Sub-lokacje układają się w pierścień wokół centrum osady.

Sub-lokacja **nie ma własnego miejsca na mapie świata** — jej „adres" to heks jej osady-rodzica.

### 1.4 Floating vs placed — najważniejsze pojęcie do zrozumienia

- **placed (osadzona)** = lokacja stoi na konkretnym heksie mapy świata. Można do niej dojść, widać ją na mapie.
- **floating (unosząca się)** = lokacja istnieje w katalogu, ale **nie ma jeszcze przypisanego miejsca w świecie**.

**425 z 485 lokacji jest floating.** To brzmi alarmująco, ale w większości jest poprawne, bo floating oznacza dwie zupełnie różne rzeczy:

1. **Sub-lokacje** — z definicji nie stoją na mapie świata (Wielka Izba nie jest osobnym punktem na mapie Kresów, tylko wnętrzem karczmy). To ~większość floatingu i to jest w porządku.
2. **Zapas makro-lokacji** — gotowe miejsca czekające na osadzenie. Silnik może je automatycznie postawić na pasującym pustym heksie o odpowiednim terenie. To celowy magazyn treści, nie śmieci.

Floating lokacja **nadal jest grywalna narracyjnie** — narrator może o niej opowiedzieć, gracz może w niej być. Traci tylko pinezkę na mapie świata.

---

## Część 2 — Skąd biorą się lokacje (14 wejść)

Lokacje wchodzą do świata **czternastoma różnymi drzwiami**. To jedna z głównych chorób systemu (Część 7), ale trzeba je znać. W grupach:

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

**Rozkład na żywej bazie DEV:**

| Kto stworzył | Ile | Uwaga |
|---|---|---|
| `admin_manual` | 241 | 211 niekanonicznych + 30 kanonicznych |
| `seed` (git, kanon) | 169 | ← prawdziwy kanon świata |
| `forge` | 25 | wszystkie w poczekalni |
| `gm_runtime` | 30 | 21 odrzuconych, 9 przyjętych |
| `auto_generated` | 19 | stuby wiosek |

---

## Część 3 — Życie lokacji: statusy i poczekalnia

Karta lokacji ma **siedem niezależnych przełączników**. To za dużo (Część 7), ale tak jest dziś:

| Przełącznik | Co znaczy | Kto go używa |
|---|---|---|
| **aktywna** | czy w ogóle istnieje; wyłączenie = miękkie skasowanie | wszystko |
| **zatwierdzona** | czy widoczna dla silnika świata | filtr treści |
| **kanoniczna** | czy to trwały element świata (a nie twór jednej kampanii) | mapa, seedy |
| **status recenzji** | `permanent` (przyjęta) · `pending_review` (poczekalnia) · `discarded` (odrzucona) | panel Świat → Oczekujące |
| **tymczasowa** | obozowisko — znika po odejściu | podróż |
| **placement** | `floating` / `placed` | silnik osadzania |
| **ai_generated** | stara flaga „stworzone przez AI" | resztki, patrz Część 7 |

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

---

## Część 7 — Znane choroby (i dlaczego temat wraca co tydzień)

Rdzeń projektu jest zdrowy. Problemy siedzą w **warstwach historycznych, których nie skasowaliśmy** po kolejnych przebudowach. Każda przebudowa dokładała nową prawdę, a stara zostawała — i nadal jest czytana przez kod.

### Choroba 1 — ta sama informacja w 2–3 miejscach

| Informacja | Ile kopii | Gdzie |
|---|---|---|
| kto jest NPC w lokacji | **3** | stara tabela `npc_locations` (wciąż czytana przez sklep, rzemiosło i silnik!) · nowa tabela przypisań · lista wpisana wprost na karcie lokacji |
| czy lokacja stoi na mapie | **3** | przełącznik `placement` · współrzędne na karcie · wskazanie z heksa |
| kto jest rodzicem | **2** | numer rodzica i nazwa rodzica — kod sprawdza oba, bo numer bywa pusty |
| czy stworzyło AI | **2** | stara flaga `ai_generated` i nowe pole „kto stworzył" |

**Dowód, że to nie teoria** — trzy pytania o to samo dawały trzy różne odpowiedzi:

```
                                    PRZED (2026-07-21)    PO fali 0
lokacji z przełącznikiem "placed"          60                39
lokacji z wpisanymi współrzędnymi          56                39
heksów świata wskazujących lokację         54                39
```

Rozbieżność miała konkretne twarze: 11 lokacji twierdziło, że stoi na mapie, choć żaden heks ich nie znał (w tym sub-lokacje Trzech Kruków, Wołanki i Wołchynii, które **z definicji** nie powinny być „placed"), a 3 heksy świata wskazywały skasowane obozowiska i rekord testowy.

✅ **Naprawione w fali 0** (#1528, commit `cc27fd22`). Od tej pory reconcile przy starcie backendu nie ma czego prostować (`cleared: 0, promoted: 0`).

Bug z gospodą „Pod Złamanym Rogiem" (#1524) to dokładnie ten sam mechanizm w wariancie NPC.

### Choroba 2 — czternaścioro drzwi
Każda z 14 ścieżek tworzenia stempluje flagi po swojemu. Jedna wpisuje status recenzji, którego panel w ogóle nie zna — takie lokacje wiszą w limbo: nie w poczekalni, nie przyjęte. Kiedyś inna ścieżka wpisywała `pending` zamiast `pending_review` i **31 lokacji liczyło się do licznika, ale nie było ich na liście**.

### Choroba 3 — samonaprawa zamiast zdrowia
Prostowanie świata przy starcie (Część 6) leczy objawy co rano zamiast usunąć przyczynę. Leczenie bywa agresywne (kasuje pinezki), więc trzeba było dokładać kolejne łatki, żeby przed nim ochronić poprawne dane.

### Choroba 4 — dokumentacja opisuje nieistniejący system
Dokument `05_WORLD_BUILDER_AND_PERSISTENCE.md` opisuje model sprzed #1243: pozycjonowanie po martwych dziś kolumnach `map_x/map_y` i tabelę terenu, której nigdy nie zbudowano. Jedyny prawdziwy opis relacji heks↔lokacja siedział **w komentarzu w kodzie**. Ten plik, który właśnie czytasz, to naprawa tej choroby.

### Choroba 5 — siedem przełączników
Większość ich kombinacji nie ma sensu. Status recenzji ma 5 realnych wartości, panel akceptuje 3.

### Dlaczego to wygląda na „ciągłe problemy"
~60 zgłoszeń o lokacjach w historii projektu. Ale wzorzec jest wyraźny: **bugi nie dotyczą rdzenia** (heksy, podróż, mapa lokalna, model osady działają) — dotyczą **szwów między duplikatami prawdy**. To argument za sprzątaniem, nie za trzecim przepisaniem.

---

## Część 8 — Plan sprzątania (fale)

Nie przepisujemy systemu. Trzeci redesign dołożyłby czwartą warstwę do trzech istniejących.

| Fala | Co robimy | Efekt dla ciebie |
|---|---|---|
| **0** ✅ (#1528) | czysty kanon wiązań heks↔lokacja + bezpiecznik seeda | geografia przestaje ginąć przy reseedzie |
| **1** (#1524) | jeden system NPC: tabela przypisań = prawda, lista na karcie = automatyczna kopia, stara tabela skasowana | gospodarze przestają znikać i dublować się |
| **2** | jedna prawda na informację: kasujemy `placement`, `ai_generated`, jeden rodzic, 3 legalne statusy | znikają rozjazdy 60/56/54 |
| **3** | jedne drzwi: wszystkie 14 ścieżek przez jedną funkcję stemplującą flagi tak samo | koniec lokacji w limbo |
| **4** | lampka w panelu admina zamiast cichej samonaprawy: lista rozjazdów + guzik „napraw" | widzisz problemy, zamiast systemu, który je zamiata |
| **5** | ten dokument | wiesz, jak działa twoja gra ✅ |

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

### Gdzie leży prawda
| Pytanie | Odpowiedź |
|---|---|
| gdzie leży lokacja? | mapa heksów (`world_hexes.location_key`), NIE karta lokacji |
| co jest kanonem świata? | `data/seeds/content/game_locations.json` w gicie |
| kto jest w lokacji? | tabela przypisań NPC (po fali 1 — jedyna) |
| jak działa relacja heks↔lokacja? | ten dokument + `backend/app/services/hex_location_link.py` |

### Zasady bezpieczeństwa danych
- **Git jest prawdą, baza jest brudnopisem.** Twoje zmiany w panelu przetrwają tylko po zrzuceniu do gita (`snapshot_world_map.py` / `snapshot_content.py`) i **zacommitowaniu**.
- ⚠️ **Snapshot zrzuca bazę taką, jaka jest — razem ze śmieciami.** Tak właśnie do kanonu Kresów trafiły obozowiska, rekord testowy i 9 lokacji roboczych Kuźni (naprawione w fali 0). Przed snapshotem sprawdź `/admin/` → Mapa, czy nie zrzucasz brudu.
- **Kanon mapy to `data/regions/region_<kraina>.json`** (pliki krain, status `live`). `docs/world/world_map_seed.json` to tylko legacy fallback — ma 0 wiązań, więc od fali 0 seed odmawia wsiania go na niepustą mapę.
- Mapa świata (`world_hexes`, poziom 0) jest **twoja** — nie ruszamy jej przy niepowiązanych zadaniach.
- Reseed treści z gita jest celowo wąski: **nie kasuje** lokacji stworzonych przez kampanie ani czekających w poczekalni.

---

*Dokument żywy. Każda fala sprzątania aktualizuje odpowiednią część.*
