# KRESY — rozdział krainy (baza wiedzy świata)

> **Status:** OPISOWY. Mapa Kresów jest **ZAMKNIĘTA** (#1480) — ten rozdział **opisuje stan zastany**, nie projektuje zmian. Rozwija LORE_v1_KANON.md (sekcja 3B); kanon-parasol pozostaje nadrzędny.
> Zasila: dział „Świat" wizytówki (`frontend/showcase/swiat.html`, sekcja `#kraina-kresy`), narratora, Księgę Zasad (rozdział XI), kampanie krainy #1497 / #1498.
> Wszystkie lokacje i NPC poniżej **wyciągnięte zapytaniem z DEV DB (2026-07-20)** — nic nie wymyślono. Issue: #1503, fala seedowania: #1483.

---

## 1. Charakter krainy

Wschodnia marchia Korony: trakt, wsie, jedna twierdza i las, który zaczyna się tuż za ostatnią chatą. Kresy to kraina **zwykłych ludzi na granicy mroku** — nie bohaterów, tylko tych, którzy chcieliby dożyć żniw. Tutaj większość historii świata się zaczyna: drobne zlecenie (zaginiony drwal, dziwne stukanie w sztolni, spalona wieś) ma paskudny zwyczaj urastania do czegoś znacznie większego.

**Filar klimatu:** *prawo Korony sięga tak daleko, jak miecz najbliższego człowieka* — a najbliższy człowiek to zwykle ty.

**Rola w grze:** kraina **startowa i wzorcowa** — pierwszy kontakt gracza ze światem, z Księgą Zasad i z mechaniką podróży. Dziś **jedyna kraina startowa człowieka** (docelowo losowanie Kresy / Vilnograd — #1500/#1501). Krasnolud startuje w Siwych Graniach (#969).

## 2. Historia (rozbudowa kanonu)

1. **Dwieście lat straży.** Strzegwacht stoi na trakcie od dwóch stuleci — postawiony, gdy Korona jeszcze wierzyła, że granicę da się zamknąć murem. Wokół twierdzy narosły wsie: drwale, górnicy, poborcy, karczmy przy rozstajach. Pogranicze żyło z traktu i z żołdu garnizonu.
2. **Zmierzch Latarni.** Imperium słabnie: podatki rosną, garnizony się kurczą, granica cofa się w sposób, którego nikt oficjalnie nie ogłasza. Kresy odczuwają to najprościej — jest mniej patroli, a te, które wychodzą, nie zawsze wracają.
3. **Zgliszcza (rok temu).** Wieś spłonęła w jedną noc; zginęło czterdzieści jeden osób. Nikt z Korony nie odpowiedział, nikt nie prowadził śledztwa. Ocalali (~30) obozują na pogorzelisku, bo nie mają dokąd pójść. **Co spaliło Zgliszcza — nie jest rozstrzygnięte w tym rozdziale**: to zagadka kampanii głównej (#1497) i wizytówka jej nie zdradza.
4. **Dziś.** Sołtysi nie piszą już do króla — czekają na kogoś takiego jak bohater. Z gór (Siwe Granie) pełznie w dół rzeki mrok wypierający dawne rody kowali; z Boru Zmarłych (Czarnobór) przestają wracać drwale; ze wschodu przychodzą wieści, że barbarzyńcy nie tyle napierają, co **uciekają przed czymś**.

## 3. Trzy napięcia krainy

1. **Korona vs pogranicze** — twierdza jest, ale garnizon się kurczy, a rozkazy przychodzą z Vilnogradu, gdzie nikt Kresów nie widział. Czy pogranicze istnieje bez Korony? (oś kampanii #1498)
2. **Prawda vs spokój** — Zgliszcza pokazały, że milczenie bywa tańsze niż śledztwo. Kto pyta za głośno, ten zwykle znika. (oś kampanii #1497)
3. **Las vs wieś** — granica cywilizacji jest tu dosłowna: linia ostatniego pola. Bór Zmarłych oddaje nocą swoich zmarłych, a wsie odpowiadają kapliczkami, zaklęciami i siekierami.

## 4. Lokacje — katalog z DB

Stan DEV DB (2026-07-20): **8 lokacji makro** + **23 czynne sub-lokacje** oznaczone jako kanoniczne, w regionie `kresy`. Poza nimi w tabeli leży osad roboczy z sesji testowych i generacji AI (Wilczburg, Kamionka, Rudnik, Borowiec, Błotstein, Czarnstein i in.) — **nie są kanonem krainy** i nie wchodzą do wizytówki ani do kampanii.

### Lokacje makro (kanoniczne)

| Lokacja (etykieta w DB) | Klucz | Typ | Tier | Hex | Odpoczynek |
|---|---|---|---|---|---|
| **Strzegwacht, Twierdza Graniczna** | `strazyn` | garrison | 3 | 33,6 | tak |
| **Wolfsmark, Wioska Górnicza** | `wolanka` | mining-village | 2 | 21,1 | tak |
| **Zgliszcza, Spalona Wieś** | `zgliszcza` | burned-village | 2 | 37,18 | nie |
| **Most Czarnej Rzeki** | `most_czarnej_rzeki` | bridge-town | 2 | 0,7 | tak |
| **Karczma Pod Trzema Krukami** | `trzech_krukow` | wayside-inn | 2 | 0,6 | tak |
| **Birkenwald, Wioska Drwali** | `brzezino` | lumber-village | 1 | 39,9 | tak |
| **Cieszburg** | `cieszowice` | village | 1 | 13,22 | tak |
| **Pustelnia Świętego Marcina** | `pustelnia_marcina` | hermitage | 1 | 0,5 | tak |

> **Uwaga o kluczach:** klucze techniczne pochodzą sprzed rename'u #997 (`strazyn`, `brzezino`, `wolanka`, `cieszowice`). **Nazwą kanoniczną jest etykieta**, nie klucz. Kluczy nie zmieniamy — trzymają je hexy, questy, plany kampanii i zapisane sesje.

### Sub-lokacje (wnętrza — struktura hub+sub, #1212)

| Hub | Sub-lokacje czynne |
|---|---|
| Strzegwacht | Koszary · Kantyna Żołnierska · Lazaret · Wieża Strażacka |
| Wolfsmark | Kopalnia Główna · Szynk Górniczy · Kuźnia Wujka · Kościół Św. Floriana |
| Zgliszcza | Obozowisko Ocalałych · Wypalony Kościół · Masowy Grób |
| Most Czarnej Rzeki | Wartownia Mostu · Komora Celna · Karczma „Pod Lipinkami" |
| Pod Trzema Krukami | Wielka Izba · Pokoje · Stajnia |
| Birkenwald | Dom Starszego · Tartak Starego Jerzego · Święta Polanka |
| Pustelnia Św. Marcina | Kapliczka Leśna · Ogród Ziołowy · Święte Źródło |
| Cieszburg | *(brak czynnych — Karczma Pod Lipą, Stara Studnia i Pola Łubków są w DB, ale nieaktywne)* |

### Lokacja startowa

**Gospoda „Pod Złamanym Rogiem"** (`gospoda_pod_zlamanym_rogiem`, hex **24,13**) — próg większości historii świata. Od #1524 stoi w kanonie treści: makro `wayside-inn` + trzy wnętrza (Izba Szynkowa, Pokoje Na Górze, Stajnia), gospodyni **Hanka Rogowa** (`karczmarka_zlamany_rog`) w izbie szynkowej. Stary runtime'owy rekord `gospoda_pod_z_amanym_rogiem` (hex 0,22) został odłożony jako `discarded`. Marta karczmarka gra dalej w Karczmie Pod Trzema Krukami (pokoje kupców) — używa jej szablon „Pierwsze Kroki".

## 5. Obsada — NPC z DB

Wszyscy poniżej **istnieją w tabeli `npcs`** i są podpięci do lokacji Kresów.

| NPC | Rola | Miejsce |
|---|---|---|
| **Komendant Bożena Groźna** | quest-giver; dowódczyni twierdzy, zleca zwiad za granicę | Strzegwacht |
| **Kuźnik Władysław** | kowal-kupiec, oręż wojskowy | Strzegwacht |
| **Felczer Ryszard** | medyk; leczenie brutalne, ale skuteczne | Strzegwacht |
| **Faktor Gildii — Bruno Miech** | gildia kupiecka (#1345) | Strzegwacht |
| **Starszy Konrad** | quest-giver; zna korytarze Czarnego Hutmana | Wolfsmark |
| **Grubas Miron** | kowal-kupiec | Wolfsmark |
| **Zofia Górska** | zielarka, górskie zioła i kamienie lecznicze | Wolfsmark |
| **Sołtys Benedykt** | quest-giver; traci drwali w Borze Zmarłych | Birkenwald |
| **Zielarka Agata** | zioła i trucizny ze skraju Boru | Birkenwald |
| **Stary Paweł Kowal** | kowal-kupiec | Birkenwald |
| **Faktor Gildii — Kunegunda Rączka** | gildia kupiecka | Birkenwald |
| **Stary Jerzy z tartaku** | plotkarz; słyszy rąbanie w borze nocą | Birkenwald: Tartak |
| **Sołtys Wiktor** | quest-giver; „coś niepokoi wioskę" | Cieszburg |
| **Babcia Marta** | znachorka; zaklęcia działają *za dobrze* | Cieszburg |
| **Józef Bednarz-Kowal** | kowal-kupiec | Cieszburg |
| **Bartek, karczmarz Pod Lipą** | karczmarz, miód pitny | Cieszburg (karczma nieaktywna) |
| **Bartłomiej Kruk** | quest-giver + kupiec; żywy spis pogranicza | Pod Trzema Krukami |
| **Marta, karczmarka** | karczmarka; plotki i pierwsze schronienie | Pod Trzema Krukami |
| **Pius, celnik** | myto, przemyt, rejestry przejazdów | Most Czarnej Rzeki / Komora Celna |
| **Lipka, karczmarz Pod Lipinkami** | karczmarz, gulasz rybny dzień i noc | Most: Pod Lipinkami |
| **Pustelnik Marcin** | quest-giver; jedyny duchowny na odludziu | Pustelnia Św. Marcina |
| **Tobiasz, ocalały ze Zgliszcz** | quest-giver; twarz katastrofy sprzed roku | Zgliszcza / Obozowisko |

**Weryfikacja postaci z kanonu:**
- **Mizel** — nie jest NPC-em w DB. To bohater-wzorzec z otwarcia gry (świat złodziejski, „człowiek z sygnetem"), obecny w prompcie systemowym i Księdze Zasad, nie w tabeli `npcs`. Kresy dziedziczą po nim motyw sygnetu (haki u Kruka i u Marty).
- **Kapitan Henryk Miecław** — istnieje w DB, ale stoi w **Vilnogradzie** (Koronne Niziny), nie na Kresach. W kampanii #1497 działa zdalnie (odradza śledztwo, bo dostał rozkaz z góry).
- **Komendant Groźna** — jedyna z „ikon" kanonu faktycznie osadzona na Kresach.

## 6. Teren — jak wygląda kraina

Kresy to **2493 hexy** overworldu (`world_hexes`, `map_level=0`, `region='kresy'`) — największa i jedyna w pełni zaludniona mapa świata. **18 typów terenu**, rozkład (liczba hexów):

| Typ | Hexy | Marsz (h/hex) | Bazowa szansa spotkania |
|---|---|---|---|
| Równiny `plains` | 543 | 1,0 | 15% |
| Las `forest` | 406 | 2,0 | 30% |
| Wrzosowisko `heath` | 382 | 1,0 | 20% |
| Rzeka `river` | 231 | — (nieprzekraczalna wprost) | 10% |
| Droga `road` | 206 | 0,5 | 5% |
| Bagno `swamp` | 137 | 4,0 | 40% |
| Śnieg `snow` | 133 | 1,5 | 15% |
| Morze `sea` | 113 | — (nieprzekraczalne) | 10% |
| Wzgórza `hills` | 88 | 2,0 | 20% |
| Wybrzeże `coast` | 85 | 1,0 | 15% |
| Góra `mountain` | 81 | 2,0 | 25% |
| Tundra `tundra` | 42 | 1,5 | 25% |
| Wioska `village` | 15 | 0 | 0% |
| Bród `brod` | 11 | 1,5 | 10% |
| Jezioro `lake` | 10 | — | 5% |
| Most `bridge` | 8 | 1,0 | 45% |
| Miasto `town` | 1 | 0 | 0% |
| Ruiny `ruins` | 1 | 1,0 | 60% |

*(wartości z `hex_type_config` — startowe, edytowalne w admin → Mapa → Konfiguracja terenu, per Numbers Policy #1118)*

**Jak to czytać jako krajobraz:** rdzeń krainy to **równiny i wrzosowiska** pocięte **traktem** (206 hexów drogi — najgęstsza sieć w świecie) i **rzekami** (231 hexów, przekraczalne tylko przez 8 mostów i 11 brodów — stąd strategiczna waga Mostu Czarnej Rzeki). Na wschód i północ ciągnie się **las** (406 hexów) przechodzący w Bór Zmarłych; na południu i w kotlinach — **bagna**, najdroższy teren w grze (4 h/hex, 40% spotkań). Północno-zachodni skraj zahacza o **góry, śnieg i tundrę** — to podnóża Siwych Grani. Zachodnia krawędź to **wybrzeże i morze** — okno na Wybrzeże Łez. Jedno **miasto**, 15 **wiosek**, jedne **ruiny**.

**Konsekwencja mechaniczna dla gracza:** na Kresach opłaca się trzymać traktu (0,5 h/hex, 5% spotkań) i unikać bagien (8× drożej, 8× groźniej). To pierwsza lekcja podróży w grze — dlatego trafia do Księgi Zasad (rozdz. XI).

## 7. Nazewnictwo — po rename'ie #997

Kresy trzymają MIX słowiańsko-germański (konwencja świata, nie realna polszczyzna):

| Dziś kanonicznie | Dawniej (do wyczyszczenia w tekstach) |
|---|---|
| **Strzegwacht** | Strażyn |
| **Birkenwald** | Brzezino |
| **Wolfsmark** | Wolanka |
| **Cieszburg** | Cieszowice |

Bez zmian: Most Czarnej Rzeki · Zgliszcza · Karczma Pod Trzema Krukami · Pustelnia Świętego Marcina · Gospoda „Pod Złamanym Rogiem".

> **Dług techniczny (nie ruszany w tym issue):** etykiety sub-lokacji w DB nadal używają starych nazw („Strażyn: Koszary", „Wolanka: Szynk Górniczy", „Brzezino: Tartak"). Zmiana wymaga migracji na lokacjach — mapa jest zamknięta, więc czeka na osobną decyzję.

## 8. Start bohatera-człowieka

- **Dziś:** człowiek zaczyna na Kresach. Domyślny próg: gospoda **„Pod Złamanym Rogiem"**; realne starty planów LLM lądują też w Cieszburgu, u Trzech Kruków i w Strzegwachcie (silnik: `template_start_anchor.py` — szablon dostaje start-hex, plan osadza lokację z whitelisty).
- **Docelowo:** losowanie krainy startowej **Kresy / Vilnograd** dla człowieka (#1500 / #1501). Rozdział tego nie wdraża.
- **Pierwsze haki:** Marta ma robotę „akurat dla kogoś takiego jak ty"; Bartłomiej Kruk sprzedaje wieści za piwo; sołtys Benedykt płaci za odnalezienie drwali.

## 9. Kampanie krainy

- **#1497 „Popiół ze Zgliszcz"** (główna, dla ludzi) — śledztwo: ocalały ze Zgliszcz, rejestry myta z Mostu, sygnet bez herbu. Stawka: wieś, prawda i cena obu. **Rozwiązanie zagadki jest spoilerem — nie trafia ani do wizytówki, ani do Księgi.**
- **#1498 „Ostatnia Warta"** (druga, na później) — Strzegwacht dostaje rozkaz wycofania po 200 latach; gracz próbuje utrzymać granicę bez Korony. Rym z „Wycofaniem" z Martwych Pustkowi (#1496).

Obie używają **wyłącznie istniejących lokacji** — mapa Kresów zamknięta.

---

*Rozdział = źródło prawdy lore krainy (opis stanu, nie projekt). Zmiany wyłącznie przez commit po dyskusji z Piotrem. Mapa regionu: `docs/world/world_map_seed.json` (git = prawda, DB = kopia robocza).*
