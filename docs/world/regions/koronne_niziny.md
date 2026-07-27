# KORONNE NIZINY — rozdział krainy (baza wiedzy świata)

> **Status:** ZATWIERDZONY (dyskusja z Piotrem 2026-07-20; styl imion §7 zaakceptowany). Rozwija LORE_v1_KANON.md (sekcja 3A). **Kraina neutralna — bez rasy rodowej**; cel „późnej fazy" kampanii wszystkich ras.
> Osobliwość startowa: człowiek dostaje LOSOWY start Kresy/Vilnograd (§8).

---

## 1. Charakter krainy

Rdzeń cywilizacji: porządek, handel, podatki, intrygi. Najbezpieczniej w świecie — i najwięcej noży w plecach. **Filar klimatu:** mrok tej krainy nie ma kłów — ma pieczęcie, weksle i uśmiech. Wszystko tu działa; pytanie tylko, dla kogo.

## 2. Funkcja w grze **[ZATWIERDZONE]**

**Cywilizacyjny sufit gry** — cel późnej fazy każdej kampanii:
1. **Vilnograd** — największe miasto gry (hub-gigant, dzielnice jako sub-lokacje).
2. **Handel najwyższego tieru** — wszystkie szlaki schodzą się w Volhynii (4 trakty); najlepszy asortyment, sufit ekonomii.
3. **Frakcje i reputacja** — per-frakcja (#1103) gra tu pierwsze skrzypce.
4. **Usługi Światła** — Klasztor Iskry: leczenie, błogosławieństwa, odklinanie; skup reliktów Brata Tomasza (łącznik z Martwymi Pustkowiami).

## 3. Historia i oś **[ZATWIERDZONE]**

Era Latarni wzniosła Vilnograd jako latarnię porządku. Dziś, w Zmierzchu Latarni, latarnia świeci na kredyt.

**Oś krainy — PEŁZAJĄCY ZAMACH.** Rada Czterech nie planuje przewrotu — ona go *kupuje, ratami*: weksle na żołd, długi twierdz granicznych, kupione rozkazy. **Rozkaz wycofania Strzegwachtu („Ostatnia Warta" #1498) i spalenie Zgliszcz (#1497) mogą być ratami tego samego zamachu** — kampanie Kresów i Nizin łączą się w jeden meta-wątek polityczny.

**Napięcia:** (1) Korona vs Rada — jawna władza vs pieniądz; (2) Światło vs kulty W SALONACH — kult nie w ruinach, a w skórze gildii; (3) stolica vs prowincja — spichlerz biednieje, by miasto błyszczało (bunt chłopski jako tło).

## 4. Lokacje

### Zasiedlone

| Lokacja | Typ | Opis |
|---|---|---|
| **Vilnograd** | stolica, hub-gigant | Suby-dzielnice: Zamek Królewski, Dzielnica Gildii, Dzielnica Złodziei (świat Mizela), Katedra Światła, Targ Wielki, Enklawa Krasnoludzka (kantory), Port Rzeczny. |
| **Volhynia** | miasto kupieckie | Skrzyżowanie 4 traktów; aukcje, karawany. |
| **Klasztor Iskry** | centrum Światła | Matka Urszula, Brat Kazimierz (uzdrowiciel), Brat Tomasz Kronikarz. |
| **Wsie spichlerzowe** (2-3) | folwarki, młyny | Prowincja, która karmi stolicę — i biednieje. |
| **Rogatka Wschodnia** | komora celna | Trakt z Kresów; glejty, myto, kontrola papierów. |

### Miejsca opuszczone / zapomniane

| Lokacja | Opis |
|---|---|
| **Pierwszy Tron** | Ruiny pierwotnej siedziby Korony z początku Ery Latarni. Dwór przeniesiono nagle; kroniki milczą, dlaczego. |
| **Zatopione Opactwo** | Klasztor zalany przy budowie stawów młyńskich. Światło nie tłumaczy, czemu opuszczono go tak szybko. |
| **Dwór Czwartego** | Spalona rezydencja rzekomego założyciela Rady. Nikt nie kupuje tej ziemi — od pokoleń. |
| **Szubieniczne Wzgórze** | Miejsce straceń Korony; cicho nawiedzone. |
| **Wieża Heroldów** | Opuszczone archiwum rodowodów. Kto NAPRAWDĘ ma prawo do tronu? |
| **Katakumby Vilnogradu** | Krypty, tunele przemytników i fundamenty starsze niż miasto — **miejski farmowalny dungeon**. |

### Hierarchia tajemnic **[ZATWIERDZONE]**

| Mit | Ranga | Zasada |
|---|---|---|
| **Sekret Rady Czterech** | mit polityczny ŚWIATA (kanon: „główny hak intrygi") | Kampania może dotknąć JEDNEGO agenta/członka — nigdy całej Rady; pełny skład i cel nigdy nieujawnione |
| **Pierwszy Tron** | long mystery krainy | Czemu przeniesiono dwór — nie otwiera tego quest |
| **Dwór Czwartego** | endgame krainy | Fabularny finał kampanii intryg |
| **Katakumby Vilnogradu** | farmowalny dungeon | Otwarte od seedu |

## 5. Teren **[ZATWIERDZONE]**

**Budowa od zera** — plik seedu ma 2 hexy (nie ma siatki; jedyna taka kraina). Charakter: odwrotność Pustkowi — drogi są wszędzie.

- Nowy typ + kafel (FLUX .170): **`pola_uprawne`** (złote łany — tożsamość spichlerza).
- Duża rzeka przez Vilnograd (Port Rzeczny) — naturalne połączenie z Wybrzeżem Łez na południu.
- Gęsta sieć traktów: 4 trakty Volhynii (do Kresów, ku Wybrzeżu, do Vilnogradu, trakt zachodni), rogatki na granicach.
- Reszta z istniejących typów (plains/heath/forest/river/village/town/bridge/road).
- Porządek przy seedzie: wchłonąć istniejący hex DB „Targowa Wola"→`vilnograd_stolica` (relikt #1305; nazwa do poprawy).

## 6. Smaczki mechaniczne **[ZATWIERDZONE]** — mrok ma pieczęcie

| Przedmiot | Działanie |
|---|---|
| **Glejt kupiecki** | Niższe myto i lepsze ceny na rogatkach/targach (dokument w ekwipunku). |
| **List żelazny** | Przejście przez rogatki i posterunki bez pytań. |
| **Fałszywe papiery** | Wersja dla łotrzyka — działa jak glejt/list, ale kontrola = test i ryzyko. |
| **Weksel kantorów** | Zamiana złota na papier wymienialny w kantorach enklawy — bezpieczny transport majątku (kradzież/śmierć nie zabiera weksla). |

Enklawa krasnoludzka awansuje z lore (🔵) do gry: kantory, jubilerstwo, weksle. Przy implementacji: wpis do **Księgi Zasad** + **wizytówki** — standard fali.

## 7. Obsada krainy — NPC-ikony **[ZATWIERDZONE]**

Reguły stylu (poprawione po uwadze Piotra): **dwór i stolica** = archaiczno-dworskie słowiańskie (jak kanoniczne Vilnograd/Volhynia); **półświatek** = pseudonimy-urzędy, nie ksywki; **krasnoludy** = wzór Grań (nordyckie imię + polski przydomek); **prowincja zachodnia** = germańskie/hybrydy (#997). Kanoniczni NPC bez zmian.

| NPC | Rola | Uwagi |
|---|---|---|
| **Brat Aleksy Złotnik** | gildmistrz | kanon |
| **Matka Urszula** | przeorysza Klasztoru Iskry | kanon |
| **Brat Tomasz Kronikarz** | skup reliktów | kanon; łącznik z Pustkowiami |
| **Kanclerz Dobrogost** | twarz Korony | dworskie słowiańskie (zamiast „Werner") |
| **„Rachmistrzyni"** | pośredniczka Rady | pseudonim-urząd: prowadzi rachunki Rady, przyjmuje raz w tygodniu; imienia nie zna nikt (zamiast „Pani Wtorkowa") |
| **„Nocny Burmistrz"** | władca dzielnicy złodziei | pseudonim-urząd; smaczek: może to urząd przechodni, nie człowiek (zamiast „Sowa") |
| **Gundrik Złota Waga** | bankier enklawy krasnoludzkiej | wzór przydomków z Grań |
| **Berta Twarda Pieczęć** | celniczka, Rogatka Wschodnia | hybryda: germańskie imię + polski przydomek |

## 8. Start — osobliwość krainy **[ZATWIERDZONE]**

**Człowiek dostaje LOSOWY start: Kresy („Pod Złamanym Rogiem") albo Vilnograd (Dzielnica Złodziei / zajazd przy Targu Wielkim)** — ciekawostka dla gracza; kampania od pierwszej sceny może potoczyć się inaczej (pogranicze vs miasto intryg). Zgodne z kanonem: ludzki łotrzyk wyrasta z dzielnicy złodziei stolicy.

- Implementacja: whitelist startowa człowieka = [Kresy-default, Vilnograd] z losowaniem w planie (silnik `template_start_anchor.py` + wzorzec whitelisty per rasa z SG-8/CB-8/MP-8).
- **Aktywacja losowania DOPIERO po zaseedowaniu Vilnogradu** — do tego czasu człowiek startuje na Kresach jak dziś.
- Pozostałe rasy: bez zmian (kraina rodowa).

---

## 9. Stan wdrożenia — domknięcie KN-11 (doprecyzowania)

> Sekcja faktograficzna: co realnie siedzi w seedzie po sesjach KN-1…KN-9 + KN-LORE. Kanon (sekcje 1-8) bez zmian. Dodane przy zamknięciu krainy (KN-11).

- **Mapa:** `data/regions/region_koronne_niziny.json` — **2500 heksów** (siatka wygenerowana OD ZERA, KN-2/KN-3; placeholder 2-hex już nieaktualny). Round-trip seed↔snapshot zweryfikowany **1:1** na kopii DB. Status pliku = `coming` do czasu ręcznego przełączenia na `live` przez Piotra po weryfikacji na DEV.
- **Wiązania heks→lokacja:** 13 heksów z `location_key` (m.in. `vilnograd_stolica` @ q=-23,r=22, typ `city` — wchłonięty relikt „Targowa Wola" #1305; `katakumby_vilnogradu`, `volhynia_kupiecka`, `klasztor_iskry_centrum`, `rogatka_wschodnia` + miejsca zapomniane).
- **Lokacje (`game_locations`, region=koronne_niziny):** 43 wpisy. Vilnograd = hub-gigant z **10 dzielnicami-subami** (Targ Wielki, Dzielnica Gildii, Dzielnica Złodziei, Enklawa Krasnoludzka, Katedra Światła, Port Rzeczny, Zamek Królewski, Kuźnia, Tawerna Pod Złotą Koroną). Volhynia = 8 subów (w tym Kantor, Plac Aukcyjny). Klasztor Iskry = 4 suby. Rogatka Wschodnia = Izba Celna + Posterunek. Wsie: Mühlfeld, Kornbrück, Ährenau (folwarki/młyn/karczmy). Miejsca zapomniane: Pierwszy Tron, Dwór Czwartego, Wieża Heroldów, Szubieniczne Wzgórze, Zatopione Opactwo.
- **Smaczki-papiery:** `glejt_kupiecki` (60 zł), `list_zelazny` (120 zł), `falszywe_papiery` (40 zł) — jako wpisy w `game_items` (reprodukowalne skryptem `scripts/seed_vilnograd_obsada.py`, poza zestawem `CONTENT_TABLES`). **Weksel** = mechanika kantoru (złoto→papier) w Enklawie Krasnoludzkiej / Volhynia Kantor.
- **Bestia i świat:** 14 wrogów (`region_tag=koronne_niziny`) + pule spotkań; **15 plotek** (`world_rumors`, region=koronne_niziny) niosących oś „pełzającego zamachu" (Rachmistrzyni, Nocny Burmistrz, latarnia na kredyt). Dungeon miejski: `game_dungeons` key `katakumby_vilnogradu`.
- **Frakcje:** `korona_vilnograd`, `gildie_vilnogradu`, `enklawa_krasnoludzka`, `swiatlo_iskry`.
- **Usługi Światła (Klasztor):** `blessing_light`, `curse_removal`, `healer_light`, `healer_heavy`.
- **Start człowieka (KN-9):** losowanie Kresy/Vilnograd aktywne (draw w `sheet_json.kn9_start`), bramkowane zaseedowaniem Vilnogradu.

---

*Rozdział = źródło prawdy lore krainy. Zmiany wyłącznie przez commit po dyskusji z Piotrem. Mapa: `data/regions/region_koronne_niziny.json` (2500 heksów, seed OD ZERA; snapshot: `scripts/snapshot_world_map.py --region koronne_niziny`).*
