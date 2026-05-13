# Szkic mechanik — przykłady liczb (do przyszłej instrukcji)

**Status:** projekt (uchwały w [`../04_decisions_log.md`](../04_decisions_log.md)). Tekst poniżej ma służyć **zrozumieniu** i późniejszemu przepisaniu do książki gracza — liczby w przykładach są **ilustracyjne**; dokładne wartości ustalicie przy balansie.

---

## 0. Cechy postaci (statystyki) a LLM — **[S3]**

**Zasada:** Lista **liczbowych** cech (siła, zwinność, itd.) jest **zamknięta w konfiguracji**. LLM może proponować **nazwy i opisy** talentów, stylów, umiejętności — ale w tle **zawsze** musi to być **przypięte do istniejącej cechy** z tej listy. **Nowa cecha liczona w mechanice** = **nowa wersja zasad** (aktualizacja bazy i zasad), nie samowolny dopisek z rozmowy z modelem.

---

## 0a. Która cecha do której umiejętności — **[S4b]**

**Ustalenie:** W konfiguracji przy każdej umiejętności jest zapisane, **która cecha** (np. zwinność) wchodzi do rzutu. **Ta baza jest panem** — zmiana w panelu admina ma **od razu** zmieniać liczenie w grze (po wdrożeniu odczytu z bazy zamiast sztywnej listy w programie).

---

## 0c. Trudność testu (DC) — słowa w opowieści, liczba z tabeli — **[S5]**

**Idea:** W konfiguracji jest **jedna tabela** poziomów (np. łatwy, średni, trudny) z **konkretnymi liczbami**. Mistrz Gry może **opisać** sytuację i powiedzieć graczowi: „to będzie **trudny** test na Skradanie” (światło, żwir…). **Mechanika** przy rzucie bierze **`value`** przypisane do **trudny** — model **nie wymyśla** własnej liczby DC.

**Kiedy w ogóle jest DC:** Poziomy łatwy/trudny mają znaczenie, **tylko gdy** odbywa się **rzut**. Jeśli akcja zostaje bez testu (czysta narracja), **nie** przypisujecie jej do wiersza z tabeli.

---

## 0d. Opis umiejętności — gracz i LLM — **[S5a]**

**Kierunek:** Lista umiejętności z bazy (nazwa, opis, powiązana cecha…) ma trafiać do **kontekstu** Mistrza Gry i do **pokazu dla gracza**. Pole **`description`** redagujecie tak, żeby było zrozumiałe **ludziom** i pomagało modelowi **rozstrzygać**, czy w danej sytuacji pasuje **test** z katalogu, czy tylko opowieść. Jeśli okaże się za mało — można później dodać pole pomocnicze lub szablon promptu (**bez** „nowych umiejętności” spoza bazy).

---

## 0e. Warunki, JSON, przedmioty — **[S6]**

**Jeden język efektów ([S2] + [S6]):** Stany na postaci (podpalenie, strach, trucizna…) i efekty mikstur / przedmiotów mają być zapisane w **tym samym rodzaju JSON-u** (wspólny schemat / walidacja), żeby admin i kod nie uczyły się dwóch dialektów.

**Nie mylić „stanu” z „bonusem z przedmiotu”:** Ten sam format może opisać np. **+3 do STR** z magicznego pierścienia (to **nie** jest „stan choroby”) oraz osobno **zatruty** jako stan przyklejony do postaci — w JSON-ie rozróżnia się **typ efektu / kategorię**, nie tylko liczby.

**Zasada ogólna — planowanie tabel:** Złożone stany (powtarzalne rzuty, DC z **[S5]**, narracja przy utracie kontroli, warunki zdjęcia) projektujemy jako **parametry w JSON-ie / typach efektów**, żeby **wiele** różnych stanów dało się opisać **tym samym mechanizmem** — bez osobnej kolumny w bazie na każdą nazwę stanu, o ile to możliwe.

**Ilustracja (jedna z wielu):** Np. **przerażenie** — co rundę test na cechę, **trudny** DC z tabeli; porażka → narracja (ucieczka, brak pełnej kontroli); powrót kontroli → kolejny trudny test lub uzgodniona procedura. Inne stany (urok, szaleństwo…) mogą używać **tego samego wzorca** z innymi parametrami.

---

## 0f. Konsumable — jeden katalog, jeden klucz — **[S6]**

**Katalog:** Mikstury i inne zużywalne rzeczy są **przedmiotami** (`game_config_items`, typ consumable). **Jeden `key`** dla danej mikstury **wszędzie** — łup, sklep, quest — bez „dwóch kopii tej samej rzeczy”.

---

## 0b. Umiejętności — rangi, kara, pierwszy wykup — **[S4]**

**Sufit:** Maksymalna ranga umiejętności to **5**.

**Bonus na szczycie:** Ranga **5** ma dawać **większy modyfikator niż +5** (sam bonus od rang — dokładne liczby przy balansie), zaś **wykup** ostatniego stopnia ma **kosztować znacznie więcej XP** niż niższe.

**Kara:** Jeśli ktoś **deklaruje** test np. na **skradanie**, ale **nie ma** tej umiejętności na karcie — dostaje **ujemny modyfikator** (próba „na czuja”).

**Bez „rang 0”:** W praktyce albo **kara** (brak treningu przy próbie), albo **rangi dodatnie 1 → 5**. Pierwszy **wykup** umiejętności: **bazowo +1** do testów z nią związanych.

**Przykład (liczby zmyślone, tylko ilustracja):**

| Ranga | Bonus od umiejętności (szkic) | Uwagi |
|-------|----------------------------------|--------|
| (brak, próba bez umiejętności) | **−2** | kara |
| 1 (pierwszy wykup) | **+1** | Twoje ustalenie |
| 2 | +2 | … |
| … | … | … |
| 5 | **> +5** (np. +7 w tabeli docelowej) | drogi w XP |

---

## 0g. Pula XP — skąd bierze się i co kosztuje rangę — **[S10a]**, **[S10b]**, **[S10c]**

**Idea:** Postać **nie ma poziomu (LVL)**; rośniesz, wydając XP z **puli** na cechy (gdy będą w zasadach) i **rangi umiejętności**. Kolejność wydatków — **dowolna** (o ile stać cię na koszt i sufit rangi).

**„Sesja” ≠ od logowania do wylogowania.** W tekście poniżej **„na odcinek”** oznacza fragment fabuły między wyraźnymi zwrotami (wypoczynek, zmiana lokacji, koniec walki itd.) — zob. **[S10c]** w uchwałach. Przy grze **bardzo asynchronicznej** ten sam sufit grantów MG można stosować **łącznie na tydzień kalendarzowy**.

**Koszty rang (domyślne w konfiguracji, MG może zmienić w adminie):** przejście na rangę 1, 2, 3, 4, 5 to odpowiednio ok. **50 / 100 / 200 / 400 / 1200** XP (dokładne wartości w `game_config_meta` → `xp_skill_rank_costs`).

**Przyznawanie — startowe widełki (Mistrz Gry i baza wrogów):**

| Sytuacja | Szacunek XP |
|----------|-------------|
| Słaby wróg (tło) | 2–5 |
| „Zwykły” napastnik (np. goblin w bazie: 3) | 5–12 |
| Twardszy przeciwnik | 12–25 |
| Elita / mały boss | 25–50 |
| Duży boss | 50–120 (rzadko) |
| MG: drobny bonus (dobry opis, zabawny moment) | 3–8 |
| MG: mini-cel z roadmapy / wyraźny postęp sceny | 5–15 |
| MG: duży przełom fabularny (często max 1× **na odcinek gry**) | 15–35 |
| MG: wybitny sukces (rzadko) | 35–60 |

**Na odcinek gry** (albo **na tydzień kalendarzowy**, jeśli asynchronicznie nie widać granic odcinka) z samych **grantów MG** (bez walki) sensowny **sufit** to ok. **60–100 XP** łącznie; więcej tylko uzasadnione. XP z walki **dodaje się** niezależnie.

*(Definicja „odcinka”: **[S10c]**; liczby: **[S10b]** w [`../04_decisions_log.md`](../04_decisions_log.md).)*

---

## 1. Obrażenia (kierunek zgodny z ustaleniami)

**Idea:** wynik kości broni + modyfikator z odpowiedniej cechy + ewentualne bonusy (magia przedmiotu, stan postaci, itd. — na później).

**Propozycja dopasowania cechy do broni (Twoje ustalenie):**

- Broń wręcz (topór, miecz, itd.) → zwykle **siła (STR)**.
- Broń dystansowa (łuk, kusza, bicz, itd.) → zwykle **zwinność (DEX)**.

W bazie przy broni jest pole „która cecha liczy się do obrażeń” — docelowo ma być zgodne z tą logiką (i z typem broni).

### Przykład A — miecz wręcz (kość 1d8), STR +3

1. Rzucasz **1d8** → np. **5**.
2. Dodajesz modyfikator STR **+3**.
3. **Obrażenia = 5 + 3 = 8** (przed redukcjami pancerza, jeśli kiedyś dodacie).

### Przykład B — łuk (kość 1d6), DEX +2

1. Rzucasz **1d6** → np. **4**.
2. Dodajesz DEX **+2**.
3. **Obrażenia = 4 + 2 = 6**.

*(Jeśli w przyszłości pojawi się broń „zwinna” w stylu szpady, można rozważyć wybór lepszej z STR/DEX — **nie** jest to jeszcze uchwalone osobno; na razie trzymamy się STR/DEX wg typu broni jak wyżej.)*

---

## 2. Dwuręczność (jako umiejętność — kierunek)

**Twoje ustalenie:** „dwuręczność” to **umiejętność** (skill), nie tylko pole przy broni.

- **Masz wykupioną umiejętność** → **dodatnie** modyfikatory przy broni dwuręcznej (dokładna wartość przy balansie).
- **Nie masz umiejętności** i używasz broni 2H → **ujemny modyfikator** (kara do ataku lub do obrażeń — **do wyboru przy implementacji**; to **nie** jest to samo co „DC testu” — DC zwykle znaczy próg trudności przy rzucie, tutaj chodzi o **karę**).
- **Tarcza albo broń w drugiej ręce** → **nie możesz** jednocześnie używać wielkiego miecza dwuręcznego w tym stylu (zgodnie z Twoim opisem).

**Przykład (liczby zmyślone):**

- Z umiejętnością: atak mieczem 2H może mieć **+1** do trafienia względem wersji bez umiejętności.
- Bez umiejętności: ten sam miecz 2H **−2** do trafienia (albo do obrażeń — do ustalenia w jednej linii z zespołem).

---

## 3. Typ broni a rodzaj ataku

**Twoje ustalenie:** typ musi się zgadzać:

| Typ w bazie | Przykłady | Rodzaj ataku w grze |
|-------------|-----------|---------------------|
| Wręcz | pięści, miecz, topór | Atak wręcz |
| Dystans | łuk, kusza, dmuchawka | Atak dystansowy |
| Magia | — | Atak magiczny; może być **na jednego** albo **obszar (AOE)** — szczegóły zapisu w konfiguracji później |

Cel: żeby nie było sytuacji „mam łuk, a system traktuje to jak cios mieczem”.

---

## 4. Zasięg (na teraz)

**Twoje ustalenie:** zasięg w metrach służy **tylko** do sprawdzenia, czy strzał / magia **doleciała do celu** (czy cel jest w zasięgu), a nie do pełnej symulacji taktyki.

---

## 5. Kolejność wdrożeń

**Twoje ustalenie:** w fazie developerskiej **wszystkie** te elementy mają w końcu trafić do gry; **nie** ustalacie na razie kolejności programowania — ważne jest, żeby **projekt** był spójny przed kodem.

---

## 6. Trafienie vs obrona (atak kontra „trudność trafienia”)

### Co robi gra dziś (skrót, żebyś widział różnicę z planem)

W obecnym silniku walki wynik **trafienia** gracza jest rozstrzygany przez **porównanie** wyniku twojego ataku z **unikiem** przeciwnika (rzut k20 + zwinność wroga), z zasadami w stylu: naturalne 20 często gwarantuje trafienie, 1 — chybienie; przy remisie korzyść dla obrońcy. To **nie** jest jeszcze pełny, jednolity model „atak vs klasa pancerza (AC)” dla wszystkich typów, o jakim myślisz na przyszłość.

### Kierunek na przyszłość (do dopisania w kolejnej rundzie projektu)

**Pytanie otwarte:** jedna wspólna obrona dla wszystkich rodzajów ataku (wręcz, dystans, magia), czy osobne ścieżki z tym samym **celem** (np. jedna liczba obrony na postać/wroga, ale inne bonusy sytuacyjne)?

**Sugestia do decyzji później:** zapisać jedną krótką procedurę w instrukcji, np.:

1. Oblicz **wartość ataku** (k20 + modyfikatory ataku dla danego typu).
2. Porównaj z **obroną celu** (jedna liczba lub „trudność uniku” — jak ustalicie).
3. Trafienie, jeśli atak ≥ obrona (albo inna reguła remisu — do ustalenia).

To ma być **ta sama logika** dla wręcz, dystansu i magii, żeby gracz nie uczył się trzech systemów.

---

## 7. Testy przeciwstawne — np. skradanie vs wypatrywanie / słuch

Tu nie chodzi o jeden rzut przeciw **DC świata**, tylko o **dwie strony**.

**Propozycja szkieletu (do uchwalenia w osobnej turze):**

1. **Skradający** rzuca: k20 + modyfikator skradania (i ewentualnie inne bonusy).
2. **Strażnik / wróg** rzuca: k20 + wypatrywanie lub słuch (zależnie od sytuacji).
3. **Wynik:** wyższy wynik wygrywa. **Remis (równe sumy):** zawsze **korzyść dla obrońcy** (np. strażnik wykrywa skradającego).

**Przykład (liczby zmyślone):**

- Złodziej: k20 = **14** + skradanie **+5** → **19**.
- Strażnik: k20 = **10** + percepcja **+3** → **13**.
- **19 > 13** → złodziej przechodzi niezauważony.

*(Jeśli wolisz model „test skradania vs ustalone DC zamiast dwóch rzutów”, też da się — to osobna uchwała.)*

---

## 8. Przedmioty — jeden zapis mechaniki (JSON) i pomoc dla osoby w panelu

**Ustalenie:** Mechanikę przedmiotu najlepiej trzymać w **jednym ustandaryzowanym formacie** (docelowo JSON według schematu), żeby gra i Mistrz Gry miały **jedno źródło prawdy**.

**Problem:** Ręczne pisanie JSON-a w panelu jest podatne na błędy.

**Kierunek (zaakceptowany):** **Generator wspomagany przez LLM** — opisujesz po ludzku, co ma robić przedmiot (np. „mikstura leczy X życia i zamienia rany z krytycznych na ciężkie, z ciężkich na lekkie”), system **proponuje** gotową formułę w poprawnym schemacie; **Ty sprawdzasz** i zapisujesz. To nie zastępuje myślenia — tylko **pomaga** trafić w format.

---

## 9. Pancerz i rzuty

**Ustalenie:** Pancerz ma **wchodzić w liczenie** (obrona przy trafieniu / redukcja — dokładna formuła przy projekcie walki).

**Na teraz (uproszczenie):** np. skórzana zbroja **+1** do obrony **jak do „wszystkich lokacji” naraz** — jedna liczba, żeby gra działała spójnie.

**Na później (zapowiedź):** podział na **części ciała** (głowa, tułów, ręce, nogi), **deklaracja** ataku w strefę, **inne szanse** na trafienie w wąską strefę — osobna rozmowa; obecne ustalenie **nie blokuje** tego rozwoju.

---

## 10. Kto może użyć przedmiotu albo broni

**Twarde zasady (przykłady z rozmowy):**

- **Magia:** jeśli przedmiot **wymaga magii** do użycia, postać **bez zdolności magicznych** nie uruchomi tego efektu.
- **Broń i styl:** mag **nie musi** walczyć wielkim toporem jak wojownik — to **klimat i wybór gracza / fabuły**; **kusza** (strzał) jest **dozwolona** w przykładzie; **czy trafi** — rozstrzyga **rzut**, nie zakaz „jesteś magiem”.

*(Szczegóły: klasy w bazie, znaczniki „wymaga magii” w JSON — przy implementacji.)*

---

## Odnośnik

Pełny zapis decyzji: [`../04_decisions_log.md`](../04_decisions_log.md) (m.in. **[S1]**, **[S1b]**, **[S1c]**, **[S2]**, **[S3]**, **[S4]**, **[S4b]**, **[S5]**, **[S5a]**, **[S5b]**, **[S6]**, **[AUDIT]**).
