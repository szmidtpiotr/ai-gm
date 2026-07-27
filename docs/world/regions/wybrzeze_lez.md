# WYBRZEŻE ŁEZ — rozdział krainy (baza wiedzy świata)

> **Status:** ZATWIERDZONY (dyskusja z Piotrem 2026-07-20). Rozwija LORE_v1_KANON.md (sekcja 3E) i **istniejącą zawartość gry** — ta kraina ma najwięcej gotowego materiału po Kresach: 3 makro-lokacje, 12 sub-lokacji i 6 NPC już w bazie (bez hexów) + bogatą sekcję w wizytówce. Rasa: **wyspiarze** (#1476 — **WDROŻONA**, start w Czarnogrodzie).
> **WDROŻONE 2026-07-27 (WL-1…WL-11).** Konkretne liczby i decyzje as-built — patrz §11.
> Mapa: `data/regions/region_wybrzeze_lez.json` = surówka generatora (31% bagien, 5% morza — NIE jest ustaleniem). **Mapę budujemy OD ZERA** wg §5.

---

## 1. Charakter krainy

Morze jako żywioł i grób. Smoliste porty, czarne galery, kontrabanda, prawo Korony kończące się na linii przyboju. **Filar klimatu — najmocniejszy w świecie:** tutaj mrok **daje jeść**. Kresy: mrok pali wieś · Granie: mrok stuka · Czarnobór: mrok gasi · Pustkowia: mrok został po ludziach · **Wybrzeże: mrok karmi**. Najbardziej dwuznaczna moralnie kraina świata.

## 2. Zawartość zastana (NIE wymyślać od nowa)

**Makro-lokacje w DB:** `czarnogrod_port` (Czarnogród, tier 2, bezpieczny) · `zatoka_topielcow` (tier 3) · `wybrzeze_lez` (obszar, tier 3). Wszystkie **bez hexów** — czekają na mapę.

**Sub-lokacje w DB (12):** Czarnogród — Czarny Targ, Latarnia Topielców, Nabrzeże, Pod Topielcem · Zatoka — Rada Piracka, Karczma Kapitańska, Pirackie Doki, Jaskinie Skarbów · Wybrzeże — Jaskinia Przemytników, Latarnia Starego, Wraki, Świątynia Topielców.

**NPC w DB (6):** Dziadek Florian (quest-giver, Zatoka) · Kapitan Jacek Smolny (quest-giver, mapa klifów i wraków) · Ruda Magda (kowal, naprawia bez pytań) · Doktor Marcin Szkalpel (chirurg) · Wielki Borek (kowal Zatoki) · Halina Morska (uzdrowicielka).

**Z wizytówki (kanon):** Czarnogród ~8 000 mieszkańców (drugie miasto świata), władza nominalnie Korony, faktycznie kupców i przemytników · **Zatoka Topielców leży NA WYSPIE** — twierdza, ~5 000 zbrojnych, rządzi **Rada Piracka (pięciu kapitanów)**, handel niewolnikami · **Latarnia Topielców opuszczona, ale nocą zapala się sama i wciąga statki na rafy**.

**Kanoniczne haki:** kto stoi nocą na latarni z ogniem? · mapa Smolnego, na której komuś bardzo zależy · towar „z głębin" na Czarnym Targu · **zaginiony piąty kapitan Rady — fotel do wzięcia** · przeciekająca klątwa w Jaskiniach Skarbów (łupy wracają jako nieumarli) · Florian widział „coś dużego".

## 3. Historia i oś

- **Sól i sztorm.** Warzelnie na mieliznach dają **najtańszą sól świata** — gorszą od górskiej z Grań i od blizny Pustkowi. Trzy krainy = trzy klasy tego samego towaru (gradacja handlowa bez nowej ekonomii).
- **Sztorm Wieczny.** Dwa pokolenia temu sztormy na południu przestały ustępować. Ostatnie statki przywiozły **wyspiarzy**; żaden nie wrócił. Korona nazwała to pogodą; marynarze — czymś, co się obudziło. Ojczyzna wyspiarzy jest odcięta (patrz §7).
- **OŚ KRAINY: FOTEL JEST DO WZIĘCIA** (z kanonicznego haka). Rada Piracka ma cztery głosy i pustą piątą ławę. Korona wietrzy okazję, by wreszcie zdusić Zatokę; Czarnogród nie wie, na kogo postawić; kapitanowie ostrzą noże. **Gracz może ten fotel zająć.**
- **Głębia.** Świątynia Topielców (istnieje w DB) to morska odnoga kultów Rdzenia: pęknięcie leży pod dnem, a „coś dużego" Floriana jest jego mieszkańcem — być może Pradawnym, którego pochłonęło morze (kanon). Spina krainę z metafizyką świata bez nowej mitologii.

**Napięcia:** Korona vs Rada Piracka (Czarnogród = pole gry) · szabrownicy vs ci, co chcą zgasić latarnię · ląd vs Głębia (kult, towar „z głębin", zaginione statki).

## 4. Latarnia Topielców — dlaczego to serce krainy **[ZATWIERDZONE]**

Latarnia jest **silnikiem gospodarki, nie ozdobą**: zapala się sama → statki idą na rafy → morze wyrzuca ładunek → szabrownicy, wsie na palach i pół Czarnogrodu z tego żyją. Kraina karmi się własnym przekleństwem.

1. **Moralny dylemat bez złoczyńcy** (ostrzejsza wersja konfliktu drwali z Czarnoboru): zgasić latarnię = uratować statki i **zagłodzić trzy osady**. Nie ma złej strony, jest koszt.
2. **Uzasadnia mechanikę rejsów:** rejsy są ryzykowne, bo są rafy; rafy zbierają żniwo, bo latarnia kłamie. **Mapa Smolnego** staje się realnym kontrprzedmiotem.
3. **Obecna w każdej sesji, nie wymaga finału** — światło na horyzoncie widać z każdego nocnego hexa. Long mystery, który działa przez samą obecność.
4. **Węzeł czterech frakcji:** Korona traci statki i podatki (chce zgasić) · Rada Piracka zyskuje na chaosie · szabrownicy żyją z wraków · kult Topielców twierdzi, że to Głębia wzywa. Jeden obiekt, cztery interesy — każdy quest może się o niego oprzeć.
5. **Furtka na przyszłość:** gdyby kiedyś powstał „przełącznik świata", zgaszona latarnia = mniej wraków i łupów, bezpieczniejsze rejsy, uboższe wsie. Nie implementujemy — mit to umożliwia.

**ZAKAZ ROZSTRZYGANIA, kto ją zapala.** Każda odpowiedź (duch latarnika, kult, Głębia, piraci z pochodnią) jest słabsza od pytania. Narrator może sugerować różne wersje w różnych kampaniach; wybór jednej zamienia ducha krainy w przeciwnika do ubicia.

## 5. Mapa OD ZERA — układ

Bounding-box: q −55…−6, r 51…124. Północ = Koronne Niziny (rzeka z Portem Rzecznym = gotowa nić handlowa), wschód i południe = otwarte morze.

1. **Północny zachód — zaplecze lądowe:** trakt z Nizin, ujście rzeki, wsie rolniczo-rybackie, kępy lasu. Tędy wjeżdża gracz z Vilnogradu.
2. **Pas wybrzeża:** **Czarnogród przy ujściu rzeki** (port rzeczno-morski — stąd 8 tys. ludzi i cały handel), dalej klify i plaże wraków.
3. **Pas pływowy** — `plycizna`: zalewane mielizny, wsie na palach, warzelnie soli.
4. **Rafy** — `rafy`: pas grozy żeglarskiej przy latarni; obok Cmentarzysko Wraków.
5. **Morze** — `morze`: nieprzejezdne pieszo, przecinają je trasy rejsów.
6. **Wyspy:** **Zatoka Topielców** (duża wyspa-twierdza) + 2–3 wysepki: kryjówka przemytników, opuszczona latarnia, **wysepka diaspory wyspiarzy**.

**Nowe typy terenu (kafle FLUX .170):** `morze`, `plycizna`, `rafy`, `wydmy`.
**Budżet orientacyjny (2500 hexów):** morze ~700 · plycizna ~450 · plains/heath ~400 · forest ~250 · coast ~250 · rafy ~150 · wydmy ~120 · reszta: rzeka, drogi, wyspy, bagna przy ujściu.

## 6. Smaczki mechaniczne **[ZATWIERDZONE]**

| Element | Działanie |
|---|---|
| **Rejsy** (konieczne, nie opcjonalne) | Bez łodzi nie ma Zatoki = połowy contentu. Fast-travel z portu: koszt złota + czas + ryzyko (sztorm, rafy, piraci). Trasy: Czarnogród ↔ Port Łez ↔ Zatoka ↔ Port Rzeczny Vilnogradu. Używa silnika podróży — bez systemu statków. |
| **Pływy** | `plycizna` przejezdna przy odpływie, zabójcza przy przypływie (kto zostanie — traci HP / musi uciekać). Działa na istniejącym zegarze gry. |
| **Tabliczka pływów** | Przedmiot z portu: pokazuje, ile godzin do zmiany. Bez niej gracz zgaduje. |
| **Mapa Smolnego** | Kanoniczny hak jako przedmiot: mniejsze ryzyko rafy, otwiera trasy skrótowe. |
| **Kontrabanda** | Towar z Czarnego Targu drogi w Nizinach — ale glejty i rogatki (#1500) grają przeciw graczowi. **Szmugiel-loop między krainami.** |
| **Sól morska** | Najtańsza klasa soli (gradacja: Pustkowia > Granie > Wybrzeże). |

Przy implementacji: wpis do **Księgi Zasad** + **wizytówki** — standard fali.

## 7. Wyspiarze — lud bez domu **[ZATWIERDZONE]**

**Diaspora w Czarnogrodzie** (własna dzielnica portowa) + mała wysepka rodowa u brzegu. Ojczyzna leży za Sztormem Wiecznym — od dwóch pokoleń nikt stamtąd nie przypłynął ani tam nie dotarł.

**Wątek łączący krainy (decyzja Piotra):** wyspiarze rozeszli się po świecie jako najemnicy, przemytnicy i marynarze — spotkasz ich w porcie Vilnogradu, w Zatoce, w Obozie Gorączki na Pustkowiach. **Jedyna rasa obecna wszędzie** — bo jako jedyna nie ma dokąd wrócić. Kontrast: krasnolud ma góry, elf bór, Piętnowany pustkowie; wyspiarz ma tylko pokład.

**Imiona — brzmienie wyspiarsko-morskie** (styl wybrany przez Piotra): **Taio** (starszy diaspory), **Nakea** (kapitanka-przemytniczka), **Malua** (szefowa doków), **Ravu** (egzekutor Zatoki, zabijaka). Miejscowi zachowują nazewnictwo słowiańsko-germańskie (#997).

## 8. Hierarchia tajemnic **[ZATWIERDZONE]**

| Mit | Ranga | Zasada |
|---|---|---|
| **Głębia** | mit ŚWIATA | Pochłonięty Pradawny (kanon); nigdy nie otwierana kampanią krainy |
| **Kto zapala Latarnię Topielców** | long mystery krainy | §4 — zakaz rozstrzygania |
| **Zatoka Topielców / piąty fotel** | endgame krainy | Finał polityczny kampanii głównej |
| **Cmentarzysko Wraków** · **Jaskinie Skarbów** | farmowalne dungeony | Jaskinie: przeciekająca klątwa — łupy wracają jako nieumarli |

## 9. Obsada krainy

**Z bazy (6, tylko dopisać role):** Dziadek Florian · Kapitan Jacek Smolny · Ruda Magda · Doktor Marcin Szkalpel · Wielki Borek · Halina Morska.
**Do dodania:** **Kapitan Roggen** (Korona, blokada portu) · **Taio** (starszy diaspory wyspiarzy) · **Nakea** (kapitanka-przemytniczka) · opcjonalnie **Malua** / **Ravu**.

## 10. Start wyspiarza (#1476 WDROŻONE)

Whitelist: default **dzielnica diaspory w Czarnogrodzie** (`czarnogrod_dzielnica_wyspiarzy`); wariant: **Nabrzeże** (`czarnogrod_nabrzeze`). Haki startowe: pusty fotel w Radzie, blokada Korony (Roggen), Florian szuka śmiałka. Kotwica startowa NIE bramkuje wyboru rasy — wyspiarza można stworzyć wszędzie, ale kampania domyślnie zaczyna się „u swoich".

## 11. Stan wdrożenia — AS-BUILT (WL-1…WL-11, 2026-07-27)

> Sekcja opisowa: notuje **liczby startowe i decyzje faktycznie w grze** po fali WL. Wartości liczbowe są strojalne (Sandbox / patrz issue #1504–#1505); ta sekcja opisuje, nie definiuje — źródło prawdy silnika to kod i `game_config_*`.

**Mapa (WL-1…WL-3).** Kanon = `data/regions/region_wybrzeze_lez.json` — **2500 hexów**, bounds q −50…−1, r 51…124, status `coming`. Round-trip seed↔snapshot 1:1 (WL-11). Na hexach: **3 makro-lokacje** (Czarnogród `czarnogrod_port` q−19 r65 · obszar Wybrzeże `wybrzeze_lez` q−19 r75 · Zatoka `zatoka_topielcow` q−20 r102) + **10 etykiet-POI** (`latarnia_topielcow`, `warzelnie_solne`, `wsie_na_palach`, `osada_rybacka`, `osada_rolna`, `wybrzeze_lez_port`, `wysepka_diaspory`, `mokradla_ujscia`, `kryjowka_przemytnikow`, `opuszczona_latarnia`). Wyspy (Zatoka + wysepki) są **nieosiągalne lądem** — tylko rejsami.

**Tereny morskie (WL-1).** `morze` i `rafy` — **nieprzejezdne pieszo** (`is_passable=0`); `plycizna` przejezdna (2 h marszu, ale patrz pływy); `wydmy` przejezdne (1 h). Kafle-ilustracje w `frontend/images/terrain/`.

**Rejsy (WL-4).** Trasa **Czarnogród ↔ Zatoka Topielców: 40 gp / 8 h**, ryzyko „umiarkowane", rośnie nocą (rzut na zdarzenie: sztorm / rafa / piraci). **Mapa Smolnego** tłumi ryzyko rafy i otwiera skróty. Trasa do Portu Rzecznego Vilnogradu = **TODO WL-4b** (czeka na seed Koronnych Nizin).

**Pływy (WL-5).** Cykl **6 h → 2 pełne cykle na dobę**: **odpływ** 00:00–06:00 i 12:00–18:00, **przypływ** 06:00–12:00 i 18:00–24:00. `plycizna` przy przypływie: wejścia się blokuje; kto zostaje — łagodny wariant (drobne HP / przeniesienie na suchy hex). **Tabliczka pływów** (kupno u Nakei, port) = licznik godzin do zmiany.

**Loch bramkowany pływem (WL-5×WL-7).** **Cmentarzysko Wraków** (boss `utopiony_kapitan`) dostępne **tylko przy odpływie** — przy przypływie wejście zwraca „Przypływ zakrył dojście — wróć za ~N h". **Jaskinie Skarbów** (boss `straznik_klatwy`) bez bramki pływowej.

**Ekonomia (WL-8).** Drabina soli (kup u źródła → sprzedaj w Nizinach): **Wybrzeże `sol_morska` 2 → 6 gp** · Granie `sol_gorska` 5 → 14 · Pustkowia `sol_z_blizny` 9 → 24. Kontrabanda (`contraband=True`): **Perła z Głębin** 40 → 140 · **Żywica topielców** 20 → 80. Region popytu = **Koronne Niziny**; na wjeździe do Nizin gra **rogatka** (#1500): kontrola → konfiskata + kara reputacji, fałszywe papiery pomagają. Szmugiel-loop domknięty.

**Bestia i żywy świat (WL-7).** Nowi wrogowie: `bosman_herszt`, `topielec_morski`, `topielec_mielizny`, `nieumarly_marynarz`, `cos_z_sieci`, `glebinowy_pomiot`, `kultysta_glebi` (+ `bagienny_topielec`). **14 plotek** (`world_rumors`) — w tym „Latarnia zapala się sama" (utrzymany **zakaz rozstrzygania**, kto ją zapala — §4). Pule spotkań: porty bezpieczne, `plycizna` ryzykowna przy zmianie pływu, rafy/latarnia najgroźniejsze.

**Obsada (WL-6).** Dodani: `kapitan_roggen`, `taio_starszy`, `nakea_przemytniczka`, `malua_doki`, `ravu_egzekutor` (+ istniejący Florian, Smolny, Magda, Szkalpel, Borek, Halina).

---

*Rozdział = źródło prawdy lore krainy. Zmiany wyłącznie przez commit po dyskusji z Piotrem. Mapa budowana od zera — plik generatora traktować jako materiał do nadpisania, nie ustalenie.*
