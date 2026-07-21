/**
 * feature_index.js — Katalog funkcji panelu admina dla wyszukiwarki (command_palette).
 *
 * Każdy wpis = jedna funkcja, którą admin może chcieć znaleźć:
 *   { section, sectionLabel, tab, title, desc, keywords }
 *
 *   section       — klucz sekcji (hash bez #), musi być w SECTIONS w index.html
 *   sectionLabel  — etykieta sekcji (badge w wynikach)
 *   tab           — klucz podzakładki do auto-otwarcia (dowolny atrybut data-* na
 *                   przycisku .stab). null = brak / funkcja poza podzakładką LUB
 *                   zakładka wymagająca wyboru encji (drawer gracza, modal kampanii,
 *                   drawer bohatera) — wtedy ląduje na sekcji, admin wybiera encję.
 *   title         — krótka nazwa funkcji (to głównie po tym szukamy)
 *   desc          — jedno zdanie: do czego służy (pokazywane w wyniku)
 *   keywords      — dodatkowe frazy/synonimy/warianty bez ogonków i po angielsku
 *
 * Utrzymanie: dodajesz funkcję do panelu → dopisz tu wpis (patrz też manual.js).
 */
export const FEATURE_INDEX = [
  // ── Przegląd ────────────────────────────────────────────────────────────────
  { section:'overview', sectionLabel:'Przegląd', tab:null, title:'Przegląd / Dashboard', desc:'Kafelki: kampanie, gracze, tury dziś, rozmiar bazy, feed tur i zmian treści.', keywords:'overview dashboard start glowna kokpit statystyki kafelki' },
  { section:'overview', sectionLabel:'Przegląd', tab:null, title:'Ekonomia 7 dni', desc:'Przepływ złota per źródło — wpływy, wydatki, bilans z ostatniego tygodnia.', keywords:'ekonomia zloto gold przeplyw bilans gospodarka' },
  { section:'overview', sectionLabel:'Przegląd', tab:'dice', title:'Rozkład rzutów kością', desc:'Statystyki d20: liczba natów, średnia, rozkład wyników.', keywords:'kosci dice d20 nat rzuty rozklad' },
  { section:'overview', sectionLabel:'Przegląd', tab:'combat', title:'Statystyki walki', desc:'Najczęściej zabijani wrogowie i najgroźniejsi przeciwnicy graczy.', keywords:'walka combat wrogowie zabici smierc' },

  // ── Gracze ──────────────────────────────────────────────────────────────────
  { section:'players', sectionLabel:'Gracze', tab:null, title:'Konta graczy', desc:'Lista wszystkich kont: rola, aktywność, model LLM; tworzenie i masowe akcje.', keywords:'gracze uzytkownicy konta users accounts lista' },
  { section:'players', sectionLabel:'Gracze', tab:null, title:'Nowe konto gracza', desc:'Ręczne utworzenie konta: login, hasło, nazwa, flaga administratora.', keywords:'nowy gracz konto rejestracja dodaj uzytkownika create user' },
  { section:'players', sectionLabel:'Gracze', tab:null, title:'Ustawienia LLM gracza', desc:'Własny model gracza: dostawca, Base URL, model, API Key (drawer → LLM).', keywords:'llm model gracza custom provider api key ustawienia' },
  { section:'players', sectionLabel:'Gracze', tab:null, title:'Reset hasła gracza', desc:'Ustawienie nowego hasła konta z panelu (drawer gracza → Info).', keywords:'haslo password reset zmien haslo' },
  { section:'players', sectionLabel:'Gracze', tab:null, title:'Zablokuj / odblokuj konto', desc:'Blokada logowania bez usuwania konta (drawer gracza → Info, strefa niebezpieczna).', keywords:'blokada ban zablokuj odblokuj konto lock' },
  { section:'players', sectionLabel:'Gracze', tab:null, title:'Wskrzeszenia gracza (limit)', desc:'Ustawianie liczby lub trybu nieograniczonego wskrzeszeń gracza (drawer → Kampanie).', keywords:'wskrzeszenie resurrection limit rezurekcja ozywienie' },
  { section:'players', sectionLabel:'Gracze', tab:null, title:'Flaga Tester', desc:'Oznaczenie konta jako tester (drawer gracza → Info).', keywords:'tester flaga rola testerzy' },

  // ── Kampanie ────────────────────────────────────────────────────────────────
  { section:'campaigns', sectionLabel:'Kampanie', tab:null, title:'Monitor kampanii', desc:'Lista żywych kampanii (tabela/karty), filtry statusu, usuwanie, wskrzeszanie.', keywords:'kampanie campaigns monitor lista gry sesje' },
  { section:'campaigns', sectionLabel:'Kampanie', tab:null, title:'Usuń kampanię', desc:'Kasowanie pojedynczej lub wielu kampanii (bohater zostaje uwolniony).', keywords:'usun kampanie delete kasuj skasuj' },
  { section:'campaigns', sectionLabel:'Kampanie', tab:null, title:'Plan GM kampanii', desc:'Podgląd i regeneracja planu MG: akty, sceny, hooki, roadmapa, zakończenia (modal → Plan GM).', keywords:'plan gm mg gravity story regeneruj sceny akty luki roadmapa' },
  { section:'campaigns', sectionLabel:'Kampanie', tab:null, title:'Cofnij do tury (rollback)', desc:'Przywrócenie pełnego stanu gry ze snapshotu wybranej tury (modal → Tury).', keywords:'rollback cofnij tura snapshot przywroc undo' },
  { section:'campaigns', sectionLabel:'Kampanie', tab:null, title:'Komendy debug (/debug)', desc:'Konsola komend na kampanii: set-hp, xp add/set, roll, set-state (modal → Przegląd).', keywords:'debug komendy cheat set-hp xp roll set-state konsola' },
  { section:'campaigns', sectionLabel:'Kampanie', tab:null, title:'Mapa heksowa kampanii', desc:'Hex mapa z pozycją i mgłą wojny; edycja heksu: teren, odkryty, notatki GM (modal → Mapa).', keywords:'mapa hex heksy fog fow pozycja pin kampania' },
  { section:'campaigns', sectionLabel:'Kampanie', tab:null, title:'Warsztat kampanii (czat AI)', desc:'Rozmowa z AI o kampanii i zmianach w planie MG; wstrzykiwanie spotkań (modal → Warsztat).', keywords:'warsztat workshop czat ai plan zmiany wstrzyknij spotkanie' },
  { section:'campaigns', sectionLabel:'Kampanie', tab:null, title:'Inspektor bohatera (na żywo)', desc:'Podgląd co 1s: intent gracza, wynik bramki (gate), stan świata (modal → Inspector).', keywords:'inspektor inspector intent gate bramka live podglad' },

  // ── Bohaterowie ─────────────────────────────────────────────────────────────
  { section:'heroes', sectionLabel:'Bohaterowie', tab:null, title:'Bohaterowie (lista)', desc:'Wszyscy bohaterowie: wolni / w grze, wyszukiwanie, usuwanie, wymuś edycję.', keywords:'bohaterowie postacie heroes characters lista gracze' },
  { section:'heroes', sectionLabel:'Bohaterowie', tab:null, title:'Arkusz bohatera (edycja liczb)', desc:'HP, mana, poziom, złoto, XP, statystyki, umiejętności, kondycje (drawer → Arkusz).', keywords:'arkusz sheet hp mana poziom zloto xp staty edycja liczb' },
  { section:'heroes', sectionLabel:'Bohaterowie', tab:null, title:'Ekwipunek bohatera', desc:'Dodawanie z katalogu, usuwanie, zakładanie/zdejmowanie przedmiotów (drawer → Ekwipunek).', keywords:'ekwipunek inventory przedmioty zaloz zdejmij plecak' },
  { section:'heroes', sectionLabel:'Bohaterowie', tab:null, title:'Zaklęcia bohatera', desc:'Nauka nowych zaklęć i awans rangi (drawer → Zaklęcia).', keywords:'zaklecia czary spells nauka ranga mag' },
  { section:'heroes', sectionLabel:'Bohaterowie', tab:null, title:'Questy bohatera', desc:'Dodawanie questów i oznaczanie jako zaliczone (drawer → Questy).', keywords:'questy quests zadania misje zalicz' },

  // ── Przedmioty (Zawartość) ──────────────────────────────────────────────────
  { section:'content', sectionLabel:'Przedmioty', tab:'weapons', title:'Broń', desc:'Tabela broni: typ, obrażenia, zasięg, slot, oburęczność, finezja, cena, rzadkość.', keywords:'bron weapons oren miecz obrazenia dmg' },
  { section:'content', sectionLabel:'Przedmioty', tab:'armor', title:'Zbroja', desc:'Tabela zbroi: bonus AC, pokrycie, waga, cena, efekty on-equip.', keywords:'zbroja armor pancerz ac obrona' },
  { section:'content', sectionLabel:'Przedmioty', tab:'items', title:'Przedmioty', desc:'Przedmioty niebojowe: narzędzia, magiczne, questowe, relikty; efekt JSON.', keywords:'przedmioty items rzeczy relikty narzedzia questowe' },
  { section:'content', sectionLabel:'Przedmioty', tab:'consumables', title:'Konsumable', desc:'Mikstury/konsumable: efekt, formuła kości, ładunki, cena, edytor on-use.', keywords:'konsumable mikstury potion eliksir jedzenie consumables' },
  { section:'content', sectionLabel:'Przedmioty', tab:'loot', title:'Tabele łupów', desc:'Definicje tabel łupów: złoto min/max, wpisy, podgląd i usuwanie.', keywords:'tabele lupow loot drop lup zloto nagrody' },
  { section:'content', sectionLabel:'Przedmioty', tab:'spells', title:'Czary', desc:'Tabela czarów: szkoła, rasa, tier, koszt many, obrażenia, leczenie, strefa.', keywords:'czary spells zaklecia mag mana szkola tier' },
  { section:'content', sectionLabel:'Przedmioty', tab:'affixes', title:'Afiksy', desc:'Afiksy przedmiotów: tier, typ, efekty — modyfikatory generowanego ekwipunku.', keywords:'afiksy affixes modyfikatory sufiks prefiks magiczne' },
  { section:'content', sectionLabel:'Przedmioty', tab:'recipes', title:'Przepisy rzemiosła', desc:'Przepisy craftingu: rzemieślnik, wynik, składniki, opłata.', keywords:'przepisy recipes rzemioslo crafting kowal skladniki' },
  { section:'content', sectionLabel:'Przedmioty', tab:'sets', title:'Sety ekwipunku', desc:'Komplety z bonusami za progi części; „Kto nosi".', keywords:'sety sets komplet bonus set part' },
  { section:'content', sectionLabel:'Przedmioty', tab:'duplicates', title:'Duplikaty treści', desc:'Wykrywanie i scalanie duplikatów przedmiotów, konsumabli, broni.', keywords:'duplikaty duplicates scalanie merge powtorki' },
  { section:'content', sectionLabel:'Przedmioty', tab:null, title:'Kreator AI (Smart Entry)', desc:'AI tworzy nowe rekordy (broń, przedmiot, wróg…) z opisu — przycisk 🤖 Kreator AI.', keywords:'kreator ai smart entry generuj tworzenie nowy rekord' },

  // ── Świat ───────────────────────────────────────────────────────────────────
  { section:'world', sectionLabel:'Świat', tab:'npcs', title:'NPC', desc:'Tabela NPC: nastawienie, lokacja, rola; portrety i ekwipunek sklepu kupców.', keywords:'npc postacie niezalezne kupiec sklep portrety nastawienie' },
  { section:'world', sectionLabel:'Świat', tab:'enemies', title:'Wrogowie', desc:'Tabela wrogów: tier, min. poziom, HP, kość obrażeń, tabela łupów, drop %.', keywords:'wrogowie enemies przeciwnicy potwory bestie hp tier' },
  { section:'world', sectionLabel:'Świat', tab:'loot', title:'Tabele łupów bestiariusza', desc:'Zarządzanie tabelami łupów wrogów: wpisy, szansa/waga, min/max sztuk.', keywords:'tabele lupow bestiariusz loot drop wrogowie' },
  { section:'world', sectionLabel:'Świat', tab:'events', title:'Wydarzenia regionalne', desc:'Żywy świat: jarmark, zaraza, rajdy, susza — wpływ na ceny, spotkania, podróż.', keywords:'wydarzenia events zywy swiat jarmark zaraza rajdy pogoda region' },
  { section:'world', sectionLabel:'Świat', tab:'lint', title:'🩺 Kontrola świata', desc:'Lista rozjazdów w świecie (usługa bez gospodarza, sieroty obsady, heks bez lokacji, zepsuty rodzic, duplikaty) + guzik Napraw i kronika napraw.', keywords:'kontrola swiata lint rozjazdy naprawa integralnosc gospodarz sieroty duplikaty kronika napraw diagnostyka' },
  { section:'world', sectionLabel:'Świat', tab:'pending', title:'Oczekujące (do zatwierdzenia)', desc:'Kolejka rekordów do zatwierdzenia: NPC, wrogowie, bronie, przedmioty, lokacje.', keywords:'oczekujace pending do zatwierdzenia kolejka zatwierdz odrzuc review' },

  // ── Mapa ────────────────────────────────────────────────────────────────────
  { section:'map', sectionLabel:'Mapa', tab:'builder', title:'Budowniczy mapy (hex)', desc:'Edytor mapy heksagonalnej: malowanie terenu, cofanie, zapis/wczytanie kanonu.', keywords:'mapa map hex heksy budowniczy edytor teren malowanie kanon' },
  { section:'map', sectionLabel:'Mapa', tab:'generate', title:'Ustawienia mapy', desc:'Licznik heksów świata i zasięg mgły wojny (bąbel wiedzy). Generator świata usunięty (#1482).', keywords:'ustawienia mapy fow mgla wojny babel wiedzy zasieg heksy licznik' },
  { section:'map', sectionLabel:'Mapa', tab:'locations', title:'Lokacje', desc:'Drzewo lokacji rodzic/dziecko: filtry, usuwanie, przypisywanie NPC/wrogów, obrazy.', keywords:'lokacje locations miejsca osady drzewo hierarchia' },
  { section:'map', sectionLabel:'Mapa', tab:'floating', title:'Floating (niezakotwiczone lokacje)', desc:'Lokacje w bazie nieumieszczone na hexach — ręczne osadzanie na q,r.', keywords:'floating niezakotwiczone kotwica osadz hex qr wiszace' },
  { section:'map', sectionLabel:'Mapa', tab:'terrain', title:'Typy terenu', desc:'Tabela terenów: waga spawnu, czas podróży, szansa spotkań, podmapa.', keywords:'teren terrain typy podroz spotkania biom' },
  { section:'map', sectionLabel:'Mapa', tab:'review', title:'Do zatwierdzenia (lokacje)', desc:'Kolejka lokacji: zatwierdź / ★ Kanon / odrzuć; heksy z możliwą podmapą.', keywords:'do zatwierdzenia review lokacje kanon zatwierdz podmapa' },
  { section:'map', sectionLabel:'Mapa', tab:'duplicates', title:'Duplikaty lokacji', desc:'Skaner duplikatów lokacji (scalanie) i sprzątanie śmieci testowych/osieroconych.', keywords:'duplikaty lokacji scalanie merge smieci sprzatanie cleanup' },

  // ── Mechanika ───────────────────────────────────────────────────────────────
  { section:'mechanics', sectionLabel:'Mechanika', tab:'stats', title:'Statystyki (STR/DEX…)', desc:'Systemowe staty postaci z edycją nazwy i opisu.', keywords:'statystyki staty stats str dex con int wis cha lck atrybuty' },
  { section:'mechanics', sectionLabel:'Mechanika', tab:'skills', title:'Umiejętności', desc:'Umiejętności: powiązana stat, maks. rang, słowa kluczowe, koszt XP per ranga.', keywords:'umiejetnosci skills skille trigger keywords koszt xp ranga' },
  { section:'mechanics', sectionLabel:'Mechanika', tab:'dc', title:'Poziomy DC', desc:'Progi trudności testów (Easy/Medium/Hard/Extreme…) z edycją.', keywords:'dc trudnosc progi difficulty test' },
  { section:'mechanics', sectionLabel:'Mechanika', tab:'conditions', title:'Kondycje (stany)', desc:'Stany: efekt JSON, kumulowalność, auto-usuwanie, aktywność.', keywords:'kondycje stany conditions status efekty zatrucie ogluszenie' },
  { section:'mechanics', sectionLabel:'Mechanika', tab:'archetypes', title:'Archetypy (klasy)', desc:'Klasy postaci: HP bazowe, złoto startowe.', keywords:'archetypy klasy classes wojownik mag hp startowe' },
  { section:'mechanics', sectionLabel:'Mechanika', tab:'xp', title:'Nagrody XP', desc:'Katalog zdarzeń dających XP z przełącznikiem aktywności i edycją kwoty.', keywords:'xp doswiadczenie nagrody rewards awans' },
  { section:'mechanics', sectionLabel:'Mechanika', tab:null, title:'Częstotliwość spotkań', desc:'Interwał spokojnych tur w dziczy i spadek szansy przy osiedleniu.', keywords:'spotkania encounter czestotliwosc interwal dzicz losowe' },

  // ── Księga Zasad ────────────────────────────────────────────────────────────
  { section:'game-mechanics', sectionLabel:'Księga Zasad', tab:null, title:'Księga Zasad', desc:'Interaktywny podręcznik gracza (/rules/) osadzony w panelu, z trybem edycji.', keywords:'ksiega zasad rules podrecznik reguly manual gracza' },

  // ── Lochy ───────────────────────────────────────────────────────────────────
  { section:'dungeons', sectionLabel:'Lochy', tab:'dungeons', title:'Lochy (seedy)', desc:'Farmowalne lochy: poziom, tryb, cooldown, biegi; edycja i usuwanie.', keywords:'lochy dungeons loch seed cooldown farm podziemia' },
  { section:'dungeons', sectionLabel:'Lochy', tab:'riddles', title:'Zagadki', desc:'Zagadki lochów: treść, odpowiedź, motyw, trudność, podpowiedzi.', keywords:'zagadki riddles zagadka riddle podpowiedzi trudnosc' },
  { section:'dungeons', sectionLabel:'Lochy', tab:'tiles', title:'Kafelki lochów', desc:'Siatka kafelków (Dungeon Tile): obraz AI, drzwi N/S/E/W, wrogowie, łup, zagadka, boss.', keywords:'kafelki tiles kafelek plansza drzwi kompas boss' },
  { section:'dungeons', sectionLabel:'Lochy', tab:'tilecats', title:'Kategorie kafelków', desc:'Kategorie kafelków: klucz, nazwa, styl promptu, aktywność.', keywords:'kategorie kafelkow tilecats kategoria styl prompt' },
  { section:'dungeons', sectionLabel:'Lochy', tab:null, title:'Nowy loch', desc:'Modal tworzenia lochu: min. poziom, cooldown, atmosfera, kategoria/liczba kafelków, boss.', keywords:'nowy loch dodaj dungeon utworz create' },

  // ── Kuźnia ──────────────────────────────────────────────────────────────────
  { section:'forge', sectionLabel:'Kuźnia', tab:'agent', title:'Agent AI (Warsztat przygód)', desc:'Czat z AI budujący strukturę przygody + edytowalny szkic; zapisane pomysły.', keywords:'kuznia forge agent ai warsztat przygoda pomysly szkic' },
  { section:'forge', sectionLabel:'Kuźnia', tab:'hooks', title:'Haki (hooks)', desc:'Siatka haków (broń, wróg, NPC, lokacja, przedmiot) z filtrem statusu i typu.', keywords:'haki hooks zaczepy hak przygoda' },
  { section:'forge', sectionLabel:'Kuźnia', tab:'templates', title:'Szablony kampanii', desc:'Tworzenie szablonów kampanii, edytor (akty, postaci, lokacje, zakończenia, przedmioty), publikacja.', keywords:'szablony templates szablon kampania adventure forge publikacja' },
  { section:'forge', sectionLabel:'Kuźnia', tab:'encounters', title:'Spotkania (encounters)', desc:'Siatka spotkań z haków; wstrzykiwanie do aktywnej kampanii.', keywords:'spotkania encounters encounter wstrzyknij' },
  { section:'forge', sectionLabel:'Kuźnia', tab:'catalog', title:'Katalog spotkań', desc:'game_config_encounters: filtr bojowe/społeczne, biom/subtyp, generowanie AI.', keywords:'katalog spotkan encounters catalog biom generuj' },

  // ── Zaproszenia ─────────────────────────────────────────────────────────────
  { section:'invites', sectionLabel:'Zaproszenia', tab:null, title:'Kody zaproszeń', desc:'Generator kodu: nadawca, e-mail, limit użyć, treść; lista aktywnych i odwołanie.', keywords:'zaproszenia invites kody invite code zapros link' },
  { section:'invites', sectionLabel:'Zaproszenia', tab:null, title:'Drzewo graczy (genealogia)', desc:'Interaktywne drzewo D3 genealogii zaproszeń z kolorami aktywności.', keywords:'drzewo graczy genealogia zaproszenia tree referral' },

  // ── Zgłoszenia ──────────────────────────────────────────────────────────────
  { section:'bugreports', sectionLabel:'Zgłoszenia', tab:null, title:'Zgłoszenia błędów', desc:'Raporty błędów/sugestii testerów z kontekstem sesji; sync z GitHub.', keywords:'zgloszenia bugi bugreports bledy raporty testerzy github sync' },

  // ── Push ────────────────────────────────────────────────────────────────────
  { section:'push', sectionLabel:'Push', tab:null, title:'Powiadomienia push', desc:'Subskrypcje push graczy i wysyłka testowego powiadomienia.', keywords:'push powiadomienia notyfikacje notifications web push test' },

  // ── Narzędzia ───────────────────────────────────────────────────────────────
  { section:'tools', sectionLabel:'Narzędzia', tab:'runner', title:'Test Runner', desc:'Uruchamianie zestawów testowych scenariuszy na stacku DEV.', keywords:'test runner testy scenariusze uruchom' },
  { section:'tools', sectionLabel:'Narzędzia', tab:'combat', title:'Combat Sandbox', desc:'Testowa arena walki na prawdziwym silniku: bohater vs wrogowie, ataki, tura.', keywords:'sandbox walka combat arena test silnik' },
  { section:'tools', sectionLabel:'Narzędzia', tab:'rest', title:'Rest Sandbox', desc:'Test mechaniki odpoczynku: obóz, krótki/długi odpoczynek, spotkania, reset HP.', keywords:'rest odpoczynek oboz sandbox test hp' },
  { section:'tools', sectionLabel:'Narzędzia', tab:'knowledge', title:'Księga Wiedzy (CMS)', desc:'CMS wskazówek gry / onboardingu: dodawanie, edycja, kategorie, kolejność.', keywords:'wiedza knowledge cms wskazowki onboarding tipy' },
  { section:'tools', sectionLabel:'Narzędzia', tab:'mcp', title:'MCP (serwer narzędzi)', desc:'Konfiguracja serwera MCP: lista narzędzi, przypięcie sesji, live iframe.', keywords:'mcp serwer narzedzia claude tools sesja' },
  { section:'tools', sectionLabel:'Narzędzia', tab:'images', title:'Generator obrazów', desc:'Generator obrazów AI z presetami: kafelek lochu, portret wroga, przedmiot, ikona.', keywords:'obrazy images generator ai portret grafika ilustracje flux' },
  { section:'tools', sectionLabel:'Narzędzia', tab:'playwright', title:'Playwright (regresja)', desc:'Lista i uruchamianie spec-ów Playwright (regresja/acceptance/admin) z live logiem.', keywords:'playwright regresja e2e spec testy ui' },
  { section:'tools', sectionLabel:'Narzędzia', tab:'dblint', title:'DB Lint', desc:'Audyt integralności bazy: wiszące FK, brakujące pola, wartości poza zakresem.', keywords:'db lint baza audyt integralnosc fk migracje' },

  // ── System ──────────────────────────────────────────────────────────────────
  { section:'system', sectionLabel:'System', tab:'llm', title:'Presety LLM', desc:'Zarządzanie presetami LLM (aktywacja, edycja) i lokalnym LLM do treści.', keywords:'llm presety preset model dostawca provider ai konfiguracja' },
  { section:'system', sectionLabel:'System', tab:'database', title:'Baza danych', desc:'Info o bazie, backup, migracje, przywracanie z pliku .db.', keywords:'baza database backup migracje przywroc restore db' },
  { section:'system', sectionLabel:'System', tab:'config', title:'Eksport/import konfiguracji', desc:'Eksport/import konfiguracji gry (JSON) z dry-run i auto-backupem.', keywords:'config konfiguracja eksport import json seed backup' },
  { section:'system', sectionLabel:'System', tab:'slash', title:'Slash Commands', desc:'Edycja komend czatu (/…): alias, widoczność, opis w /help.', keywords:'slash commands komendy czat help alias' },
  { section:'system', sectionLabel:'System', tab:'resurrection', title:'Wskrzeszenie (globalne)', desc:'Globalna konfiguracja wskrzeszania: tryb kosztu, limity, cap_percent.', keywords:'wskrzeszenie resurrection globalne koszt limit cap' },
  { section:'system', sectionLabel:'System', tab:'email', title:'Email / SMTP', desc:'Ustawienia SMTP, test e-mail, przełącznik otwartej rejestracji.', keywords:'email smtp mail rejestracja test poczta' },
  { section:'system', sectionLabel:'System', tab:'visual', title:'Wygląd (tła ekranów)', desc:'Konfiguracja pory dnia (tło/ramka) i teł ekranów UI gracza.', keywords:'wyglad visual tla pora dnia ramka ekrany theme' },
  { section:'system', sectionLabel:'System', tab:'teksty', title:'Teksty UI (CMS)', desc:'CMS tekstów interfejsu gracza z filtrem po ekranie.', keywords:'teksty texts cms interfejs ui napisy' },
  { section:'system', sectionLabel:'System', tab:'voice', title:'Głos (TTS/STT)', desc:'Konfiguracja TTS (Piper/F5) i STT (Whisper), serwery głosu, konsola testowa.', keywords:'glos voice tts stt piper whisper mowa lektor' },
  { section:'system', sectionLabel:'System', tab:'narration', title:'Narracja / System prompt', desc:'System prompt GM, ton narracji, Story Gravity, wyłączanie narracji walki.', keywords:'narracja narration system prompt gm ton story gravity' },
  { section:'system', sectionLabel:'System', tab:'gamemodes', title:'Tryby gry', desc:'Włączanie/wyłączanie trybów: Kampania AI, Gotowa, Loch, Multiplayer.', keywords:'tryby gry gamemodes multiplayer kampania loch wlacz' },
  { section:'system', sectionLabel:'System', tab:'imagegen', title:'Serwis obrazów (ComfyUI)', desc:'Konfiguracja generowania obrazów: URL ComfyUI, checkpoint, kroki, rozmiar.', keywords:'imagegen comfyui obrazy serwis checkpoint konfiguracja' },
  { section:'system', sectionLabel:'System', tab:'dice', title:'Kostki 3D (wygląd)', desc:'Wygląd i fizyka kostek 3D: kolory, tekstura, materiał, grawitacja.', keywords:'kostki dice 3d wyglad kolory fizyka grawitacja' },

  // ── Statystyki ──────────────────────────────────────────────────────────────
  { section:'analytics', sectionLabel:'Statystyki', tab:'players', title:'Aktywność graczy', desc:'Tabela aktywnych graczy: postać, kampania, ostatnia aktywność, tury, śmierci.', keywords:'statystyki analytics aktywnosc gracze metryki' },
  { section:'analytics', sectionLabel:'Statystyki', tab:'events', title:'Zdarzenia gry (log)', desc:'Filtrowany log zdarzeń gry (typ, severity, kampania) z podglądem JSON.', keywords:'zdarzenia events log severity dziennik' },
  { section:'analytics', sectionLabel:'Statystyki', tab:'llm', title:'Wydajność LLM', desc:'Statystyki wywołań LLM wg typu i najwolniejsze zapytania (24h/7d/30d).', keywords:'wydajnosc llm latencja performance zapytania statystyki' },
  { section:'analytics', sectionLabel:'Statystyki', tab:'errors', title:'Błędy systemu', desc:'Ostatnie błędy systemu i LLM ze źródłem, typem i detalem.', keywords:'bledy errors awarie logi exception' },

  // ── Wizytówka ───────────────────────────────────────────────────────────────
  { section:'showcase', sectionLabel:'Wizytówka', tab:'historia', title:'Historia projektu (wizytówka)', desc:'Edycja wstępu i etapów historii projektu na /showcase/.', keywords:'wizytowka showcase historia projekt strona' },
  { section:'showcase', sectionLabel:'Wizytówka', tab:'swiat', title:'Świat (wizytówka)', desc:'Edycja wstępu świata i opisów krain na stronie wizytówki.', keywords:'swiat wizytowka krainy opis showcase' },
  { section:'showcase', sectionLabel:'Wizytówka', tab:'faq', title:'FAQ (wizytówka)', desc:'Dodawanie/edycja/kolejność pytań i odpowiedzi FAQ.', keywords:'faq pytania odpowiedzi wizytowka' },
  { section:'showcase', sectionLabel:'Wizytówka', tab:'roadmap', title:'Roadmapa (wizytówka)', desc:'Edycja kolumn i punktów publicznej roadmapy.', keywords:'roadmapa roadmap plan wizytowka' },
  { section:'showcase', sectionLabel:'Wizytówka', tab:'changelog', title:'Changelog (wizytówka)', desc:'Podgląd changelogu wersji (tylko odczyt, z CHANGELOG.md).', keywords:'changelog wersje zmiany historia' },

  // ── Scenariusze / Instrukcja ────────────────────────────────────────────────
  { section:'scenario', sectionLabel:'Scenariusze', tab:null, title:'Scenariusze (sandbox)', desc:'Przygotowanie i uruchamianie scenariuszy testowych na klonie postaci.', keywords:'scenariusze scenario sandbox test przygotuj' },
  { section:'manual', sectionLabel:'Instrukcja', tab:null, title:'Instrukcja admina', desc:'Podręcznik administratora pogrupowany wg zakładek panelu, ze spisem treści.', keywords:'instrukcja manual pomoc podrecznik admin help' },
];
