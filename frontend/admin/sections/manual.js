/**
 * Sekcja „Instrukcja" — podręcznik administratora gry (#1407).
 *
 * Living document: rozdziały w ROZDZIALY[] poniżej, spis treści generowany
 * automatycznie. Konwencja treści:
 *  - nazwy sekcji / zakładek / przycisków DOKŁADNIE jak w UI (kopiuj z kodu,
 *    razem z emoji) — admin nie może zgadywać, o który przycisk chodzi;
 *  - żadnych wzmianek o historii prac / commitach / issue — to manual, nie
 *    changelog;
 *  - nowa funkcjonalność w adminie ⇒ dopisz/zmień rozdział w tym pliku.
 */

const ROZDZIALY = [
  {
    id: 'wstep',
    title: 'Jak korzystać z instrukcji',
    body: `
<p>Ten podręcznik opisuje, jak zarządzać światem gry z poziomu panelu administratora.
Wszystkie nazwy sekcji, zakładek i przycisków są pisane <b>dokładnie tak, jak w panelu</b>
(razem z ikonami), np. przycisk <b>★ Kanon</b> w zakładce <b>Do zatwierdzenia</b> sekcji <b>Mapa</b>.</p>
<p>Rozdziały są niezależne — możesz czytać tylko ten, którego potrzebujesz. Spis treści po lewej.</p>`,
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
„Jak narrator korzysta z lokacji").</p>

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
    title: 'Mapa → Do zatwierdzenia',
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
    title: 'Mapa → ⚓ Floating',
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
<b>Mapa</b>, patrz rozdział „Budowniczy świata").</li>
<li>Współrzędne hexa podejrzysz klikając hex w budowniczym.</li>
</ul>
<h4>👁 Podgląd</h4>
<p>Pełne dane lokacji przed osadzeniem.</p>`,
  },
  {
    id: 'lokacje',
    title: 'Mapa → Lokacje',
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
    title: 'Mapa → 🧹 Duplikaty',
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
    id: 'budowniczy',
    title: 'Mapa → Mapa (budowniczy świata)',
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
<li><b>💾 Zapisz mapę (kanon)</b> — robi zrzut CAŁEJ siatki hexów (teren, etykiety, krainy)
do pliku wzorcowego. Ten zapis przeżywa reset bazy. Rób go po każdej większej ręcznej
edycji mapy, z której jesteś zadowolony.</li>
<li><b>📂 Wczytaj mapę (z kanonu)</b> — przywraca mapę z ostatniego zapisu,
<b>nadpisując bieżącą siatkę</b>.</li>
<li>System odmówi zapisu, gdy mapa wygląda na pustą — ochrona przed nadpisaniem dobrego
wzorca śmieciem.</li>
</ul>
<p>Dla porównania: <b>★ Kanon</b> (w <b>Do zatwierdzenia</b>) oznacza JEDNĄ lokację jako
kanoniczną (drogowskaz, pula startów). <b>💾 Zapisz mapę (kanon)</b> zabezpiecza CAŁY teren świata.</p>`,
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
  {
    id: 'przedmioty',
    title: 'Przedmioty i tabele łupów',
    body: `<p style="color:var(--t3)">Rozdział w przygotowaniu.</p>`,
  },
  {
    id: 'kampanie',
    title: 'Kampanie i Plan GM',
    body: `<p style="color:var(--t3)">Rozdział w przygotowaniu.</p>`,
  },
  {
    id: 'kuznia',
    title: 'Kuźnia — szablony przygód',
    body: `<p style="color:var(--t3)">Rozdział w przygotowaniu.</p>`,
  },
];

function _esc(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

export async function init(panel) {
  const toc = ROZDZIALY.map(r =>
    `<a href="#" class="man-toc-link" data-target="man-${r.id}"
        style="display:block;padding:6px 10px;border-radius:5px;color:var(--t2);text-decoration:none;font-size:0.82rem;line-height:1.3">${_esc(r.title)}</a>`
  ).join('');

  const chapters = ROZDZIALY.map(r => `
    <section id="man-${r.id}" class="card" style="padding:18px 22px;margin-bottom:14px;scroll-margin-top:12px">
      <h3 style="margin:0 0 10px;font-size:1.02rem">${_esc(r.title)}</h3>
      <div class="man-body" style="font-size:0.86rem;line-height:1.55;color:var(--t1)">${r.body}</div>
    </section>`
  ).join('');

  panel.innerHTML = `
    <div class="section-head">
      <div>
        <div class="section-title">Instrukcja</div>
        <div class="section-sub">Podręcznik administratora gry — jak zarządzać światem z panelu</div>
      </div>
    </div>
    <div style="display:flex;gap:16px;align-items:flex-start">
      <nav class="card" style="width:230px;flex-shrink:0;padding:10px;position:sticky;top:12px;max-height:calc(100vh - 40px);overflow-y:auto">
        <div style="font-size:0.68rem;font-weight:700;color:var(--t3);letter-spacing:0.08em;padding:2px 10px 8px">SPIS TREŚCI</div>
        ${toc}
      </nav>
      <div style="flex:1;min-width:0" id="man-content">${chapters}</div>
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
