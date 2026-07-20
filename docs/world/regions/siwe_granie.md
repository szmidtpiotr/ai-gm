# SIWE GRANIE — rozdział krainy (baza wiedzy świata)

> **Status:** projekt zatwierdzony kierunkowo (dyskusja z Piotrem 2026-07-20). Rozdział rozwija LORE_v1_KANON.md (sekcja 3D) — kanon-parasol pozostaje nadrzędny. Elementy oznaczone **[PROPOZYCJA]** czekają na akceptację Piotra.
> Zasila: dział „Świat" wizytówki, narratora, seedowanie regionu `siwe_granie` (issue krainy w milestone Faza RM).

---

## 1. Charakter krainy

Surowa północ: granitowe pasma, wieczny śnieg, wymarłe kopalnie i wiatr, który niesie **stukanie**. Ojczyzna krasnoludów — dumna, okaleczona i pełna miejsc, o których nikt już nie mówi. Kraina rasy krasnoludzkiej (grywalna, #969) i jej startowy dom.

**Filar klimatu:** wszystko tu jest *starsze niż pamięć* — a to, co opuszczone, nie zawsze jest puste.

## 2. Historia (rozbudowa kanonu)

1. **Era hołdów.** Od Ery Latarni krasnoludzkie rody drążyły Granie: srebro, sól, żelazo. Sieć hołdów (osad rodowych) połączonych sztolniami i traktami grani. Stolica: **Kamienny Gród** pod Krzyżem Gór.
2. **Głębokie Bicie (20 lat temu).** Kopalnia Czarnego Hutmana dowierciła się do żyły Rdzenia. To, co się obudziło, nie wyszło na powierzchnię — ale **stuka**, a stukanie niesie się żyłami srebra po całym paśmie. Krasnoludy słyszą je w każdej kopalni, która sięga za głęboko.
3. **Exodus i Linia Soli.** Po ucieczce z Hutmana starszyzna rodów wyznaczyła **Linię Soli** — głębokość graniczną, poniżej której nie wolno kopać. Sól (obojętna na Rdzeń wg krasnoludzkiej tradycji górniczej) wyznacza granicę w sztolniach. Mniejsze hołdy porzucono; część rodów odeszła na Kresy i do stolicy Korony.
4. **Dziś.** Kamienny Gród trwa. Ród **Młotodzierżców** otwarcie mówi o powrocie i odbiciu Hutmana; starszyzna zakazuje. To główna oś napięcia krainy — i naturalny dylemat gracza-krasnoluda.

## 3. Trzy napięcia krainy

1. **Starszyzna vs Młotodzierżcy** — czekać, aż stukanie ucichnie, czy zejść i skończyć to, co się zaczęło?
2. **Pamięć vs przetrwanie** — opuszczone hołdy pełne dziedzictwa rodów; wracać po nie znaczy łamać zakazy.
3. **Góra vs lodowiec** — stary, niepisany zakaz wchodzenia na Lodowy Pas. Nikt nie pamięta, kto go wydał. **[PROPOZYCJA]** może oba zakazy (kopania w głąb i wchodzenia na lód) wydało dawno temu to samo — patrz §7.

## 4. Lokacje

### Zasiedlone

| Lokacja | Typ | Opis |
|---|---|---|
| **Kamienny Gród** | miasto-twierdza, **hub startowy krasnoluda** | Brama-most nad przepaścią, Wielka Kuźnia, Sala Rodów, targ, szynk „Pod Rdzawym Młotem". Struktura hub+sub-lokacje (#1212). |
| **Wyrobisko Srebrnej Żyły** | czynna kopalnia + wioska | Ekonomia srebra; questy „stukanie coraz głośniej"; kopalnia trzyma się NAD Linią Soli. |
| **Posterunek Linii Soli** | sztolnia graniczna | Wejście do zakazanej głębi; wartownicy rodowi; quest-gate. |
| **Siarkowe Pola** | obóz zbieraczy pod Czarnymi Skałami | Handel siarką, trujące opary (kondycje), geotermia. |
| **Gorące Źródła** | odpoczynek | Jedyne ciepłe miejsce w górach; odpoczynek, plotki, kąpielisko karawan. |
| **Karawanseraj na trakcie** | przystanek handlowy | Łącznik z Kresami; karawany, przemytnicy ze Starej Przełęczy. |

### Istniejące w DB (zostają)

Kopalnia Czarnego Hutmana (przeklęta, serce mitu) · Lodowy Pas / „Tron Białej Bogini" · Krzyż Gór · Czarne Skały · Przesmyk Wilczej Grani · Stara Przełęcz Przemytników.

### Miejsca opuszczone / zapomniane (pole do kampanii i historii)

| Lokacja | Opis |
|---|---|
| **Cmentarz Młotów** | Każdy młot wbity w lód = poległy w exodusie. Miejsce pamięci; nocą podobno któryś młot dzwoni. |
| **Echo-Wieża** | Krasnoludzki nasłuch stukania: rezonansowe dzwony w szybie. Ostatni obserwator odszedł; zapisy zostały. |
| **Wyssane Hołdy** | 3–4 porzucone osady rodowe z czasów exodusu, rozsiane po pasmie. Każda = mini-dungeon z historią jednego rodu. |
| **Zamarznięta Karawana** | Wraki wozów wmarznięte w lodową szczelinę. Co wieźli? Dlaczego jechali NA lodowiec, nie z niego? |
| **Kaplica Zapomnianego Rodu** | Ród wymazany z kronik Sali Rodów. Kaplica pamięta imię, którego nikt nie wypowiada. |
| **Sztolnia Umarłego Rodu** | Opuszczona kopalnia — farmowalny dungeon seed, tier niżej niż Hutman. |
| **Stacja Pradawnych** | Ruina starsza niż krasnoludzkie hołdy — Pradawni byli tu przed nimi. Nić do Martwych Pustkowi. |
| **Lodowa Brama** | Wmarznięte w lodowiec wrota. Nikt nie wie, co za nimi. Long-term mystery krainy — NIE otwieramy jej questem; ona czeka. |

## 5. Teren — plan różnicowania

Stan zastany: 84% mapy to mountain+snow (1293+839 z 2544 hexów), 6 lokacji. Cel: góry zostają dominantą, ale zyskują strukturę — doliny osadnicze, pas lasu na południowych stokach, strefy specjalne.

**Nowe typy terenu (nowe kafle — generacja FLUX .170):**
- `lodowiec` — Lodowy Pas; wyższy koszt marszu, brak obozowania, encounter pool lodowy
- `siarka` — pola siarkowe pod Czarnymi Skałami; opary = ryzyko kondycji, brak wody
- `las_iglasty` — świerkowy pas dolnych stoków południowych; łagodniejszy encounter pool

**Istniejące typy — redystrybucja:** doliny (hills/heath wokół osad), więcej jezior górskich, `grania` (44) zostaje jako grzbiety, przełęcze bez zmian.

## 6. Sól — materiał przeciw-Rdzeniowy **[PROPOZYCJA mechaniczna]**

Zasada fikcji: sól nie jest magiczna — jest **obojętna na Rdzeń** (izolator). Dlatego Linia Soli działa, dlatego górnicy noszą woreczek soli przy pasie. Przedmioty (wartości startowe, silnik effect_json/kondycji — bez nowego kodu koncepcyjnie):

| Przedmiot | Działanie | Koszt/limit |
|---|---|---|
| **Krąg soli** (consumable) | Rytuał: istoty z przecieku Rdzenia (nieumarli/demony — tag bestiariusza) nie wchodzą do ZWARCIA przez 3 rundy; przy obozie: bezpieczny odpoczynek w strefie skażonej | 1 użycie |
| **Solona klinga** (nałożenie na broń) | +1k4 obrażeń vs istoty Rdzenia | 1 walka |
| **Szczypta soli** (consumable, mag) | Następny miscast w tej walce złagodzony o 1 stopień | −1 do obrażeń czarów do końca walki (sól tłumi też własny kanał) |

Ekonomia: **sól = drugi towar eksportowy Grań** (obok srebra) — sztolnie solne dają regionowi tożsamość handlową i uzasadniają dostępność przedmiotów.

## 7. Biała Bogini — bez nowego ludu **[DO AKCEPTACJI — dwie opcje]**

Kanon trzyma Białą Boginię jako niedowiedzioną legendę. Żywy kult tubylców tworzyłby nowy lud — odrzucone. Alternatywy:

**Opcja A (rekomendowana): Zamarznięta Pielgrzymka.** Na Lodowym Pasie stoi opuszczone sanktuarium, a w lodzie wokół — zamarznięta procesja pielgrzymów sprzed pokoleń. Nikt nie wie, skąd przyszli ani czemu szli w górę. Sanktuarium jest puste — ale odśnieżone. Jedyny żywy: **ostatni strażnik-pustelnik** (człowiek, JEDEN NPC — żaden lud), który nie pamięta, kiedy przyszedł. Kult martwy, tajemnica żywa; idealnie wpisuje się w filar „miejsc zapomnianych".

**Opcja B: Wygnańcy Lodu.** Krasnoludzki ród wyklęty za złamanie zakazu lodowca, koczujący w tundrze — nie nowa rasa, to krasnoludy; żywa osada questowa i trzecia strona konfliktu rodów.

Opcje łączą się (B jako mała enklawa obok A), ale rekomendacja bazowa: **A** — mniejszy zakres, większy klimat.

---

*Rozdział = źródło prawdy lore krainy. Zmiany wyłącznie przez commit po dyskusji z Piotrem. Mapa regionu: `data/regions/region_siwe_granie.json` (git = prawda, DB = kopia robocza).*
