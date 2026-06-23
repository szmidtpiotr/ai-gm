# Poprawki tekstów — podstrony AI-GM (v2)
# Plik uzupełniający do showcase_copy_fixes.md
# Pokrywa: /rules/, /showcase/swiat.html, /showcase/changelog.html

> **Format identyczny z poprzednim plikiem.**
> Agent szuka ORYGINAŁ w plikach HTML strony i zastępuje ZAMIEŃ NA.
> Jeśli fragment kończy się „…", wyszukaj unikalny kawałek bez „…".

---

## ══════════════════════════════════════
## PODSTRONA: /rules/ — Księga Zasad
## ══════════════════════════════════════

## POPRAWKA R01
**SEKCJA:** Wstęp / wprowadzenie narracyjne — tytuł rozdziału

**ORYGINAŁ:**
```
✦ Wstęp · Opowieść
```

**ZAMIEŃ NA:**
```
✦ Wstęp — Jak to działa
```

**POWÓD:** „Opowieść" jako tytuł rozdziału z zasadami jest mylące — sugeruje lore, a to jest mechaniczny wstęp do testów. Gracz szukający „jak rzucam kością" nie kliknie w „Opowieść".

---

## POPRAWKA R02
**SEKCJA:** Rozdział I — Test umiejętności / nagłówek podsekcji

**ORYGINAŁ:**
```
Kość w ferworze walki
```

**ZAMIEŃ NA:**
```
Rzuty podczas walki
```

**POWÓD:** „W ferworze walki" to poetycki zwrot, który nie pasuje do tytułu technicznego podrozdziału w księdze zasad. Czytelnik szuka konkretnej informacji.

---

## POPRAWKA R03
**SEKCJA:** Rozdział I — Test umiejętności / tabela trudności

**ORYGINAŁ:**
```
PT 8=Łatwe, 12=Średnie, 16=Trudne, 20=Ekstremalne, 24+=Legendarne
```

**ZAMIEŃ NA:**
```
Próg 8 = Łatwe, Próg 12 = Średnie, Próg 16 = Trudne, Próg 20 = Ekstremalne, Próg 24+ = Legendarne
```

**POWÓD:** Skrót „PT" nie jest nigdzie wcześniej wyjaśniony dla nowego gracza. Warto rozwinąć lub poprzedzić zdaniem: „Próg Trudności (PT) to liczba, którą musisz osiągnąć lub przekroczyć rzutem."

---

## POPRAWKA R04
**SEKCJA:** Rozdział II — Siedem cech / podsekcja

**ORYGINAŁ:**
```
Czym rządzi każda cecha
```

**ZAMIEŃ NA:**
```
Do czego służy każda cecha
```

**POWÓD:** „Czym rządzi" brzmi archaicznie i niejasno. „Do czego służy" jest bezpośrednie i zrozumiałe.

---

## POPRAWKA R05
**SEKCJA:** Rozdział II — Siedem cech / punkty życia i mana (nagłówek)

**ORYGINAŁ:**
```
Punkty życia i mana
```

**ZAMIEŃ NA:**
```
Punkty życia i punkty many
```

**POWÓD:** „Mana" samo w sobie jest OK jako termin, ale w nagłówku spójniej jest „punkty many" skoro obok jest „punkty życia" — zachowuje równoległą strukturę.

---

## POPRAWKA R06
**SEKCJA:** Rozdział II — Siedem cech / tabela HP archetypów

**ORYGINAŁ:**
```
HP Archetypów (poziom 3, CON mod +2): Wojownik 16HP, Łotrzyk 14HP, Uczony 12HP
```

**ZAMIEŃ NA:**
```
Punkty życia (poziom 3, Kondycja +2): Wojownik 16 PŻ, Łotrzyk 14 PŻ, Uczony 12 PŻ
```

**POWÓD:** „HP", „CON mod" — skróty angielskie, nieczytelne dla kogoś bez tła w grach RPG po angielsku. Polska wersja jest spójna z resztą gry.

---

## POPRAWKA R07
**SEKCJA:** Rozdział III — Umiejętności / przykładowa tabela rangi

**ORYGINAŁ:**
```
Ranga skradania (ZRĘ +3): brak=+3, ranga1=+4, ranga2=+5, ranga3=+8 (+2 biegłości)
```

**ZAMIEŃ NA:**
```
Skradanie (Zręczność +3): bez rangi = +3, ranga 1 = +4, ranga 2 = +5, ranga 3 = +8 (bonus biegłości ×2)
```

**POWÓD:** „ZRĘ" to skrót wewnętrzny, „+2 biegłości" jest niejasne — dla nowego gracza nie wiadomo, co to znaczy. „Bonus biegłości ×2" lub „podwójny bonus biegłości" jest zrozumiałe.

---

## POPRAWKA R08
**SEKCJA:** Rozdział IV — Walka / podsekcja trafienie

**ORYGINAŁ:**
```
Trafienie i unik
```

**ZAMIEŃ NA:**
```
Jak trafić i jak się bronić
```

**POWÓD:** Nagłówki w formie pytań lub krótkich opisów czynności są bardziej intuicyjne dla gracza, który szuka konkretnej odpowiedzi.

---

## POPRAWKA R09
**SEKCJA:** Rozdział IV — Walka / podsekcja pancerz

**ORYGINAŁ:**
```
Pancerz i obrażenia
```

**ZAMIEŃ NA:**
```
Pancerz i jak zmniejsza obrażenia
```

**POWÓD:** Samo „Pancerz i obrażenia" nie mówi o relacji między nimi. Nowy gracz nie wie, czy pancerz blokuje trafienia czy redukuje obrażenia — tytuł powinien to sugerować.

---

## POPRAWKA R10
**SEKCJA:** Rozdział V — Rany / tabela drabiny ran

**ORYGINAŁ:**
```
>75% Zdrowy(0), 75-50% Ranny(−1), 50-25% Ciężko ranny(−2), 25-10% Poważnie ranny(−4), <10% Na skraju śmierci(−4)
```

**ZAMIEŃ NA:**
```
Powyżej 75% PŻ — Zdrowy (bez kary)
75–50% PŻ — Ranny (−1 do rzutów)
50–25% PŻ — Ciężko ranny (−2 do rzutów)
25–10% PŻ — Poważnie ranny (−4 do rzutów)
Poniżej 10% PŻ — Na skraju śmierci (−4 do rzutów)
```

**POWÓD:** Tabela jako jeden ciąg tekstu jest nieczytelna. Każdy stopień powinien być osobną linią z jasnym opisem — co to znaczy dla gracza (kara do rzutów).

---

## POPRAWKA R11
**SEKCJA:** Rozdział V — Rany / tabela rzutów na śmierć

**ORYGINAŁ:**
```
Rzuty na śmierć: 1szy próg 10, 2gi=13, 3ci=16, 4ty+=19
```

**ZAMIEŃ NA:**
```
Rzuty na śmierć — potrzebujesz osiągnąć:
1. rzut — Próg 10
2. rzut — Próg 13
3. rzut — Próg 16
4. rzut i dalej — Próg 19
```

**POWÓD:** „1szy", „2gi", „4ty+" to nieformalne skróty, które wyglądają jak notatki robocze, nie jak podręcznik. Czytelna lista lepsza niż skompresowany ciąg.

---

## POPRAWKA R12
**SEKCJA:** Rozdział VI — Stany i kondycje / nagłówek grupy

**ORYGINAŁ:**
```
Rany w czasie (Podpalenie, Krwotok, Trucizna)
```

**ZAMIEŃ NA:**
```
Obrażenia w czasie — Podpalenie, Krwotok, Trucizna
```

**POWÓD:** „Rany w czasie" brzmi jak dosłowne tłumaczenie angielskiego „damage over time" (DoT). „Obrażenia w czasie" jest bardziej naturalne po polsku.

---

## POPRAWKA R13
**SEKCJA:** Rozdział VI — Stany / nagłówek grupy

**ORYGINAŁ:**
```
Utrata kontroli (Ogłuszenie, Panika, Berserk, Zamęt, Sen, Zauroczenie, Przerażenie, Spowolnienie/Zamrożenie, Klątwa, Wyczerpanie)
```

**ZAMIEŃ NA:**
```
Stany negatywne — Ogłuszenie, Panika, Szał, Zamęt, Sen, Zauroczenie, Przerażenie, Spowolnienie, Zamrożenie, Klątwa, Wyczerpanie
```

**POWÓD:** „Utrata kontroli" nie opisuje dobrze całej grupy — Klątwa czy Wyczerpanie to nie utrata kontroli. „Stany negatywne" jest neutralne i precyzyjne. „Berserk" zamieniony na „Szał" (polskie słowo).

---

## POPRAWKA R14
**SEKCJA:** Rozdział VI — Stany / nagłówek grupy wzmocnień

**ORYGINAŁ:**
```
Wzmocnienia (Furia, Przyśpieszenie, Błogosławieństwo, Natchnienie, Ukrycie)
```

**ZAMIEŃ NA:**
```
Stany pozytywne — Furia, Przyśpieszenie, Błogosławieństwo, Natchnienie, Ukrycie
```

**POWÓD:** Spójność z poprzednim nagłówkiem. „Wzmocnienia" jest OK, ale „Stany pozytywne" tworzy symetrię z „Stany negatywne".

---

## POPRAWKA R15
**SEKCJA:** Rozdział VII — Magia / tabela Miscast

**ORYGINAŁ:**
```
Miscast: poziom 1-2 → oszołomienie, 3-4 → 1k4 obrażeń, 5-7 → 1k6+ogłuszenie, 8+ → 1k8+ogłuszenie+dziki efekt
```

**ZAMIEŃ NA:**
```
Nieudany rzut czaru (poziom zaklęcia):
Poziom 1–2 → oszołomienie
Poziom 3–4 → 1k4 obrażeń własnych
Poziom 5–7 → 1k6 obrażeń + ogłuszenie
Poziom 8+ → 1k8 obrażeń + ogłuszenie + nieprzewidywalny efekt magiczny
```

**POWÓD:** „Miscast" to angielski termin branżowy. „Nieudany rzut czaru" jest czytelniejszy. Tabela jako ciąg jest nieczytelna — potrzebuje formatowania. „Dziki efekt" zamieniony na „nieprzewidywalny efekt magiczny" — pełniejszy opis.

---

## POPRAWKA R16
**SEKCJA:** Rozdział VII — Magia / nagłówek podsekcji

**ORYGINAŁ:**
```
Miscast i krytyk
```

**ZAMIEŃ NA:**
```
Nieudane zaklęcie i krytyczne trafienie czarem
```

**POWÓD:** „Miscast" — jak wyżej. „Krytyk" to żargon skrócony — „krytyczne trafienie" jest zrozumiałe dla każdego.

---

## POPRAWKA R17
**SEKCJA:** Rozdział VII — Magia / nagłówek

**ORYGINAŁ:**
```
Nauka i rangi
```

**ZAMIEŃ NA:**
```
Uczenie się zaklęć i poziomy czarów
```

**POWÓD:** „Rangi" to wewnętrzna terminologia systemu. „Poziomy czarów" jest bardziej intuicyjne — gracz rozumie, że zaklęcia mają poziomy trudności/mocy.

---

## POPRAWKA R18
**SEKCJA:** Rozdział VIII — Złoto / tabela trwałości

**ORYGINAŁ:**
```
Trwałość: T1(100trw/20GP naprawy), T2(150trw/50GP), T3(200trw/100GP)
```

**ZAMIEŃ NA:**
```
Trwałość przedmiotów:
Tier 1 — 100 punktów trwałości, naprawa 20 złota
Tier 2 — 150 punktów trwałości, naprawa 50 złota
Tier 3 — 200 punktów trwałości, naprawa 100 złota
```

**POWÓD:** „T1", „trw", „GP" — skróty robocze, nieczytelne. „GP" to anglojęzyczne „Gold Pieces". Tabela powinna być czytelna bez słowniczka.

---

## POPRAWKA R19
**SEKCJA:** Rozdział VIII — Złoto / tabela rzemiosła

**ORYGINAŁ:**
```
Rzemiosło: Nałożenie właściwości 150/500/1200GP (T1/T2/T3); Tier upgrade T1→T2=350GP, T2→T3=700GP
```

**ZAMIEŃ NA:**
```
Rzemiosło:
Dodanie specjalnej właściwości do przedmiotu: 150 / 500 / 1200 złota (Tier 1 / Tier 2 / Tier 3)
Ulepszenie przedmiotu: Tier 1 → Tier 2 za 350 złota, Tier 2 → Tier 3 za 700 złota
```

**POWÓD:** „GP", skróty „T1/T2/T3", strzałki — format notatki deweloperskiej. Gracz czyta Księgę Zasad żeby zrozumieć, ile coś kosztuje.

---

## POPRAWKA R20
**SEKCJA:** Rozdział VIII — Złoto / tabela cen usług

**ORYGINAŁ:**
```
Posiłek 2GP, Napój 1GP, Nocleg 5GP, Luksus 20GP, Uzdrowiciel lekki 10GP, ciężki 50GP, Kowal naprawa 15GP, Posłaniec 8/12GP
```

**ZAMIEŃ NA:**
```
Posiłek — 2 złote
Napój — 1 złoty
Nocleg — 5 złotych
Nocleg w luksusie — 20 złotych
Uzdrowiciel (lekkie rany) — 10 złotych
Uzdrowiciel (ciężkie rany) — 50 złotych
Kowal (naprawa) — 15 złotych
Posłaniec (w mieście / poza miastem) — 8 / 12 złotych
```

**POWÓD:** „GP" (angielskie Gold Pieces) nie pasuje do polskiej gry. Ciąg zamiast listy jest nieczytelny. „Posłaniec 8/12GP" — niejasne, co oznacza ukośnik.

---

## POPRAWKA R21
**SEKCJA:** Rozdział VIII — Złoto / tabela wyników targowania

**ORYGINAŁ:**
```
Wynik targu: Sukces krytyczny −40%, Sukces −15%, Porażka 0%, Porażka krytyczna +10%+obrażony kupiec
```

**ZAMIEŃ NA:**
```
Wynik targowania:
Sukces krytyczny — cena niższa o 40%
Sukces — cena niższa o 15%
Porażka — cena bez zmian
Porażka krytyczna — cena wyższa o 10%, kupiec odmawia dalszych rozmów
```

**POWÓD:** Format ciągu z procentami i plusami/minusami wygląda jak dane z arkusza, nie jak zasady gry. „Obrażony kupiec" brzmi jak skrót notatki — warto opisać skutek.

---

## POPRAWKA R22
**SEKCJA:** Rozdział IX — Odpoczynek / nagłówek

**ORYGINAŁ:**
```
Krótki i długi odpoczynek
```

**ZAMIEŃ NA:**
```
Odpoczynek — krótki i długi
```

**POWÓD:** Drobna korekta — nagłówki w Księdze powinny zaczynać się od tematu, nie od przymiotnika. Ułatwia skanowanie listy.

---

## POPRAWKA R23
**SEKCJA:** Rozdział IX — Rozwój / tabela doświadczenia

**ORYGINAŁ:**
```
Doświadczenie: Słaby wróg 3PD, Zwykły 8PD, Elitarny 30PD, Boss 70PD, Beat 30PD, Quest poboczny 40PD, Loch 75PD, Kampania 200PD
```

**ZAMIEŃ NA:**
```
Nagrody doświadczenia:
Słaby wróg — 3 PD
Zwykły wróg — 8 PD
Elitarny wróg — 30 PD
Bossowy wróg — 70 PD
Pokonanie trudnego wyzwania — 30 PD
Ukończenie zadania pobocznego — 40 PD
Ukończenie lochu — 75 PD
Ukończenie kampanii — 200 PD
```

**POWÓD:** „Beat 30PD" — angielskie słowo bez kontekstu, wygląda jak błąd copy-paste z tabeli deweloperskiej. Reszta to skróty i ciąg zamiast listy.

---

## POPRAWKA R24
**SEKCJA:** Rozdział IX — Rozwój / tabela progów poziomów

**ORYGINAŁ:**
```
Progi poziomów: 2→100PD, 3→250, 4→450, 5→700, 6→1000, 7→1350, 8→1750, 9→2200, 10→2700
```

**ZAMIEŃ NA:**
```
Progi awansów:
Poziom 2 — 100 PD
Poziom 3 — 250 PD
Poziom 4 — 450 PD
Poziom 5 — 700 PD
Poziom 6 — 1000 PD
Poziom 7 — 1350 PD
Poziom 8 — 1750 PD
Poziom 9 — 2200 PD
Poziom 10 — 2700 PD
```

**POWÓD:** Ciąg strzałek wygląda jak dane z backendu. Tabela lub lista z wyraźnymi poziomami jest czytelna na pierwszy rzut oka.

---

## ══════════════════════════════════════
## PODSTRONA: /showcase/changelog.html — Co nowego
## ══════════════════════════════════════

## POPRAWKA C01
**SEKCJA:** Changelog — nagłówek wpisu

**ORYGINAŁ:**
```
Multiplayer FAZA 5 dokończona + czary maga – (siatka 26→34) + interaktywna Księga Zasad + pathfinding lochów
```

**ZAMIEŃ NA:**
```
Multiplayer ukończony + czary maga (rozszerzono o 8 zaklęć) + interaktywna Księga Zasad + nawigacja w lochach
```

**POWÓD:** „FAZA 5" to wewnętrzna etykieta dewelopera. „Siatka 26→34" to kompletnie niezrozumiały zapis dla gracza — chodzi o liczbę zaklęć. „Pathfinding" to angielski termin techniczny.

---

## POPRAWKA C02
**SEKCJA:** Changelog — szczegóły wpisu (pierwsze ◆)

**ORYGINAŁ:**
```
◆ character_campaign_state — izolacja HP/mana per-kampania (bohater w wielu MP naraz)
```

**ZAMIEŃ NA:**
```
◆ Bohater może uczestniczyć w kilku sesjach multiplayer jednocześnie — każda ma własne HP i manę
```

**POWÓD:** `character_campaign_state` to nazwa techniczna z kodu. „Izolacja HP/mana per-kampania" to żargon deweloperski. „MP" to skrót niezrozumiały dla gracza.

---

## POPRAWKA C03
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ sekwencyjny silnik walki dla multiplayer
```

**ZAMIEŃ NA:**
```
◆ Walka w trybie wieloosobowym odbywa się w turach — każdy gracz ma swoją kolejkę
```

**POWÓD:** „Sekwencyjny silnik walki" to opis architektury, nie funkcji dla gracza.

---

## POPRAWKA C04
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ rzuty dwustopniowe w rundzie MP (planer → kod → narrator)
```

**ZAMIEŃ NA:**
```
◆ Każda akcja w multiplayer przechodzi przez dwa etapy: najpierw mechanika oblicza wynik, potem AI opisuje co się stało
```

**POWÓD:** „Planer → kod → narrator" to opis wewnętrznego pipeline'u. „Dwustopniowe" to termin architektury. Gracz widzi efekt, nie implementację.

---

## POPRAWKA C05
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ timer walki 2 min + push „Twoja kolej"
```

**ZAMIEŃ NA:**
```
◆ Licznik czasu w walce: masz 2 minuty na swoją turę. Powiadomienie przypomni, kiedy czas twojego ruchu
```

**POWÓD:** „Push" to termin techniczny (push notification). Brak kontekstu co do tego, skąd przychodzi powiadomienie.

---

## POPRAWKA C06
**SEKCJA:** Changelog — nagłówek wpisu

**ORYGINAŁ:**
```
Multiplayer FAZA 5 + zaproszenia przez link + dopięcie walki (dual-wield/grapple/akcje) + fixy lochów
```

**ZAMIEŃ NA:**
```
Multiplayer — zaproszenia przez link, walka oburęczna i chwytanie przeciwnika, poprawki lochów
```

**POWÓD:** „FAZA 5" — wewnętrzna etykieta. „Dual-wield/grapple" — angielskie terminy. „Dopięcie" i „fixy" to żargon deweloperski.

---

## POPRAWKA C07
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ wymuszanie timera rund — sweep wygasłych rund + migracje DB
```

**ZAMIEŃ NA:**
```
◆ System automatycznie kończy turę gracza po upłynięciu czasu — nieaktywne rundy są zamykane
```

**POWÓD:** „Sweep", „migracje DB" — żargon techniczny/deweloperski niewidoczny i nieistotny dla gracza.

---

## POPRAWKA C08
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ współdzielony world state dla rund MP
```

**ZAMIEŃ NA:**
```
◆ Wszyscy gracze w sesji widzą ten sam stan świata — zmiany jednego gracza są natychmiast widoczne dla pozostałych
```

**POWÓD:** „World state" — wewnętrzna nazwa systemu. „Rund MP" — skrót niezrozumiały.

---

## POPRAWKA C09
**SEKCJA:** Changelog — nagłówek wpisu

**ORYGINAŁ:**
```
Admin Panel Mobile + redesign obrony walki + dual-wield/amunicja + FAZA LB (lochy onboarding) + audyt
```

**ZAMIEŃ NA:**
```
Panel administratora na telefon, nowy model obrony w walce, walka oburęczna i amunicja, wprowadzenie do lochów
```

**POWÓD:** „FAZA LB", „redesign", „dual-wield", „onboarding", „audyt" — mieszanka angielskiego żargonu i wewnętrznych etykiet.

---

## POPRAWKA C10
**SEKCJA:** Changelog — szczegóły wpisu (opis nowego modelu walki)

**ORYGINAŁ:**
```
◆ Jeden rzut obronny na trafienie (koniec double jeopardy). Pancerz (ac_base/AC) = redukcja obrażeń, …
```

**ZAMIEŃ NA:**
```
◆ Jeden rzut decyduje, czy cios trafia. Pancerz zmniejsza obrażenia zamiast blokować trafienie — koniec sytuacji, gdzie gracz był karany dwa razy za jeden cios
```

**POWÓD:** „Double jeopardy", „ac_base/AC" — angielskie terminy techniczne. „AC" to skrót z D&D nieznany nowemu graczowi.

---

## POPRAWKA C11
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ Margines ataku → obrażenia: +1 dmg za każde pełne 5 pkt nadwyżki; Nat 20 ×2 osobno. Symetryczny gra…
```

**ZAMIEŃ NA:**
```
◆ Im wyżej wyrzucisz ponad wymagany próg, tym więcej obrażeń zadajesz (+1 za każde 5 punktów nadwyżki). Wynik 20 na kości podwaja obrażenia osobno
```

**POWÓD:** „Margines ataku", „dmg", „pkt nadwyżki", „Nat 20", „Symetryczny" — żargon RPG/deweloperski.

---

## POPRAWKA C12
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ Helpery apply_defense_model / compute_enemy_attack_hit w combat_service.py; wartości startowe stroj…
```

**ZAMIEŃ NA:**
```
◆ Nowy silnik obliczania walki — wartości startowe będą dostrajane na podstawie testów rozgrywki
```

**POWÓD:** Nazwy funkcji z kodu (`apply_defense_model`, `combat_service.py`) są kompletnie niewidoczne dla gracza. Ten punkt w changelogu dla graczy powinien w ogóle zostać usunięty lub zastąpiony wyjaśnieniem skutku.

---

## POPRAWKA C13
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ Karta ataku wroga pokazuje pasywny unik (d20+ZRC) zamiast vs AC ; kalkulacja redukcji pancerza wido…
```

**ZAMIEŃ NA:**
```
◆ Interfejs walki pokazuje teraz, jak wróg próbuje uniknąć ciosu i jak działa redukcja pancerza — więcej informacji podczas starcia
```

**POWÓD:** „Pasywny unik (d20+ZRC)", „vs AC", „kalkulacja redukcji" — żargon techniczny. Gracz chce wiedzieć, co widzi na ekranie, nie jak to jest obliczane.

---

## POPRAWKA C14
**SEKCJA:** Changelog — nagłówek wpisu

**ORYGINAŁ:**
```
FAZA L (lochy kafelkowe) + FAZA O (observability + archmap) + fixy walki i lokacji
```

**ZAMIEŃ NA:**
```
Lochy z mapą kafelkową, narzędzia diagnostyczne dla deweloperów, poprawki walki i lokacji
```

**POWÓD:** „FAZA L", „FAZA O", „observability", „archmap", „fixy" — wewnętrzne etykiety i żargon deweloperski.

---

## POPRAWKA C15
**SEKCJA:** Changelog — szczegóły wpisu (lochy)

**ORYGINAŁ:**
```
◆ Silnik lochu kafelkowego: generowanie proceduralnych map z kafli PNG, tryb endless (go_deeper), che…
```

**ZAMIEŃ NA:**
```
◆ Lochy generują się proceduralnie — każda sesja to inna mapa. Tryb „idź głębiej" pozwala schodzić kolejne poziomy bez końca
```

**POWÓD:** „Kafli PNG", „go_deeper" (nazwa funkcji), „che…" — techniczne szczegóły implementacji.

---

## POPRAWKA C16
**SEKCJA:** Changelog — szczegóły wpisu (kafle)

**ORYGINAŁ:**
```
◆ 40+ kafli krypty: kategoria nieumarłych (, 20 kafli 768px), kafle zaślepki N/S/E/W, kafle krypty 26…
```

**ZAMIEŃ NA:**
```
◆ Ponad 40 grafik kafelków krypty z kategorią nieumarłych — nowe klimaty wizualne dla lochów
```

**POWÓD:** „768px", „kafle zaślepki N/S/E/W", „kafle krypty 26…" — dane techniczne artysty/dewelopera, nie gracza.

---

## POPRAWKA C17
**SEKCJA:** Changelog — nagłówek wpisu

**ORYGINAŁ:**
```
FAZA S/B/SF/HI: silnik skilli i stanów, balans klas, feedback walki, Inspektor Bohatera
```

**ZAMIEŃ NA:**
```
System umiejętności i stanów, balans klas, nowe informacje zwrotne w walce, podgląd bohatera w panelu
```

**POWÓD:** „FAZA S/B/SF/HI" — wewnętrzne kody etapów. „Skilli" — ang. slang. „Feedback walki" — ang. termin. „Inspektor Bohatera" brzmi jak narzędzie deweloperskie, nie jak feature.

---

## POPRAWKA C18
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ FAZA S — silnik Skilli i Stanów : backend silnika skilli/stanów (+ ogon FAZY U); pełny suite pytest…
```

**ZAMIEŃ NA:**
```
◆ Nowy system umiejętności i stanów — efekty tymczasowe działają teraz spójnie w całej grze
```

**POWÓD:** „Backend silnika", „ogon FAZY U", „suite pytest" — zapis implementacyjny dla dewelopera, nie gracza.

---

## POPRAWKA C19
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ FAZA S/U frontend: karty rzutu z marginesem sukcesu i przerzutem, kondycje w Sandboxie, targowanie …
```

**ZAMIEŃ NA:**
```
◆ Karty rzutu pokazują teraz margines sukcesu i opcję przerzutu. Stany postaci widoczne w podglądzie
```

**POWÓD:** „Frontend", „Sandbox" (nazwa środowiska testowego), urwany tekst — żargon techniczny.

---

## POPRAWKA C20
**SEKCJA:** Changelog — nagłówek wpisu

**ORYGINAŁ:**
```
FAZA U: Blok 4 ekonomia/UX + unifikacja przedmiotów + usability
```

**ZAMIEŃ NA:**
```
Ekonomia i sklep, ujednolicenie systemu przedmiotów, poprawki użyteczności
```

**POWÓD:** „FAZA U: Blok 4", „UX", „unifikacja", „usability" — wewnętrzne etykiety i angielski żargon UX.

---

## POPRAWKA C21
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ Unifikacja przedmiotów → game_items (/556/557/558): jedna tabela zamiast 3 (weapons/armor/items/con…
```

**ZAMIEŃ NA:**
```
◆ Wszystkie przedmioty — broń, zbroja, eliksiry — są teraz w jednym, spójnym systemie
```

**POWÓD:** Nazwa tabeli z bazy danych i numery migracji (`/556/557/558`) są kompletnie nieprzydatne dla gracza.

---

## POPRAWKA C22
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ Content pipeline : seed_lint_service (świeża baza → schemat → seedy 01–15 → lint +); CLI host+konte…
```

**ZAMIEŃ NA:**
```
◆ Poprawiono proces wdrażania nowej zawartości gry — nowe kampanie i przedmioty są łatwiejsze do dodania
```

**POWÓD:** `seed_lint_service`, `CLI`, `lint` — to opis pipeline'u CI/CD deweloperów. W changelogu dla graczy powinno być albo usunięte, albo opisane skutkiem.

---

## POPRAWKA C23
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ Celebracja dropu afiksowego : karta po claimie dla broni/zbroi specjalnej — kolor rzadkości, afiksy…
```

**ZAMIEŃ NA:**
```
◆ Nowa karta nagrody po zdobyciu wyjątkowego przedmiotu — pokazuje kolor rzadkości i specjalne właściwości
```

**POWÓD:** „Drop afiksowy", „claim", „afiksy" — żargon game-dev. „Celebracja dropu" brzmi jak notatka z backlogu.

---

## POPRAWKA C24
**SEKCJA:** Changelog — nagłówek wpisu

**ORYGINAŁ:**
```
FAZA U: pancerz LLM, system hexów świata, effect schema lockdown
```

**ZAMIEŃ NA:**
```
Instrukcje dla AI o mechanice walki, mapa świata z hexami, zablokowanie schematu efektów
```

**POWÓD:** „Pancerz LLM" (prompt context dla AI), „effect schema lockdown" — wewnętrzny żargon deweloperski bez żadnej wartości dla gracza. Ten nagłówek powinien być przepisany lub połączony z innym wpisem.

---

## POPRAWKA C25
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ Placement engine: backend osadza lokacje z bazy przy odkryciu hexa (terrain_tags + placement)
```

**ZAMIEŃ NA:**
```
◆ Odkrywanie nowego heksa na mapie świata automatycznie generuje lokacje pasujące do terenu
```

**POWÓD:** „Placement engine", „terrain_tags", „backend" — architektura systemu.

---

## POPRAWKA C26
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ Ruch mechaniczny: POST /travel (klik mapy = podróż, intent MOVE rozstrzygany przed LLM, anty-desync…
```

**ZAMIEŃ NA:**
```
◆ Kliknięcie heksa na mapie = natychmiastowa podróż — gra rozstrzyga ruch przed przekazaniem go AI, co eliminuje niespójności
```

**POWÓD:** `POST /travel`, `intent MOVE`, `anty-desync` — implementacja techniczna endpointu API.

---

## POPRAWKA C27
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ Scena z bazy: ENTER_LOCATION ładuje scene_npcs/scene_enemies z przypisań; travel pills z prawdziwyc…
```

**ZAMIEŃ NA:**
```
◆ Po wejściu do lokacji NPC i wrogowie są pobierani z bazy danych — koniec losowych, niespójnych spotkań
```

**POWÓD:** `ENTER_LOCATION`, `scene_npcs/scene_enemies`, `travel pills` — nazwy wewnętrznych eventów i komponentów UI.

---

## POPRAWKA C28
**SEKCJA:** Changelog — nagłówek wpisu

**ORYGINAŁ:**
```
Affix system, economy effect builder, SPEND_GOLD, bugfixy
```

**ZAMIEŃ NA:**
```
System właściwości przedmiotów, konstruktor efektów ekonomicznych, wydawanie złota, poprawki
```

**POWÓD:** „Affix system", `SPEND_GOLD` (nazwa eventu/komendy), „economy effect builder" — anglojęzyczny żargon techniczny.

---

## POPRAWKA C29
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ typowane Effect Objects w silniku walki (damage_bonus, heal_on_hit, ac_bonus, static_stat_modifier,…
```

**ZAMIEŃ NA:**
```
◆ Nowy system efektów w walce: premie do obrażeń, leczenie przy trafieniu, bonus do pancerza i inne — wszystkie działają przez jeden spójny mechanizm
```

**POWÓD:** `damage_bonus`, `heal_on_hit`, `ac_bonus`, `static_stat_modifier` — nazwy klas/obiektów z kodu.

---

## POPRAWKA C30
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ loot engine losuje afiksy per dungeon tier przy dropach wrogów
```

**ZAMIEŃ NA:**
```
◆ Wrogowie upuszczają przedmioty ze specjalnymi właściwościami dopasowanymi do poziomu lochu
```

**POWÓD:** „Loot engine", „afiksy", „per dungeon tier", „dropach" — techniczny żargon.

---

## POPRAWKA C31
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ loot_tier na game_config_enemies + roll afiksów dla dropów wrogów
```

**ZAMIEŃ NA:**
```
◆ Każdy wróg ma przypisany poziom łupów — gra automatycznie dobiera właściwości upuszczanego ekwipunku
```

**POWÓD:** `loot_tier`, `game_config_enemies`, „roll afiksów" — implementacja techniczna.

---

## POPRAWKA C32
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ POST/PATCH/DELETE /api/admin/affixes — pełne CRUD
```

**ZAMIEŃ NA:**
```
◆ Panel administratora: pełne zarządzanie właściwościami przedmiotów (dodawanie, edycja, usuwanie)
```

**POWÓD:** `POST/PATCH/DELETE /api/admin/affixes` i „CRUD" to dokumentacja API, nie changelog dla graczy.

---

## POPRAWKA C33
**SEKCJA:** Changelog — nagłówek wpisu

**ORYGINAŁ:**
```
Lochy pełna treść, onboarding, Uczony zaklęcia, bugfixy
```

**ZAMIEŃ NA:**
```
Pełna zawartość lochów, wprowadzenie dla nowych graczy, zaklęcia Uczonego, poprawki
```

**POWÓD:** „Onboarding" — angielskie słowo. „Bugfixy" — angielski slang deweloperski.

---

## POPRAWKA C34
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ POST /api/campaigns/{id}/cast-spell — endpoint dla nieofensywnych zaklęć poza walką
```

**ZAMIEŃ NA:**
```
◆ Można teraz rzucać niebojowe zaklęcia poza walką — np. Magiczne Światło podczas eksploracji
```

**POWÓD:** `POST /api/campaigns/{id}/cast-spell` — endpoint REST API. Gracz nie potrzebuje znać ścieżki URL.

---

## POPRAWKA C35
**SEKCJA:** Changelog — nagłówek wpisu

**ORYGINAŁ:**
```
FADM strangler fig ukończony
```

**ZAMIEŃ NA:**
```
Nowy panel administracyjny — ukończony
```

**POWÓD:** „FADM" to wewnętrzny akronim, „strangler fig" to wzorzec architektoniczny oprogramowania (Strangler Fig Pattern). Kompletnie niezrozumiałe poza zespołem deweloperskim.

---

## POPRAWKA C36
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ FADM strangler fig ukończony — modularny admin shell /admin/ zastępuje monolityczny admin3; 18 faz, …
```

**ZAMIEŃ NA:**
```
◆ Nowy panel administracyjny zastąpił stary — modularny, szybszy i łatwiejszy do rozbudowy
```

**POWÓD:** „Strangler fig", „admin shell", „admin3", „18 faz" — terminologia architektoniczna i wewnętrzne nazewnictwo.

---

## POPRAWKA C37
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ SSE heartbeat fix — group-run Playwright nie zrywa SSE (network error) przy ~90s ciszy startu; naty…
```

**ZAMIEŃ NA:**
```
◆ Naprawiono stabilność połączeń długotrwałych sesji — nie rozłączają się po dłuższej ciszy
```

**POWÓD:** „SSE heartbeat", „group-run Playwright", `network error` — implementacja techniczna WebSocket/SSE.

---

## POPRAWKA C38
**SEKCJA:** Changelog — nagłówek wpisu

**ORYGINAŁ:**
```
Admin panel modularny (FADM) + onboarding theme
```

**ZAMIEŃ NA:**
```
Nowy panel administracyjny + wybór motywu wizualnego przy starcie
```

**POWÓD:** „(FADM)", „onboarding theme" — wewnętrzny akronim i angielski termin.

---

## POPRAWKA C39
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ hub kampanii — 5 trybów z flagami dostępności (Nowa / Gotowa / Loch / Loch-kafelki / Multiplayer)
```

**ZAMIEŃ NA:**
```
◆ Centrum kampanii — 5 trybów gry: Nowa kampania, Kontynuuj, Loch, Loch z mapą kafelkową, Multiplayer
```

**POWÓD:** „Flagami dostępności" — termin deweloperski. Lista powinna być czytelna dla gracza.

---

## POPRAWKA C40
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ ekran profilu gracza — edycja email, lista znajomych, ustawienia LLM Connect
```

**ZAMIEŃ NA:**
```
◆ Ekran profilu: zmiana adresu email, lista znajomych i ustawienia połączenia z własnym modelem AI
```

**POWÓD:** „LLM Connect" — wewnętrzna nazwa funkcji. Gracz powinien wiedzieć, co to robi, nie jak się nazywa w kodzie.

---

## POPRAWKA C41
**SEKCJA:** Changelog — nagłówek wpisu

**ORYGINAŁ:**
```
Harness testów – + panel Playwright w admin3
```

**ZAMIEŃ NA:**
```
Automatyczne testy akceptacyjne — nowe narzędzia dla zespołu
```

**POWÓD:** „Harness testów", „Playwright", „admin3" — wyłącznie dla deweloperów. Ten wpis w ogóle nie powinien pojawiać się w changelogu dla graczy — ewentualnie do ukrycia lub przeniesienia do sekcji technicznej.

---

## POPRAWKA C42
**SEKCJA:** Changelog — szczegóły wpisu

**ORYGINAŁ:**
```
◆ Harness testów akceptacyjnych – (pytest + Playwright), uruchamialny z admin3 → Narzędzia → 🎭 Playwr…
```

**ZAMIEŃ NA:**
*(cały wpis do usunięcia lub przeniesienia do sekcji „zmiany techniczne" — jest tylko dla deweloperów)*

**POWÓD:** `pytest`, `Playwright`, ścieżka nawigacji w panelu admin — bez wartości dla gracza.

---

## ══════════════════════════════════════
## PODSTRONA: /showcase/swiat.html — Świat
## ══════════════════════════════════════

## POPRAWKA S01
**SEKCJA:** Świat — wprowadzenie / akapit o Rdzeniu

**ORYGINAŁ:**
```
Pod tym wszystkim — pod traktami, polami, ruinami i lodem — leży Rdzeń Pradawnych: pierwotne źródło mocy, którego nadużycie popękało granicę między światem żywych a tym, co za nią. Z tych pęknięć przecieka wszystko, co najgorsze.
```

**ZAMIEŃ NA:**
```
Pod tym wszystkim — pod traktami, polami, ruinami i lodem — leży Rdzeń Pradawnych: pradawne źródło mocy, które ktoś kiedyś nadużył. To nadużycie pękło granicę między światem żywych a tym, co za nią leży. Z tych pęknięć przecieka wszystko, co najgorsze.
```

**POWÓD:** „Którego nadużycie popękało granicę" — nienaturalna konstrukcja, brzmi jak przetłumaczona kalka. Rozbicie na dwa zdania jest czytelniejsze.

---

## POPRAWKA S02
**SEKCJA:** Świat — lore o Rdzeniu / podsekcja „Kulty Rdzenia"

**ORYGINAŁ:**
```
Kulty Rdzenia — robią odwrotnie: tam, gdzie Światło pęknięcia łata, kulty je poszerzają — bo wierzą, że za nimi czeka moc, wieczność albo bóg. Ich „nekrotyczna moc płynąca przez symbol b…
```

**ZAMIEŃ NA:**
```
Kulty Rdzenia robią odwrotnie: tam, gdzie Świątynia Światła pęknięcia łata, kulty je poszerzają — wierzą, że za nimi czeka moc, wieczność albo bóg. Ich magia płynie z ciemności Rdzenia.
```

**POWÓD:** „Nekrotyczna moc płynąca przez symbol" — zdanie urwane i brzmi jak notatka lore-designera. „Nekrotyczna" to termin z RPG, który warto zastąpić lub wyjaśnić.

---

## POPRAWKA S03
**SEKCJA:** Świat — Frakcje / „Plaga nieumarłych"

**ORYGINAŁ:**
```
Plaga nieumarłych — Lisze, wampiry (Mistrz Wampirów, Krwawy Hrabia), ghule, widma. Nie „lud"
```

**ZAMIEŃ NA:**
```
Nieumarli — Lisze, wampiry (Mistrz Wampirów, Krwawy Hrabia), ghule, widma. To nie lud ani frakcja — to zagrożenie.
```

**POWÓD:** „Plaga nieumarłych" sugeruje mechanikę gry (plagę), podczas gdy to po prostu kategoria wrogów. Urwane zdanie „Nie »lud«" potrzebuje dokończenia.

---

## POPRAWKA S04
**SEKCJA:** Świat — Ludy / „Nieumarli"

**ORYGINAŁ:**
```
Nieumarli — Lisze, wampiry, ghule, widma. Nie „lud"
```

**ZAMIEŃ NA:**
```
Nieumarli — Lisze, wampiry, ghule, widma. To nie jest frakcja ani lud — to wrogowie, których napędza siła Rdzenia.
```

**POWÓD:** „Nie »lud«" — urwane, niezrozumiałe zdanie. Wymaga dokończenia.

---

## POPRAWKA S05
**SEKCJA:** Świat — Ludy / krasnoludy

**ORYGINAŁ:**
```
Górski lud kowali i górników z Siwych Grani. Odeszli z Czarnego Hutmana, gdy dowiercili się do żyły…
```

**ZAMIEŃ NA:**
```
Górski lud kowali i górników z Siwych Grani. Opuścili kopalnie Czarnego Hutmana, gdy nawiercili się na coś, czego nikt nie powinien był budzić…
```

**POWÓD:** „Dowiercili się do żyły" — niejasne, brzmi jakby chodziło o żyłę rudy. W kontekście lore chodzi o coś złowrogiego — warto to zasugerować.

---

## POPRAWKA S06
**SEKCJA:** Świat — Historia świata / Epoka Pradawnych

**ORYGINAŁ:**
```
Zaawansowana, przed-ludzka cywilizacja opanowała moc Rdzenia — i to ją zniszczyło. Zostały ruiny pe…
```

**ZAMIEŃ NA:**
```
Przed-ludzka cywilizacja opanowała moc Rdzenia i sięgnęła za daleko — i to ją zniszczyło. Zostały ruiny pełne zagadek i niebezpieczeństw.
```

**POWÓD:** „Zaawansowana" w tym kontekście brzmi jak opis z Wikipedii, nie jak lore RPG. Urwane zdanie potrzebuje dokończenia.

---

## POPRAWKA S07
**SEKCJA:** Świat — Historia świata / Zmierzch Latarni

**ORYGINAŁ:**
```
Imperium słabnie, podatki rosną, granice się cofają. Wsie palone (Zgliszcza — rok temu), kopalnie p…
```

**ZAMIEŃ NA:**
```
Imperium słabnie, podatki rosną, granice się cofają. Wsie płoną — jak Zgliszcza, spalone rok temu. Kopalnie pustoszeją.
```

**POWÓD:** „Wsie palone (Zgliszcza — rok temu)" — nawias w środku zdania brzmi jak przypis designerski, nie jak narracja. Urwane zdanie.

---

## ══════════════════════════════════════
## INSTRUKCJA DLA AGENTA EDYCYJNEGO
## ══════════════════════════════════════

```
1. Znajdź w plikach HTML/JS/JSON strony dokładny ciąg znaków z pola ORYGINAŁ.
2. Zastąp go ciągiem z pola ZAMIEŃ NA.
3. Jeśli ORYGINAŁ jest urwany (kończy się na „…"), wyszukaj unikalny fragment
   bez „…" — np. pierwsze 40 znaków bez wielokropka.
4. Nie zmieniaj niczego poza wskazanym fragmentem.
5. Po każdej zamianie sprawdź, czy strona renderuje się poprawnie.
6. Poprawki C42 i podobne oznaczone „do usunięcia" — przed usunięciem zapytaj
   Piotra o potwierdzenie (mogą być widoczne tylko dla adminów).
```

---

## PODSUMOWANIE STATYSTYK

| Podstrona | Liczba poprawek |
|---|---|
| /showcase/index.html (plik v1) | 30 |
| /rules/ | 24 (R01–R24) |
| /showcase/changelog.html | 42 (C01–C42) |
| /showcase/swiat.html | 7 (S01–S07) |
| **RAZEM** | **103** |
