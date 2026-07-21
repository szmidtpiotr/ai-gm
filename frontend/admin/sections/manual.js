/**
 * Sekcja „Instrukcja" — podręcznik administratora gry (#1407).
 *
 * Living document: treść pogrupowana wg GŁÓWNYCH zakładek panelu (GRUPY[] —
 * ikona+nazwa 1:1 z nawigacją w index.html), w każdej grupie rozdziały.
 * Spis treści generowany automatycznie. Konwencja treści:
 *  - nazwy sekcji / zakładek / przycisków DOKŁADNIE jak w UI (kopiuj z kodu,
 *    razem z emoji) — admin nie może zgadywać, o który przycisk chodzi;
 *  - żadnych wzmianek o historii prac / commitach / issue — to manual, nie
 *    changelog;
 *  - nowa funkcjonalność w adminie ⇒ dopisz/zmień rozdział w tej grupie,
 *    której zakładki dotyczy.
 */

const STUB = `<p style="color:var(--t3)">Rozdział w przygotowaniu.</p>`;

const GRUPY = [
  {
    ico: '🧭', label: 'Wstęp',
    chapters: [
      {
        id: 'wstep',
        title: 'Jak korzystać z instrukcji',
        body: `
<p>Ten podręcznik opisuje, jak zarządzać światem gry z poziomu panelu administratora.
Treść jest pogrupowana według głównych zakładek panelu (lewa nawigacja): <b>Gracze</b>,
<b>Kampanie</b>, <b>Mapa</b> itd. Wszystkie nazwy sekcji, zakładek i przycisków są pisane
<b>dokładnie tak, jak w panelu</b> (razem z ikonami), np. przycisk <b>★ Kanon</b>
w zakładce <b>Do zatwierdzenia</b> sekcji <b>Mapa</b>.</p>
<p>Rozdziały są niezależne — czytaj ten, którego potrzebujesz. Spis treści po lewej.</p>`,
      },
      {
        id: 'wyszukiwarka',
        title: 'Szukaj funkcji (wyszukiwarka)',
        body: `
<p>Nie musisz pamiętać, w której zakładce jest dana funkcja. Na górze lewej nawigacji jest pole
<b>🔍 Szukaj funkcji…</b> — otwierasz je kliknięciem albo skrótem <b>Ctrl + K</b> (na Macu ⌘ K).</p>
<p>Wpisz nazwę tego, czego szukasz (np. <b>tabele łupów</b>, <b>presety LLM</b>, <b>kostki</b>,
<b>portret wroga</b>). W miarę pisania pojawia się lista wyników — każdy z krótkim opisem i etykietą
zakładki, w której się znajduje. Kliknij wynik (lub wybierz strzałkami ↑↓ i wciśnij ↵), a panel
<b>przeniesie Cię prosto do tej zakładki</b> — jeśli funkcja siedzi w podzakładce, otworzy się od razu
ta podzakładka.</p>
<p>Wyszukiwarka rozumie pisownię bez polskich znaków i odmiany (np. <b>lupy</b> znajdzie
<b>Tabele łupów</b>). Kilka funkcji (np. Plan GM konkretnej kampanii, LLM konkretnego gracza) wymaga
wcześniejszego wybrania kampanii/gracza — wtedy wynik przenosi Cię do właściwej sekcji, a resztę
wybierasz już na miejscu.</p>`,
      },
    ],
  },
  { ico: '▦', label: 'Przegląd',  chapters: [{ id: 'przeglad',  title: 'Pulpit i statystyki', body: STUB }] },
  { ico: '◉', label: 'Gracze',    chapters: [{ id: 'gracze',    title: 'Konta graczy i ustawienia LLM', body: STUB }] },
  { ico: '⛺', label: 'Kampanie',  chapters: [{ id: 'kampanie',  title: 'Monitor kampanii i Plan GM', body: STUB }] },
  { ico: '🧍', label: 'Bohaterowie', chapters: [{ id: 'bohaterowie', title: 'Zarządzanie bohaterami', body: STUB }] },
  { ico: '⚔', label: 'Przedmioty', chapters: [{ id: 'przedmioty', title: 'Bronie, przedmioty i tabele łupów', body: STUB }] },
  {
    ico: '⊕', label: 'Świat',
    chapters: [
      { id: 'swiat', title: 'NPC, wrogowie i zasady świata', body: STUB },
      {
        id: 'sol-rdzen',
        title: 'Sól i „istoty Rdzenia" (klasa wroga)',
        body: `
<p>Wrogowie mają pole <b>klasa istoty</b> (<code>creature_type</code>) — puste dla zwykłych, żywych
stworzeń, a dla reszty jedna z trzech wartości: <code>undead</code> (nieumarli), <code>demon</code>,
<code>rdzen</code> (twory żyły Rdzenia). To pole robi jedną rzecz: decyduje, czy działają na wroga
<b>przedmioty solne</b> z krainy Siwych Grań.</p>
<h4>Trzy przedmioty solne</h4>
<ul>
  <li><b>Krąg soli</b> — istoty Rdzenia nie wchodzą do zwarcia przez 3 rundy; te, które już stoją
      w zwarciu, zostają wypchnięte na dystans w chwili użycia.</li>
  <li><b>Solona klinga</b> — +1k4 obrażeń przeciw istotom Rdzenia, na jedną walkę.</li>
  <li><b>Szczypta soli</b> — najbliższy miscast maga o 1 stopień łagodniejszy (raz na walkę),
      w zamian −1 do obrażeń czarów do końca walki.</li>
</ul>
<p>Na żywym wrogu (troll, wilk, bandyta) żaden z tych przedmiotów nie robi <b>nic</b> — tak działa
fikcja krainy: sól nie jest magiczna, jest obojętna na Rdzeń.</p>
<p>Jeśli dodajesz nowego nieumarłego albo demona i chcesz, żeby sól na niego działała, ustaw mu
klasę istoty. Nowe wpisy bez klasy są traktowane jak żywe. Kupcem solnym jest
<b>Helga Solnobroda</b> (targ Kamiennego Grodu) — asortyment solny widać w jej sklepie.</p>
<p class="muted">Wartości (3 rundy, 1k4, −1 do obrażeń, ceny 30–45 GP) to wartości startowe —
do strojenia w Sandboksie.</p>`,
      },
      {
        id: 'towarzysze',
        title: 'Zakładka Towarzysze (najemnicy i wierzchowce)',
        body: `
<p>W sekcji <b>Świat</b> zakładka <b>Towarzysze</b> to katalog towarzyszy podróży i wierzchowców,
których gracz może najmować i kupować w osadach — tak jak katalog wrogów, tylko po przyjaznej stronie.</p>
<h4>Trzy typy</h4>
<ul>
  <li><b>🗡 Najemnik</b> i <b>🐕 Zwierzę (pies)</b> — <b>walczą</b> u boku bohatera (podaj <b>Atak (JSON)</b>,
      np. <code>{"attack_bonus":3,"damage_dice":"1d6","zone":"engaged"}</code>).</li>
  <li><b>🐴 Wierzchowiec</b> (koń, muł) — <b>nie walczy</b>; zostaw pole Atak puste. Skraca podróż i daje
      ucieczkę przed walką. Efekty ustawiasz w polu <b>Pasywy (JSON)</b>:
      <code>travel_speed_mult</code>, <code>daily_cap_bonus_h</code>, <code>escape_enabled</code>,
      <code>encounter_chance_mult</code> (pies), <code>terrain_speed_mult</code> (tropiciel).</li>
</ul>
<h4>Koszty</h4>
<p><b>Najem/dzień</b> = żołd potrącany co dzień gry (0 = nie do najęcia). <b>Kupno</b> = cena na własność
(puste = nie do kupienia). <b>Utrzymanie/dz</b> = pasza dla kupionego wierzchowca. Głodny koń traci bonusy;
niezapłacony najemnik po dwóch dniach odchodzi.</p>
<h4>Kreator AI</h4>
<p>Przycisk <b>+ Dodaj towarzysza</b> otwiera formularz. Możesz też użyć <b>Kreatora AI</b> (Smart Entry) —
opisz towarzysza, a LLM wypełni pola. Aby przyznać towarzysza konkretnemu bohaterowi od ręki, użyj cheatu
<code>grant companion</code> w Inspektorze bohatera (sekcja Gracze).</p>
<p class="muted">Wszystkie liczby (HP, koszty, mnożniki) to wartości startowe — strojone po obserwacji rozgrywki.</p>`,
      },
      {
        id: 'wydarzenia',
        title: 'Zakładka Wydarzenia (żywy świat)',
        body: `
<p>W sekcji <b>Świat</b> zakładka <b>Wydarzenia</b> steruje „żywym światem" — region co jakiś czas
dostaje wydarzenie, które realnie zmienia grę, nawet gdy gracz nic nie robi:</p>
<ul>
  <li><b>🎪 Jarmark</b> — ceny w sklepach niższe (−20%), gwar w osadzie.</li>
  <li><b>☠ Zaraza</b> — mikstury droższe (+50%), a odpoczynek w osadzie regionu grozi
      chorobą (bohater rzuca na odporność; przy porażce łapie kondycję <b>Chory</b> — kara do testów,
      leczona u zielarza/uzdrowiciela lub miksturą).</li>
  <li><b>⚔ Rajdy bandytów</b> — częstsze spotkania na traktach regionu, ale lepszy łup z bandytów.</li>
  <li><b>❄ Surowa zima / 🌵 Susza</b> — podróż między osadami trwa dłużej.</li>
</ul>
<p>Gracz dowiaduje się o wydarzeniu z <b>narracji</b>, <b>cen w sklepie</b> i <b>znacznika na mapie</b>
(ŻAR) — nie ma osobnego ekranu.</p>
<h4>Sterowanie</h4>
<p>Na dole zakładki: wybierz <b>region</b> i <b>szablon</b>, opcjonalnie liczbę dni, i kliknij
<b>+ Dodaj wydarzenie</b>. Przycisk <b>🎲 Wylosuj</b> dobiera wydarzenie losowo dla regionu.
Aktywne wydarzenie kończysz przyciskiem <b>⏹</b> w wierszu. W jednym regionie może trwać
najwyżej jedno wydarzenie naraz.</p>
<h4>Automatyczne losowanie</h4>
<p>Przełącznik u góry (<b>Automatyczne losowanie przy zmianie dnia gry</b>) jest domyślnie
<b>wyłączony</b>. Włączony — świat sam losuje wydarzenia (mała szansa dziennie na region).
Ręczne sterowanie działa zawsze, niezależnie od przełącznika.</p>
<p class="muted">Wszystkie liczby (szansa, czas trwania, mnożniki cen, DC choroby) to wartości
startowe — będą strojone po obserwacji rozgrywki.</p>`,
      },
      {
        id: 'plotki',
        title: 'Zakładka Plotki (kierowanie graczami)',
        body: `
<p>W sekcji <b>Świat</b> zakładka <b>Plotki</b> to <b>pula plotek dla całego regionu</b> — nie dla
jednej kampanii. Plotki, które tu dodasz, może usłyszeć <b>każdy bohater</b> przebywający w tym
regionie, gdy nadstawi ucha w karczmie. To kanał dystrybucji hooków (lochy, skarby, wydarzenia,
nieodkryte lokacje) <b>bez</b> łamania immersji przez „deus ex machina" w narracji.</p>
<p>Gracz zdobywa plotki sam: w karczmie pisze <b>„nadstawiam ucha"</b> (za darmo, plotka nie zawsze
się trafia) albo <b>„stawiam kolejkę"</b> (kosztuje kilka złotych, plotka gwarantowana i łatwiej
wyczuć fałsz). System najpierw sięga po Twoje plotki z puli regionu, a dopiero potem generuje
zastępczą plotkę dobraną pod danego bohatera.</p>
<h4>Prawda i fałsz</h4>
<p>Świat nie jest wiarygodny w 100% — część plotek to <b>bujda</b>. Prawdziwa plotka <b>potwierdza się</b>,
gdy gracz dotrze do celu; fałszywa <b>demaskuje się</b> („okazała się bujdą") i zostaje przekreślona
w dzienniku gracza. Udany test wyczucia (WIS/CHA) oznacza plotkę jako <b>podejrzaną</b>, ale nie zdradza
wprost prawdy.</p>
<h4>Jak dodać plotkę</h4>
<p>Najpierw wybierz <b>region</b> z listy u góry. Potem:</p>
<ul>
  <li><b>+ Dodaj ręcznie</b> — podaj treść i zdecyduj (OK = prawdziwa, Anuluj = fałszywa).
      Najdelikatniejsze narzędzie do naprowadzania graczy.</li>
  <li><b>🤖 Generuj plotki AI</b> — podaj ile (1–12). LLM bierze fakty tego regionu
      (lokacje, lochy, aktywne wydarzenie) i tworzy plotki, część <b>celowo fałszywych</b>.
      Plotki, które nie pasują, po prostu usuń przyciskiem 🗑.</li>
</ul>
<p>Kolumna <b>Źródło</b> pokazuje, czy plotka jest 🤖 AI czy ✋ ręczna. Plotki błędne usuwasz 🗑.</p>
<p class="muted">Generator AI korzysta z profilu <b>content-LLM</b> (Ustawienia). Koszt kolejki, szansa
na plotkę, proporcja prawda/fałsz i DC wyczucia to wartości startowe — będą strojone po obserwacji.</p>`,
      },
    ],
  },
  {
    ico: '🗺', label: 'Mapa',
    chapters: [
      {
        id: 'kontrola-swiata',
        title: '🩺 Kontrola świata (lampka zamiast cichej samonaprawy)',
        body: `
<p>Do tej pory świat prostował się <b>sam i po cichu</b> przy każdym starcie backendu. Rozjazd znikał
z ekranu, ale przyczyna zostawała, a Ty nigdy się nie dowiadywałeś, że coś było nie tak. Zakładka
<b>Mapa → 🩺 Kontrola świata</b> odwraca to: pokazuje listę problemów i pozwala je naprawiać
świadomie, jednym kliknięciem.</p>
<h4>Co lint sprawdza</h4>
<ul>
  <li><b>Usługa bez gospodarza</b> — karczma, kuźnia, kram, świątynia, stajnia albo komora, w której
      nie stoi ani jeden NPC. Gracz wchodzi do pustego wnętrza. Liczone <b>tylko dla krain
      otwartych</b> (status <code>live</code>) — Czarnobór i Pustkowia wejdą tu same w dniu otwarcia.</li>
  <li><b>Sierota obsady</b> — NPC przypisany do lokacji, której już nie ma.</li>
  <li><b>Heks bez lokacji</b> — pole mapy wskazuje lokację, która nie istnieje.</li>
  <li><b>Pin bez kanonu</b> — lokacja twierdzi, że stoi na heksie, którego mapa jej nie przyznaje.</li>
  <li><b>Zepsuty rodzic</b> — sub-lokacja bez rodzica albo z niekompletnym wiązaniem.</li>
  <li><b>Nielegalna flaga</b> — <code>created_by</code> / <code>review_status</code> spoza dozwolonego zbioru.</li>
  <li><b>Duplikat etykiety</b> — dwie lokacje o (prawie) tej samej nazwie w jednej krainie.</li>
</ul>
<h4>Guzik „Napraw" i naprawa masowa</h4>
<p>Pojawia się tylko przy rozjazdach, które da się rozwiązać <b>jednoznacznie</b> (odpiąć pin, zwolnić
heks, uzupełnić rodzica, zdjąć martwe przypisanie). Tam, gdzie potrzebna jest <b>decyzja treściowa</b>
— dosiew gospodarza albo wybór, którą kopię lokacji zostawić — panel pisze „decyzja człowieka"
i niczego nie zgaduje.</p>
<p>Lista jest <b>pogrupowana po regule</b>, bo tak wyglądają realne dane: kilkanaście sub-lokacji po
skasowanym szablonie to jeden problem powtórzony wiele razy, a nie kilkanaście osobnych decyzji.
Nad każdą taką grupą jest <b>🔧 Napraw wszystkie (N)</b> — jedno potwierdzenie, wszystkie naprawy
osobno zapisane w historii. Grupy „decyzja człowieka" nie dostają go nigdy.</p>
<p><b>Czego celowo nie ma:</b> guzika „napraw wszystko" dla całej listy. Taki guzik odtworzyłby ciche
zamiatanie — tylko z jednym kliknięciem zamiast po nocach. Naprawa masowa zawsze dotyczy jednej
reguły, którą świadomie wskazałeś.</p>
<h4>Kronika napraw</h4>
<p>Przycisk <b>🕮 Historia napraw</b> pokazuje, co i kiedy zostało naprawione — osobno to, co zrobił
start backendu (⚙️), a osobno to, co kliknąłeś sam (👤). Licznik problemów wisi jako plakietka
przy pozycji <b>Mapa</b> w menu bocznym.</p>`,
      },
      {
        id: 'cykl-lokacji',
        title: 'Skąd biorą się lokacje',
        body: `
<p>Lokacje w bazie powstają czterema drogami. Trzy z nich to twórczość AI — takie lokacje
zawsze trafiają do kolejki <b>Mapa → Do zatwierdzenia</b>, gdzie decydujesz o ich losie.</p>

<h4>1. Narrator wymyśla miejsce w trakcie gry</h4>
<p>Gracz gra, narrator opisuje scenę i „powołuje do życia" nowe miejsce.
<i>Przykład: gracz pisze „rozglądam się po wiosce", narrator odpowiada „na skraju wioski
dostrzegasz kuźnię starego Bartha" — i w tej chwili w bazie powstaje lokacja „Kuźnia Bartha".</i>
Takie wpisy mają w kolumnie autora <code>gm_runtime</code>.</p>

<h4>2. Gracz idzie w miejsce, którego jeszcze nie ma</h4>
<p>Plan przygody wspomina jakieś miejsce (np. „chata zielarki"), ale nikt go nie założył.
Gdy gracz tam rusza i narrator potwierdza, system sam zakłada lokację — i gracz
<b>od razu do niej wchodzi</b>, zanim ją zobaczysz w kolejce (patrz rozdział
„Jak narrator (AI) korzysta z lokacji").</p>

<h4>3. Kuźnia — szablony przygód</h4>
<p>Gdy w sekcji <b>Kuźnia</b> generujesz szablon przygody, wszystkie kluczowe miejsca z planu
(osady, lochy, punkty fabularne) są od razu zakładane w bazie i czekają w
<b>Do zatwierdzenia</b>. Autor: <code>forge</code>.</p>

<h4>4. Start kampanii z szablonu</h4>
<p>Przy uruchomieniu kampanii z szablonu system zakłada lokację startową i strukturę osady.
Też trafiają do kolejki, ale <b>z jedną różnicą: od razu dostają hex na mapie</b>
(gracz musi gdzieś zacząć), więc nie zobaczysz ich w <b>⚓ Floating</b>.</p>

<h4>Lokacje zakładane ręcznie</h4>
<p>To, co dodasz sam przyciskiem <b>+ Dodaj lokację</b>, NIE przechodzi przez kolejkę —
od razu jest pełnoprawną częścią świata.</p>`,
      },
      {
        id: 'do-zatwierdzenia',
        title: 'Zakładka Do zatwierdzenia',
        body: `
<p>Kolejka lokacji stworzonych przez AI. Czerwona plakietka <b>N oczekujące</b> u góry sekcji
<b>Mapa</b> pokazuje, ile wpisów czeka. Przy każdej pozycji masz cztery przyciski:</p>

<h4>👁 Podgląd</h4>
<p>Pełne dane wpisu (opis, biom, typ, rodzic). Możesz poprawić pola przed decyzją.</p>

<h4>✓ Zatwierdź</h4>
<p>Lokacja staje się stałą częścią świata: narrator zaczyna ją widzieć w kontekście okolicy,
gracze mogą do niej wracać. Dla osad (miasto/wioska) wyskoczy checklista podlokacji —
zaznaczone (karczma, targ itp.) zostaną dogenerowane jako części osady.</p>
<p><b>Uwaga:</b> zatwierdzenie <b>nie umieszcza lokacji na mapie</b>. Jeśli nie ma hexa,
pojawi się w <b>⚓ Floating</b> — tam ją osadzasz. Zatwierdzenie nie zmienia też terenu żadnego hexa.</p>

<h4>★ Kanon</h4>
<p>To samo co <b>✓ Zatwierdź</b>, plus oznaczenie lokacji jako <b>kanonicznej</b> dla świata.
Flaga kanonu daje trzy konkretne rzeczy:</p>
<ol>
<li><b>Drogowskaz na mapie gracza</b> — hex z kanoniczną lokacją jest podpisany nazwą od
początku gry („znane z opowieści"), zanim gracz tam dotrze. Zwykła lokacja podpisuje się
dopiero po odkryciu hexa.</li>
<li><b>Pula miejsc startowych</b> — nowa kampania bez szablonu losuje start wyłącznie
spośród lokacji kanonicznych (typu macro). Bez kanonów system nie ma z czego wybierać.</li>
<li><b>Cele podróży</b> — dopasowanie nazw celów podróży i map skarbów szuka po kanonach.</li>
</ol>
<p><b>Kiedy co:</b> <b>★ Kanon</b> dla stałych punktów świata (miasta, ważne osady, landmarki).
<b>✓ Zatwierdź</b> dla miejsc jednorazowych — karczma z jednej przygody nie musi być
drogowskazem dla wszystkich graczy.</p>

<h4>✕ (odrzuć)</h4>
<p>Wpis znika z kolejki, ale <b>zostaje w bazie</b> (status „odrzucona"). Jeśli był podpięty
do hexa — hex dalej na niego wskazuje. Żeby naprawdę usunąć, przejdź do zakładki
<b>Lokacje</b> albo <b>🧹 Duplikaty</b> i tam skasuj.</p>

<h4>🏘️ Heksy z podmapą</h4>
<p>Niżej w tej samej zakładce: tabela hexów, których typ terenu może mieć lokalną podmapę
(miasto, ruiny itp.). Wybierz rozmiar (S/M/L/XL) i kliknij <b>🏘 Generuj</b>
(albo <b>↺ Regen</b> / <b>✎ Edytuj</b>, jeśli podmapa już istnieje).
Uwaga przy <b>↺ Regen</b>: jeśli podmapa zawiera osadzone lokacje, system poprosi
o potwierdzenie — regeneracja usuwa układ sub-hexów.</p>`,
      },
      {
        id: 'floating',
        title: 'Zakładka ⚓ Floating',
        body: `
<p>Lokacje, które istnieją w bazie, ale <b>nie stoją na żadnym hexie mapy świata</b>.
Najczęściej: świeżo zatwierdzone wpisy z <b>Do zatwierdzenia</b> (drogi 1–3 z rozdziału
„Skąd biorą się lokacje").</p>
<h4>⚓ Osadź</h4>
<p>Otwiera okno <b>⚓ Osadź lokację na hexie</b>. Podajesz <b>Współrzędna Q (kolumna)</b> i
<b>Współrzędna R (wiersz)</b> — hex zaczyna wskazywać na tę lokację, a lokacja znika z Floating.</p>
<ul>
<li>Jeden hex = jedna lokacja. Jeśli hex jest zajęty, system odmówi.</li>
<li><b>Osadzenie nie zmienia terenu hexa.</b> „Święty gaj" osadzony na bagnie zostanie na
bagnie — dobierz hex pasujący do charakteru miejsca (teren malujesz osobno w zakładce
<b>Mapa</b>, patrz rozdział „Zakładka Mapa (budowniczy świata)").</li>
<li>Współrzędne hexa podejrzysz klikając hex w budowniczym.</li>
</ul>
<h4>👁 Podgląd</h4>
<p>Pełne dane lokacji przed osadzeniem.</p>`,
      },
      {
        id: 'lokacje',
        title: 'Zakładka Lokacje',
        body: `
<p>Pełna lista lokacji świata w formie drzewa (osada → podlokacje). Filtry: wyszukiwarka,
typy (<b>Wszystkie / Loch / Miasto / Dzikość</b>) i lista krain (<b>Wszystkie krainy</b>).</p>
<h4>Akcje na pojedynczym wierszu</h4>
<ul>
<li><b>👤</b> — przypisz NPC/wrogów do lokacji.</li>
<li><b>🎨</b> / <b>🖼</b> — wygeneruj / podejrzyj obraz lokacji.</li>
<li><b>✎</b> — edycja pól (nazwa, typ, biom, tier, opis, obraz).</li>
<li><b>✕</b> — usunięcie lokacji <b>razem z podlokacjami</b>. Usunięcie jest trwałe
(wpis znika z bazy), z jednym wyjątkiem: lokacja, na którą wskazuje hex mapy świata,
nie zostanie skasowana — najpierw odepnij ją od hexa w budowniczym.</li>
</ul>
<h4>Masowe usuwanie</h4>
<p>Zaznacz lokacje checkboxami w pierwszej kolumnie (checkbox w nagłówku zaznacza wszystkie).
Pojawi się przycisk <b>🗑 Usuń zaznaczone (N)</b>. Po potwierdzeniu usuwa wszystkie
zaznaczone wpisy; na końcu toast pokaże, ile się udało, a ile nie.</p>
<h4>+ Dodaj lokację</h4>
<p>Ręczne dodanie lokacji — taki wpis nie przechodzi przez kolejkę zatwierdzania.</p>`,
      },
      {
        id: 'duplikaty',
        title: 'Zakładka 🧹 Duplikaty',
        body: `
<p>Detektor porządkowy: znajduje lokacje o tej samej (lub prawie tej samej) nazwie oraz
cztery rodzaje śmieci. Czerwona plakietka na zakładce pokazuje liczbę nadmiarowych duplikatów.</p>

<h4>Sekcja DUPLIKATY (ta sama nazwa)</h4>
<p>Grupy lokacji o identycznej nazwie (<b>🟰 Dokładne</b>) lub bardzo podobnej (<b>≈ Podobne</b>).
W każdej grupie:</p>
<ul>
<li><b>⦿ = zachowaj</b> — wybierz jedną lokację, która przetrwa;</li>
<li><b>☑ = usuń</b> — zaznacz kopie do skasowania;</li>
<li><b>Scal</b> — wykonuje scalenie: podlokacje i sesje graczy zostają przepięte na
zachowaną, kopie są usuwane;</li>
<li><b>🚫 Nie duplikat</b> — fałszywy alarm (np. dwie różne „Karczmy" w różnych miastach):
grupa znika ze skanów na stałe;</li>
<li><b>🔒 hex</b> przy wpisie — ta kopia stoi na hexie mapy świata i <b>nie zostanie
usunięta</b> przy scalaniu. Jeśli chcesz się jej pozbyć: wybierz ją jako zachowaną
(⦿) albo najpierw odepnij od hexa w budowniczym.</li>
</ul>

<h4>Sekcja ŚMIECI</h4>
<ul>
<li><b>🧪 Testowe / smoke</b> — pozostałości po testach automatycznych.</li>
<li><b>🔗 Osierocone</b> — podlokacje, których rodzic już nie istnieje.</li>
<li><b>🎈 Bez hexa i kampanii</b> — aktywne lokacje niepodpięte do niczego.</li>
<li><b>💤 Nieaktywne</b> — wpisy wyłączone z gry, zalegające w bazie.</li>
</ul>
<p>Przy każdym wpisie przycisk <b>Usuń</b> — kasuje trwale. <b>↻ Odśwież</b> ponawia skan.</p>
<p><b>Ważne:</b> nieaktywne lokacje nie są liczone jako duplikaty (nie ma ich w grze) —
znajdziesz je wyłącznie w kuble <b>💤 Nieaktywne</b>.</p>`,
      },
      {
        id: 'dostepnosc-krain',
        title: 'Udostępnianie krain graczom',
        body: `
<p>Świat ma sześć krain, ale gracze mają widzieć tylko te, które sam otworzysz.
Każda kraina ma jeden z trzech stanów:</p>
<ul>
<li><b>live</b> — otwarta, gracze mogą tam podróżować.</li>
<li><b>coming</b> — poczekalnia. Gracz odbija się z komunikatem „Kraina niedostępna",
ale konto z flagą <b>Tester</b> może tam wejść i sprawdzić krainę przed premierą.</li>
<li><b>locked</b> — zamknięta na głucho. Nie wchodzi nikt, także tester.</li>
</ul>
<h4>Gdzie to przełączyć</h4>
<p><b>Mapa → zakładka Mapa</b> → w pasku nad kanwą wybierz krainę z listy rozwijanej.
Dopiero wtedy pojawi się przycisk <b>✅ Udostępnij graczom</b> / <b>🚫 Ukryj graczom</b>.
Przy „Wszystkie (live)" przycisku nie ma — nie wiadomo, której krainy miałby dotyczyć.</p>
<p>Zmiana działa <b>natychmiast</b>: gracz w trakcie sesji od razu przestaje (albo zaczyna)
przechodzić granicę. Decyzja jest trwała — przeżywa restart serwera.</p>
<h4>Co jeszcze się zmienia</h4>
<p>Rasy są przypisane do krain ojczystych (krasnolud → <b>Siwe Granie</b>,
elf leśny → <b>Czarnobór</b>). Gdy zamkniesz
taką krainę, karta tej rasy w kreatorze bohatera <b>wyszarza się</b> z powodem
(„te ziemie są jeszcze zamknięte") — nie znika, więc gracz wie, że coś nadejdzie.
Człowiek nie ma kotwicy i jest dostępny zawsze. Istniejący bohaterowie grają dalej
bez zmian.</p>
<h4>Rasa wyznacza też archetyp i miejsce startu (#1477)</h4>
<p>Krasnolud gra tylko <b>Wojownikiem</b> albo <b>Uczonym Rdzenia</b> — karta Łotrzyka
nie pojawia się w kreatorze po wybraniu tej rasy, a backend odrzuca taki zapis, nawet
gdyby ktoś próbował wysłać go z pominięciem UI. Człowiek ma wszystkie trzy archetypy.</p>
<p>Kampania krasnoluda startuje w <b>Siwych Graniach</b>: domyślnie w szynku
<b>„Pod Rdzawym Młotem"</b> (Kamienny Gród). Plan kampanii może zamiast tego wskazać
<b>Karawanseraj na Trakcie</b> lub <b>Wyrobisko Srebrnej Żyły</b> — nazwa spoza tej trójki
cofa start do szynku. Człowiek startuje jak dotąd. Jawny <i>start-hex</i> ustawiony
w Kuźni wygrywa z kotwicą rasy, więc szablon może celowo postawić bohatera gdzie indziej.</p>
<h4>Elf leśny (#1474)</h4>
<p>Elf gra tylko <b>Zwiadowcą</b> albo <b>Uczonym-Stroicielem</b> — karty Wojownika nie ma
w kreatorze po wybraniu tej rasy (backend też ją odrzuca). W kreatorze nazwy archetypów
zmieniają się wraz z rasą: „Łotrzyk" czyta się u elfa jako <b>Zwiadowca</b>, „Uczony" jako
<b>Uczony-Stroiciel</b> — klucze w bazie zostają te same.</p>
<p>Czary elfa to osobna pula <b>szkoły Stroiciela</b> (kontrola, ochrona, iluzje), zamknięta
polem <code>race_lock = elf</code> w <b>Zawartość → Czary</b>. Elf nie nauczy się czarów
ludzkich ani krasnoludzkich i odwrotnie — tak samo jak przy Rdzeń-magii.</p>
<p><b>Pola „Rasy (kto może się uczyć)" w modalu czaru (#1510):</b> trzy checkboxy —
Ludzie / ⛏ Krasnolud / 🍃 Elf. Każdy z 50 czarów ma teraz wpis <b>jawnie</b>: 37 ludzkich,
6 krasnoludzkich (Rdzeń), 6 elfich (Stroiciel), 1 wspólny (Rana Uleczona = krasnolud + człowiek).
Zaznaczenie kilku ras robi z czaru pulę wspólną. Puste zaznaczenie = zapis <code>NULL</code>,
który silnik nadal czyta jako „tylko ludzie" — lepiej zaznaczyć świadomie.
Zmiana działa od razu: kreator, zakładka <i>Czary</i>, modal awansu przy odpoczynku i lista
czarów w walce biorą tę samą listę (backend odsiewa katalog po rasie bohatera).</p>
<p><b>Czary użytkowe ras (#1518):</b> elf i krasnolud mają po <b>7 własnych czarów narracyjnych</b>
(typ <code>narrative</code>, bez obrażeń, rzucane poza walką) — elf: Rój Świetlików, Szept Kniei,
Wzrok Pęknięć, Mowa Liści, Kojący Gaj, Stróżowe Drzewo, Nastrojenie Pęknięcia; krasnolud:
Kuźniany Żar, Wyczucie Żyły, Pamięć Kamienia, Kowalski Uchwyt, Głęboka Droga, Kowadłowy Krąg,
Czarna Cisza. Efekt gra narrator — silnik liczy tylko manę, więc dodanie kolejnego takiego
czaru to sam wpis w tabeli, bez kodu.</p>
<p><b>Balans bojówki ras (#1519):</b> gra jest w głównej mierze jednoosobowa, więc każda rasa
musi mieć czym uderzyć, zasłonić się, wyleczyć i zatrzymać wroga — bez drużyny nie ma kto
załatać brakującej roli. Elf dostał <i>Uskok Cienia</i> (T2 reakcja), <i>Korę Pradrzewa</i>
(T3 tarcza 12), <i>Deszcz Cierni</i> (T4 AoE), <i>Zielone Odrodzenie</i> (T4 leczenie 3d6),
<i>Pieśń Pęknięcia</i> (T5 3d8+ogłuszenie). Krasnolud: <i>Kamienna Postawa</i> (T1 tarcza 6),
<i>Żarowe Zrastanie</i> (T2 leczenie), <i>Okowy Skalne</i> (T3 unieruchomienie),
<i>Runy Rodu</i> (T4 tarcza 14), <i>Rodowa Opoka</i> (T5 nietykalność 2 rundy).
Bilans czarów bojowych: <b>człowiek 34 · krasnolud 12 · elf 11</b> (pule całkowite 36/19/18).
Wyłączone jako duplikaty: <code>frost_bolt</code>, <code>lightning_arrow</code> (ściśle gorsze
od Ognistego Pocisku i Lodowej Lancy, nikt ich nie znał). <code>acid_splash</code> dostał rolę
antypancerną, <code>magic_bolt</code> przeszedł na T2 (2d6 za 2 many bił wszystko na T1).</p>
<p><b>Bramka umiejętności klasa+rasa (#1522):</b> do tej pory kreator dawał każdemu archetypowi
cały katalog 43 umiejętności — Zwiadowca bez many mógł wziąć <i>Tarczę Many</i>. Teraz trzy grupy
są zamknięte: MAGICZNE (<code>arcana</code>, <code>arcane_ward</code>, <code>mana_shield</code>,
<code>magic_sense</code>) = Uczony; CIĘŻKA WALKA (<code>shield_block</code>,
<code>two_handed</code>, <code>wrestling</code>) = Wojownik; ZŁODZIEJSKIE (<code>lockpick</code>,
<code>pickpocket</code>, <code>disguise</code>) = Łotrzyk. Rasa odblokowuje: elf →
<code>magic_sense</code>, krasnolud → <code>shield_block</code> + <code>two_handed</code>.
Reguła siedzi w <code>backend/app/services/skill_access_service.py</code> (jedno źródło: rzut
startowy, zamiana w kreatorze, nauka za XP, katalog <code>/api/mechanics/skills?character_id=</code>).
Istniejące postacie zachowują to, co już mają — bramka działa na nowe nabycia.</p>
<p><b>Uwaga o starcie:</b> Czarnobór nie ma jeszcze zaseedowanej mapy, więc kampania elfa
startuje na razie tam, gdzie kampania człowieka (Kresy). Kotwica startowa w krainie ojczystej
dojdzie razem z wdrożeniem Czarnoboru (sesja CB-8). Sama rasa jest już zabramkowana statusem
krainy: dopóki Czarnobór stoi na <b>coming</b>, kartę elfa widzi tylko konto z flagą Tester.</p>
<p><b>Flagę Tester</b> nadajesz w <b>Gracze</b> → konto → „Tester (może zgłaszać błędy)".
Tester dostaje też rasy krain w stanie <b>coming</b> — skoro może tam wejść, może nimi grać.</p>
<h4>Wizytówka nadąża sama</h4>
<p>Karty krain na stronie-wizytówce mają odznaki <b>grywalne</b> / <b>wkrótce</b>. Idą one
za stanem gry — przełączysz krainę w panelu, odznaka zmienia się bez ruszania plików.</p>
<p>Gdybyś potrzebował rozjazdu celowo (np. kraina już grywalna, ale jeszcze niezapowiedziana),
w <code>swiat.json</code> jest pole <code>available_override</code>: <code>true</code> lub
<code>false</code> wygrywa ze stanem gry. Pole <code>available</code> to lustro utrzymywane
automatycznie — nie edytuj go ręcznie.</p>`,
      },
      {
        id: 'budowniczy',
        title: 'Zakładka Mapa (budowniczy świata)',
        body: `
<p>Edytor siatki hexów świata. Tu — i tylko tu — zmienia się <b>teren</b>. Żadna akcja
zatwierdzania, osadzania ani kanonu lokacji nie modyfikuje terenu hexa.</p>
<h4>Narzędzia (lewy pasek)</h4>
<ul>
<li><b>⬡ Wybierz</b> — klik na hex otwiera jego edycję w prawym panelu (typ terenu,
etykieta, atmosfera, szansa spotkania, przypięta lokacja).</li>
<li><b>🖌 Maluj</b> — wybierz typ terenu z palety TEREN i przeciągnij po mapie.</li>
<li><b>↶ Cofnij</b> — cofa ostatnią edycję (też Ctrl+Z).</li>
<li><b>📍 Lokacje na mapie</b> — podświetla hexy z przypiętymi lokacjami (zielone = ma lokację).</li>
<li><b>⊡ Dopasuj</b> — wycentrowanie widoku. Alt+przeciągnięcie = przesuwanie, scroll = zoom.</li>
</ul>
<h4>💾 Zapisz mapę (kanon) / 📂 Wczytaj mapę (z kanonu)</h4>
<p><b>To jest inny „kanon" niż przycisk ★ Kanon przy lokacji</b> — wspólna jest tylko nazwa.</p>
<ul>
<li><b>💾 Zapisz mapę (kanon)</b> — robi zrzut siatki hexów (teren, etykiety, krainy)
do pliku wzorcowego. Gdy masz wybraną krainę, zapisuje TYLKO ją. Ten zapis przeżywa reset
bazy. Rób go po każdej większej ręcznej edycji mapy, z której jesteś zadowolony.</li>
<li><b>📂 Wczytaj mapę (z kanonu)</b> — przywraca <b>wybraną krainę</b> z pliku wzorcowego,
nadpisując jej heksy. Bez wybranej krainy przycisk poprosi o jej wskazanie — od #1482 nie
da się jednym kliknięciem nadpisać wszystkich krain naraz.</li>
<li>System odmówi zapisu, gdy mapa wygląda na pustą — ochrona przed nadpisaniem dobrego
wzorca śmieciem.</li>
</ul>

<h4>Dlaczego nie ma już „🌍 Generuj świat" (#1482)</h4>
<p>Świat Kresów budujemy ręcznie, heks po heksie. Proceduralny generator całego świata
i przycisk „🗑 Wyczyść mapę świata" zostały usunięte — jedno kliknięcie potrafiło skasować
godziny pracy. Zakładka nazywa się teraz <b>⚙ Ustawienia mapy</b> i trzyma licznik heksów
oraz zasięg mgły wojny.</p>
<p>Gdyby coś próbowało masowo skasować mapę (skrypt, stary przycisk, pomyłka w API),
serwer odmawia z komunikatem i podpowiada właściwą drogę: odtworzenie <b>per kraina</b>
z plików w gicie (<code>data/regions/region_&lt;klucz&gt;.json</code>). Nie dotyczy to
edycji pojedynczego hexa, malowania terenu ani <b>🏘 Generuj</b> dla podmap osad — te działają
normalnie.</p>
<p>Dla porównania: <b>★ Kanon</b> (w <b>Do zatwierdzenia</b>) oznacza JEDNĄ lokację jako
kanoniczną (drogowskaz, pula startów). <b>💾 Zapisz mapę (kanon)</b> zabezpiecza CAŁY teren świata.</p>`,
      },
      {
        id: 'skarby',
        title: 'Mapy skarbów i ich fragmenty',
        body: `
<p>Mapa skarbu prowadzi bohatera do <b>zakopanego skarbu</b> na konkretnym hexie świata. Mapa może
przyjść w całości albo w <b>kilku fragmentach</b> — bohater musi zebrać komplet, zanim skrytka
pojawi się na jego mapie i da się ją odkopać. To osobna zawartość od zwykłego łupu: nośnik mapy
nigdy nie ląduje jako martwy przedmiot w plecaku — system przechwytuje go i zapisuje jako postęp
mapy.</p>

<h4>Skąd bohater bierze mapę (dwie drogi)</h4>
<ol>
<li><b>Z łupu (losowo)</b> — nośnik <code>fragment_mapy_skarbow</code> wpada z tabeli łupów jak
każdy inny przedmiot. Steruje tym <b>Przedmioty → Tabele łupów</b> (patrz niżej).</li>
<li><b>Ręcznie zakopana przez Ciebie</b> — przyciskiem <b>🗺 Zakop skarb</b> w budowniczym mapy.</li>
</ol>

<h4>🗺 Zakop skarb (ręczne wręczenie mapy)</h4>
<p>W sekcji <b>Mapa</b> wybierz narzędzie <b>⬡ Wybierz</b> i kliknij hex, na którym ma leżeć skarb —
w prawym panelu edycji hexa jest przycisk <b>🗺 Zakop skarb</b>. Zapyta o cztery rzeczy:</p>
<ul>
<li><b>ID bohatera (character_id)</b> — kto dostanie mapę do swoich <b>Map skarbów</b>. Pole
obowiązkowe; ID podejrzysz w sekcji <b>Bohaterowie</b>.</li>
<li><b>Liczba części mapy</b> — <b>1</b> = cała mapa naraz; więcej = tyle fragmentów do uzbierania
(bohater zbiera je stopniowo).</li>
<li><b>Nazwa skarbu</b> (opcjonalnie) — etykieta widoczna dla gracza (domyślnie „Mapa skarbu").</li>
<li><b>Klucz strażnika</b> (opcjonalnie) — klucz wroga, który pilnuje skrytki; puste = brak strażnika.
Przy kopaniu wskoczy walka z nim.</li>
</ul>
<p>Po zakopaniu toast potwierdza <b>Skarb zakopany (#numer)</b>. Skarb jest <b>jednorazowy dla tego
bohatera</b> — ten sam bohater nie odkopie go dwa razy.</p>

<h4>Sterowanie szansą wypadnięcia mapy (z łupu)</h4>
<p>Prawdopodobieństwo, że mapa wypadnie z walki, ustawiasz w sekcji <b>Przedmioty → Tabele łupów</b>.
W tabeli łupów danego wroga dodaj wpis niosący <code>fragment_mapy_skarbow</code> i ustaw pole
<b>Waga (1-100)</b> — waga to wprost szansa w procentach (np. 10 = 10% na wpis). Szansa wpisu jest
dodatkowo bramkowana <b>szansą łupu wroga</b> (pole przy edycji wroga): jeśli ta bramka spudłuje,
nie pada nic. Efektywna szansa = szansa_łupu × (waga/100).</p>
<p><b>Uwaga (obejście):</b> istniejącej wagi wpisu z mapą <b>nie zmienisz w miejscu</b> — <b>usuń</b>
wpis i <b>dodaj go ponownie</b> z nową wagą.</p>

<h4>Co robi gracz</h4>
<p>Fragmenty tej samej mapy grupują się razem (po skarbie, nie po nazwie). Gdy bohater ma komplet,
mapa jest <b>złożona</b> i skrytka pojawia się na jego mapie. Na właściwym hexie gracz kopie —
zdaje test <b>Dochodzenie</b>. Jeśli ustawiłeś strażnika, najpierw walka. Skarb <b>nigdy nie jest
pusty</b>: zawsze wypłaca złoto (jest minimalny próg) i łup, a im więcej części miała mapa, tym
<b>hojniejsza wypłata</b> (więcej złota, dodatkowe losowania łupu, wyższy tier).</p>
<p class="muted">Liczby (próg złota, DC kopania, mnożniki wypłaty za liczbę części, wagi w tabelach
łupów) to wartości startowe — będą strojone po obserwacji rozgrywki.</p>`,
      },
      {
        id: 'narrator',
        title: 'Jak narrator (AI) korzysta z lokacji',
        body: `
<p>Przy każdej turze narrator dostaje opis okolicy — lokacje wokół miejsca, w którym stoi
gracz (rodzic, podlokacje, sąsiedztwo). Do tego opisu wchodzą lokacje <b>aktywne
i zatwierdzone</b>, z jednym wyjątkiem: <b>miejsce, w którym gracz aktualnie stoi, wchodzi
zawsze</b> — nawet niezatwierdzone.</p>
<p>Z tego wynika najważniejsza zasada:</p>
<p><b>Kolejka „Do zatwierdzenia" to porządkowanie świata wstecz, nie bramka.</b>
Gdy narrator wymyśli „Kuźnię Bartha" w trakcie sesji, gracz wchodzi do niej od razu —
zanim zobaczysz ją w kolejce. Twoja decyzja porządkuje świat na przyszłość, ale nie cofa
tego, co już się wydarzyło.</p>
<ul>
<li><b>Niezatwierdzona</b> — działa tylko „na chwilę": gracz może w niej być, ale narrator
nie proponuje jej w opisie okolicy i nie działa jako cel ruchu z sąsiednich miejsc.</li>
<li><b>Zatwierdzona (✓)</b> — istnieje na stałe: pojawia się w opisie okolicy, gracze mogą wracać.</li>
<li><b>Odrzucona (✕)</b> — narrator jej nie proponuje; jeśli gracz akurat w niej stoi,
scena dokończy się normalnie.</li>
<li><b>Kanoniczna (★)</b> — dodatkowo: podpis na mapie gracza od początku gry, pula
startowa nowych kampanii, cele podróży.</li>
</ul>
<p>Na mapie gracza lokacje nie mają osobnej „ikony oczekiwania" — hex wygląda normalnie.
Jedyną różnicę robi kanon (etykieta widoczna przed odkryciem).</p>`,
      },
      {
        id: 'sciaga',
        title: 'Ściąga decyzyjna',
        body: `
<p>Otwierasz <b>Mapa → Do zatwierdzenia</b>, przykładowe pozycje:</p>
<table class="data-table" style="font-size:0.82rem">
<thead><tr><th>Sytuacja</th><th>Decyzja</th></tr></thead>
<tbody>
<tr><td>„Karczma Pod Krukiem" — narrator wymyślił w sesji, gracze byli, pasuje do świata</td>
<td><b>✓ Zatwierdź</b></td></tr>
<tr><td>„Trzcinowisko" — osada z szablonu, ważny punkt regionu</td>
<td><b>★ Kanon</b> + zaznacz podlokacje w checkliście; potem sprawdź <b>⚓ Floating</b>
i <b>⚓ Osadź</b> na pasującym terenie</td></tr>
<tr><td>„Tajemnicza jaskinia" — wątek umarł, nikt nie wróci</td>
<td><b>✕</b>; jak zaśmieca bazę → <b>Lokacje</b> → <b>✕</b> (trwałe usunięcie)</td></tr>
<tr><td>„Chata zielarki" — gracz w niej stoi TERAZ</td>
<td><b>✓ Zatwierdź</b> (odrzucanie miejsca, w którym stoi gracz, psuje narrację)</td></tr>
<tr><td>Druga „Gospoda szlaku" o tej samej nazwie</td>
<td>nie zatwierdzaj — <b>🧹 Duplikaty</b> → <b>Scal</b></td></tr>
</tbody>
</table>
<p>Reguły kciuka:</p>
<ul>
<li>AI wymyśliło i było w grze używane → <b>✓ Zatwierdź</b>.</li>
<li>Stały punkt świata / start kampanii / podpis na mapie → <b>★ Kanon</b>.</li>
<li>Martwy pomysł → <b>✕</b>. Śmieć → usuń w <b>Lokacje</b> lub <b>🧹 Duplikaty</b>.</li>
<li>Zatwierdzone ≠ na mapie: <b>⚓ Floating</b> → <b>⚓ Osadź</b>.</li>
<li>Teren zmieniasz tylko w budowniczym; po dobrej edycji <b>💾 Zapisz mapę (kanon)</b>.</li>
</ul>`,
      },
    ],
  },
  { ico: '⚙', label: 'Mechanika',  chapters: [{ id: 'mechanika',  title: 'Statystyki, umiejętności, DC, trudność spotkań', body: `
<h3>🎚 Trudność spotkań</h3>
<p>Karta <b>Trudność spotkań</b> (na górze zakładki <b>Mechanika</b>) steruje siłą i liczebnością
wrogów w losowych zasadzkach podczas <b>podróży po mapie</b>. Zmiana działa od razu, bez wdrożenia.</p>
<ul>
<li><b>Preset</b> — <b>Łatwy</b> / <b>Normalny</b> / <b>Trudny</b> / <b>Hardcore</b>. Jeden klik ustawia mnożnik
i zapisuje. Aktywny preset jest podświetlony.</li>
<li><b>Mnożnik</b> — ręczna wartość (0.25–3.0). Skaluje „budżet zagrożenia": im wyżej, tym silniejsza
grupa (wataha, herszt z poplecznikami) na ten sam poziom bohatera. Po zmianie kliknij <b>Zapisz</b>.</li>
<li><b>Zaawansowane</b> — budżet bazowy, przyrost na punkt Power bohatera, minimalny rozmiar puli wrogów,
kara za powtórki tego samego składu. Rusz tylko gdy wiesz, co robisz — presety zwykle wystarczą.</li>
<li><b>Podgląd składu</b> — wybierz poziom bohatera i teren (np. <code>road</code>, <code>forest</code>),
kliknij <b>Losuj skład</b> i zobacz 3 przykładowe grupy, które gra by wygenerowała. Sprawdź efekt
suwaka zanim zapiszesz.</li>
</ul>
<p>Skala celuje w <b>Power Score</b> bohatera (ekwipunek, rangi, czary), nie w sam poziom — rozbudowana
postać dostaje twardsze spotkania automatycznie. Na dole skali (poziom 1) skład zostaje pojedynczym
słabym wrogiem, żeby świeży gracz nie oberwał watahą na starcie.</p>
<p>Zakładki poniżej (Statystyki, Umiejętności, Poziomy DC, Kondycje, Archetypy, Nagrody XP) to definicje
systemowe — edytuj nazwę/opis/wartości, klucze są zablokowane.</p>` }] },
  { ico: '⛓', label: 'Lochy',      chapters: [{ id: 'lochy',      title: 'Ziarna lochów i przebiegi', body: STUB }] },
  { ico: '⚒', label: 'Kuźnia',     chapters: [{ id: 'kuznia',     title: 'Szablony przygód', body: STUB }] },
  { ico: '🛠', label: 'Narzędzia',  chapters: [{ id: 'narzedzia',  title: 'Test Runner i narzędzia bazy', body: STUB }] },
  { ico: '⎔', label: 'System',     chapters: [{ id: 'system',     title: 'Presety LLM i konfiguracja', body: `
<h3>Szybkie akcje (chipy)</h3>
<p>W zakładce <b>System → LLM</b>, w karcie <b>⚡ Szybkie akcje (chipy)</b>, sterujesz podpowiedziami akcji,
które pojawiają się graczowi pod polem tekstowym.</p>
<ul>
<li><b>Włącz chipy generowane przez LLM</b> — narrator sam proponuje 1–3 oczywiste akcje sceny
(np. „Przeszukaj ciała", „Porozmawiaj z karczmarzem"). Wyłączenie zostawia tylko chipy regułowe
(podróż, odpoczynek, usługi) — te są widoczne zawsze, niezależnie od tego przełącznika.</li>
<li><b>Maks. chipów LLM</b> — ile takich podpowiedzi maks. dołożyć (wartość startowa: 3).</li>
</ul>
<p>System twardo odrzuca sugestie, które zdradzałyby rozwiązanie zagadki, hasło albo wynik testu —
chipy mają podpowiadać oczywistości, nie wyręczać gracza. Każdy gracz może też wyłączyć te chipy
u siebie w <b>Profilu → Rozgrywka → Szybkie akcje</b>.</p>
` }] },
];

function _esc(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

export async function init(panel) {
  const toc = GRUPY.map(g => `
    <div style="font-size:0.7rem;font-weight:700;color:var(--t3);letter-spacing:0.06em;padding:10px 10px 3px">${_esc(g.ico)} ${_esc(g.label.toUpperCase())}</div>
    ${g.chapters.map(r =>
      `<a href="#" class="man-toc-link" data-target="man-${r.id}"
          style="display:block;padding:4px 10px 4px 22px;border-radius:5px;color:var(--t2);text-decoration:none;font-size:0.8rem;line-height:1.3">${_esc(r.title)}</a>`
    ).join('')}`
  ).join('');

  const content = GRUPY.map(g => `
    <div style="display:flex;align-items:center;gap:8px;margin:22px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--border)">
      <span style="font-size:1.1rem">${_esc(g.ico)}</span>
      <span style="font-size:0.95rem;font-weight:700;letter-spacing:0.02em">${_esc(g.label)}</span>
    </div>
    ${g.chapters.map(r => `
      <section id="man-${r.id}" class="card" style="padding:18px 22px;margin-bottom:14px;scroll-margin-top:12px">
        <h3 style="margin:0 0 10px;font-size:1.02rem">${_esc(r.title)}</h3>
        <div class="man-body" style="font-size:0.86rem;line-height:1.55;color:var(--t1)">${r.body}</div>
      </section>`).join('')}`
  ).join('');

  panel.innerHTML = `
    <div class="section-head">
      <div>
        <div class="section-title">Instrukcja</div>
        <div class="section-sub">Podręcznik administratora gry — jak zarządzać światem z panelu</div>
      </div>
    </div>
    <div style="display:flex;gap:16px;align-items:flex-start">
      <nav class="card" style="width:240px;flex-shrink:0;padding:6px 8px 12px;position:sticky;top:12px;max-height:calc(100vh - 40px);overflow-y:auto">
        <div style="font-size:0.68rem;font-weight:700;color:var(--t3);letter-spacing:0.08em;padding:8px 10px 2px">SPIS TREŚCI</div>
        ${toc}
      </nav>
      <div style="flex:1;min-width:0" id="man-content">${content}</div>
    </div>`;

  // Styl treści rozdziałów (h4, listy, tabele) — lokalny, bez dotykania layout.css.
  const style = document.createElement('style');
  style.textContent = `
    .man-body h4 { margin:16px 0 6px; font-size:0.88rem; color:var(--text); }
    .man-body p { margin:6px 0; }
    .man-body ul, .man-body ol { margin:6px 0 6px 4px; padding-left:20px; }
    .man-body li { margin:3px 0; }
    .man-body code { background:var(--bg3,#1a1a22); padding:1px 5px; border-radius:4px; font-size:0.78rem; }
    .man-body table { margin:8px 0; }
    .man-body td, .man-body th { padding:6px 10px; }
    .man-toc-link:hover { background:var(--bg3,#1a1a22); color:var(--text); }
  `;
  panel.appendChild(style);

  panel.addEventListener('click', e => {
    const link = e.target.closest('.man-toc-link');
    if (!link) return;
    e.preventDefault();
    document.getElementById(link.dataset.target)?.scrollIntoView({ behavior: 'smooth' });
  });
}
