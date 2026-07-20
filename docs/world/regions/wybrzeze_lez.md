# WYBRZEŻE ŁEZ — rozdział krainy (baza wiedzy świata)

> **Status:** ZATWIERDZONY (dyskusja z Piotrem 2026-07-20). Rozwija LORE_v1_KANON.md (sekcja 3E) i **istniejącą zawartość gry** — ta kraina ma najwięcej gotowego materiału po Kresach: 3 makro-lokacje, 12 sub-lokacji i 6 NPC już w bazie (bez hexów) + bogatą sekcję w wizytówce. Rasa: **wyspiarze** (#1476 — mechanika NIEwdrożona).
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

## 10. Start wyspiarza (po wdrożeniu #1476)

Whitelist: default **dzielnica diaspory w Czarnogrodzie**; wariant: Nabrzeże. Haki startowe: pusty fotel w Radzie, blokada Korony, Florian szuka śmiałka.

---

*Rozdział = źródło prawdy lore krainy. Zmiany wyłącznie przez commit po dyskusji z Piotrem. Mapa budowana od zera — plik generatora traktować jako materiał do nadpisania, nie ustalenie.*
