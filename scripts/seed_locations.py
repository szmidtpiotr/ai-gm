#!/usr/bin/env python3
"""Seed ~150 locations: 30 macro areas + ~4 sub-locations each.
Polish dark-fantasy theme. Idempotent (INSERT OR IGNORE keyed on `key`).
"""
import sqlite3
import sys

sys.path.insert(0, "/app")

from app.services.location_factory import LocationSource, create_location  # noqa: E402

DB_PATH = "/data/ai_gm.db"

# (macro_key, label, biome, tier, safe_for_rest, map_icon, location_subtype,
#  description, [(sub_key, sub_label, sub_subtype, sub_safe, sub_desc), ...])
LOCATIONS = [
    # ── CITIES (5) ─────────────────────────────────────────────────────────
    ("vilnograd_stolica", "Vilnograd, Stolica", "urban", 1, 1, "castle", "city",
     "Wielka, kamienna stolica królestwa o szarych dachach i czarnych dymnych obłokach unoszących się nad dzielnicami rzemieślniczymi. Mury obronne pokrywa stary mech, a strażnicy w niebieskich pelerynach patrolują bramy o każdej godzinie.",
     [
        ("vilnograd_rynek", "Vilnograd: Rynek Główny", "market", 1,
         "Brukowany plac z fontanną z czterema kamiennymi gryfami. Kupcy z różnych krajów krzyczą ceny w pół tuzinie języków."),
        ("vilnograd_zamek", "Vilnograd: Zamek Królewski", "castle", 1,
         "Trzy wieże z czarnego granitu, każda z czerwonym sztandarem. Wartownicy nie pozwalają zbliżyć się bez przepustki."),
        ("vilnograd_tawerna_pod_korona", "Vilnograd: Pod Złotą Koroną", "tavern", 1,
         "Najlepsza karczma w mieście — wino z południa, izba dla każdego, ale ceny dla zamożnych."),
        ("vilnograd_swiatynia_swiatla", "Vilnograd: Świątynia Światła", "temple", 1,
         "Marmurowa świątynia kapłanów Słońca. Witraże rzucają tęczowe smugi na posadzkę o świcie."),
        ("vilnograd_dzielnica_zlodziei", "Vilnograd: Dzielnica Łotrów", "slum", 0,
         "Wąskie zaułki, gdzie nawet straż nie wchodzi po zmroku. Każdy róg może kryć nóż w plecach."),
     ]),
    ("czarnogrod_port", "Czarnogród, Port", "urban", 2, 1, "town", "port-city",
     "Smolisty port pełen wraków, dziwnych ryb i kontrabandy. W mgielne poranki widać tylko maszty kołyszące się w rytm fal.",
     [
        ("czarnogrod_nabrzeze", "Czarnogród: Nabrzeże", "port", 0,
         "Drewniane molo śliskie od ryb i krwi. Cumują tu statki z dalekich krajów — i wraki bez załogi."),
        ("czarnogrod_pod_topielcem", "Czarnogród: Pod Topielcem", "tavern", 1,
         "Najgorsza karczma w mieście — i najtańsza. Tu można nająć przemytnika albo pożegnać się z życiem."),
        ("czarnogrod_giełda_kontrabandy", "Czarnogród: Czarny Targ", "market", 0,
         "Nieoficjalny targ pod molem, gdzie kupisz wszystko — od trucizny po dziecięcego niewolnika."),
        ("czarnogrod_latarnia_topielcow", "Czarnogród: Latarnia Topielców", "ruin", 0,
         "Stara, opuszczona latarnia. Mówią, że nocą zapala się sama i wciąga statki na rafy."),
     ]),
    ("klasztor_iskry_centrum", "Klasztor Iskry, Centrum Wiary", "urban", 1, 1, "temple", "religious-city",
     "Białe mury klasztoru widoczne z dwudziestu mil. Mnisi w szarych habitach modlą się dzień i noc, a wieże świątyń sięgają chmur.",
     [
        ("klasztor_iskry_kaplica_glowna", "Klasztor Iskry: Wielka Kaplica", "temple", 1,
         "Sklepienie wysokie jak las. Pochodnie się tu nie palą — światło daje sama Iskra Wieczna w ołtarzu."),
        ("klasztor_iskry_biblioteka", "Klasztor Iskry: Biblioteka", "library", 1,
         "Dziesiątki tysięcy ksiąg. Mnich-bibliotekarz pamięta każdą stronę — i każdą zna na pamięć."),
        ("klasztor_iskry_cele_mnichow", "Klasztor Iskry: Cele Pokuty", "monastery", 1,
         "Małe pomieszczenia bez okien, gdzie pokutnicy spędzają tygodnie w ciszy. Pielgrzymi mogą zarezerwować nocleg."),
        ("klasztor_iskry_grobowiec_swietego", "Klasztor Iskry: Grobowiec Świętego", "tomb", 1,
         "Krypta założyciela klasztoru. Czasem słychać stamtąd szept — mnisi twierdzą, że to jego błogosławieństwo."),
     ]),
    ("volhynia_kupiecka", "Volhynia, Miasto Kupieckie", "urban", 1, 1, "town", "trade-city",
     "Skrzyżowanie czterech głównych traktów. Kupcy wszystkich nacji śpią tu jeden na drugim, a magazyny pękają od towaru.",
     [
        ("volhynia_targowisko", "Volhynia: Wielkie Targowisko", "market", 1,
         "Sto namiotów, tysiąc krzyków. Wszystko można kupić — i wszystko może być fałszywe."),
        ("volhynia_gildia_kupcow", "Volhynia: Gildia Kupiecka", "guild", 1,
         "Pałac z dwoma piętrami i strażą. Tylko członek gildii albo bogaty gość przekroczy próg."),
        ("volhynia_arena_walk", "Volhynia: Arena Walk", "arena", 0,
         "Drewniana arena, gdzie najmnicy walczą o złoto i sławę. Krew lała się tu jak wino."),
        ("volhynia_gospoda_szlaku", "Volhynia: Gospoda Szlaku", "tavern", 1,
         "Solidna gospoda dla kupców — z pokojami, stajnią i strażnikami przy bramie."),
     ]),
    ("zatoka_topielcow", "Zatoka Topielców", "urban", 3, 0, "town", "pirate-haven",
     "Pirackie miasto-twierdza na wyspie. Bez prawa, bez podatków, bez litości. Każdy nosi tu broń.",
     [
        ("zatoka_kapitanska_karczma", "Zatoka: Karczma Kapitańska", "tavern", 0,
         "Tu spotykają się kapitanowie piratów. Spór załatwia się szabelką, nie słowami."),
        ("zatoka_pirackie_doki", "Zatoka: Pirackie Doki", "port", 0,
         "Stocznie remontują czarne galery. Robotnicy są więźniami albo zdesperowanymi."),
        ("zatoka_jaskinie_skarbow", "Zatoka: Jaskinie Skarbów", "cave", 0,
         "Krętym labirynt grot, gdzie kapitanowie chowają zdobycze. Pułapki, strażnicy, klątwy."),
        ("zatoka_rada_piracka", "Zatoka: Rada Piracka", "guild", 0,
         "Pięciu kapitanów decyduje o losie wyspy. Ich słowo jest tu prawem."),
     ]),

    # ── TOWNS / VILLAGES (8) ───────────────────────────────────────────────
    ("cieszowice", "Cieszowice", "rural", 1, 1, "town", "village",
     "Spokojna wieś z dwudziestoma domami i jednym kapłanem. Słynie z miodu pitnego i kradzieży kur.",
     [
        ("cieszowice_karczma", "Cieszowice: Karczma Pod Lipą", "tavern", 1,
         "Mała karczma pod stuletnią lipą. Karczmarz Bartek warzy najlepszy miód w okolicy."),
        ("cieszowice_kaplica", "Cieszowice: Kapliczka", "temple", 1,
         "Drewniana kapliczka z figurką Świętej Anny. Wieśniacy palą tu świece za zmarłych."),
        ("cieszowice_studnia", "Cieszowice: Stara Studnia", "ruin", 0,
         "Wyschnięta studnia w środku wsi. Mówią, że dziecko utopiło się w niej sto lat temu."),
        ("cieszowice_pole_lubek", "Cieszowice: Pola Łubków", "wilderness", 0,
         "Łąki za wsią. Pszczoły żyją w starych pniach, a dziki kradną kapustę."),
     ]),
    ("zgliszcza", "Zgliszcza, Spalona Wieś", "rural", 2, 0, "ruin", "burned-village",
     "Po pożarze z zeszłego roku zostały tylko kominy. Niektórzy próbują odbudować — inni przeklinają to miejsce.",
     [
        ("zgliszcza_kosciol_spalony", "Zgliszcza: Wypalony Kościół", "ruin", 0,
         "Kamienne ściany i osmolony krzyż. Dzwon spadł i leży połamany w nawie."),
        ("zgliszcza_obozowisko", "Zgliszcza: Obozowisko Ocalałych", "camp", 1,
         "Pół tuzina rodzin mieszka w prowizorycznych chatach z desek. Czują się na czuwaniu."),
        ("zgliszcza_masowy_grob", "Zgliszcza: Masowy Grób", "graveyard", 0,
         "Świeżo wykopany dół z prowizorycznymi krzyżami. Czterdzieści jeden ofiar."),
     ]),
    ("most_czarnej_rzeki", "Most Czarnej Rzeki", "rural", 2, 1, "town", "bridge-town",
     "Drewniany most strzeżony przez przedmieście karczmarzy i poborców. Każdy podróżny zostawia tu monetę.",
     [
        ("most_komora_celna", "Most: Komora Celna", "guild", 1,
         "Mały urząd przy bramie mostu. Poborca Pius zna każdą sztuczkę przemytników."),
        ("most_karczma_pod_lupinkami", "Most: Pod Lipinkami", "tavern", 1,
         "Karczma z widokiem na rzekę. Karczmarka serwuje rybny gulasz dzień i noc."),
        ("most_warta_mostowa", "Most: Wartownia Mostu", "fortress", 1,
         "Mała wieża z trzyma strażnikami. Zawsze ktoś czuwa nad mostem."),
     ]),
    ("wolanka", "Wolanka, Wioska Górnicza", "mountain", 2, 1, "town", "mining-village",
     "Wioska wcięta w stok góry. Wszyscy pracują w kopalniach żelaza albo zmierzają tam codziennie przed świtem.",
     [
        ("wolanka_kopalnia_glowna", "Wolanka: Kopalnia Główna", "cave", 0,
         "Sztolnie ciągnące się kilometrami pod ziemią. Słychać czasem dziwne dźwięki z głębi."),
        ("wolanka_kuznia", "Wolanka: Kuźnia Wujka", "smithy", 1,
         "Kuźnia pradziadka i prawnuka. Płomień nie wygasł od trzech pokoleń."),
        ("wolanka_kosciol_swietego_floriana", "Wolanka: Kościół Św. Floriana", "temple", 1,
         "Kapliczka patrona górników. Codziennie modlitwa za tych w sztolniach."),
        ("wolanka_szynk", "Wolanka: Szynk Górniczy", "tavern", 1,
         "Mała karczma, gdzie pijani górnicy płaczą o sztolniach i kobietach."),
     ]),
    ("strazyn", "Strażyn, Twierdza Graniczna", "mountain", 3, 1, "fortress", "garrison",
     "Kamienna twierdza na pograniczu. Strzeże traktu od wschodnich barbarzyńców już od dwustu lat.",
     [
        ("strazyn_koszary", "Strażyn: Koszary", "fortress", 1,
         "Trzy izby dla setki żołnierzy. Pachnie potem, smarem do broni i palącymi się świecami."),
        ("strazyn_wieza_strazak", "Strażyn: Wieża Strażacka", "tower", 1,
         "Najwyższa wieża w twierdzy. Z jej szczytu widać równinę na pięć mil w każdą stronę."),
        ("strazyn_lazaret", "Strażyn: Lazaret", "temple", 1,
         "Polowy szpital. Felczer Bolesław leczy rany, choroby i strach."),
        ("strazyn_kantyna", "Strażyn: Kantyna Żołnierska", "tavern", 1,
         "Wojskowa karczma — piwo proste, jedzenie sycące, plotki świeże."),
     ]),
    ("brzezino", "Brzezino, Wioska Drwali", "forest", 1, 1, "town", "lumber-village",
     "Pół tuzina chat z drewna brzozowego, w sercu lasu. Tylko zapach żywicy zdradza, że ktoś tu mieszka.",
     [
        ("brzezino_tartak", "Brzezino: Tartak Starego Jerzego", "smithy", 0,
         "Wodny tartak nad strumieniem. Pracuje od świtu do zmierzchu."),
        ("brzezino_dom_starszego", "Brzezino: Dom Starszego", "town", 1,
         "Największa chata, gdzie mieszka starszy wsi. Można tu przenocować za drobną opłatą."),
        ("brzezino_swieta_polanka", "Brzezino: Święta Polanka", "shrine", 1,
         "Stara polana z kamiennym kręgiem. Drwale modlą się tu o bezpieczeństwo w lesie."),
     ]),
    ("pustelnia_marcina", "Pustelnia Świętego Marcina", "rural", 1, 1, "temple", "hermitage",
     "Samotna chata pustelnika na wzgórzu nad rzeką. Brat Marcin nie odmawia nikomu noclegu — ani okruchu chleba.",
     [
        ("pustelnia_kaplica_lesna", "Pustelnia: Kapliczka Leśna", "shrine", 1,
         "Drewniana kapliczka pod dębem. Modlitwa tu daje spokój ducha."),
        ("pustelnia_ogrod_ziolowy", "Pustelnia: Ogród Ziołowy", "garden", 1,
         "Pustelnik hoduje setkę gatunków ziół. Pomoże uleczyć każdą znaną chorobę."),
        ("pustelnia_zrodlo", "Pustelnia: Święte Źródło", "river", 1,
         "Krystaliczna woda. Mówią, że leczy gorączkę i zły wzrok."),
     ]),
    ("trzech_krukow", "Karczma Pod Trzema Krukami", "rural", 2, 1, "town", "wayside-inn",
     "Samotna karczma na skrzyżowaniu traktów. Punkt zborny kupców, najemników i tych, którzy nie chcą być znalezieni.",
     [
        ("trzech_krukow_wielka_izba", "Pod Trzema Krukami: Wielka Izba", "tavern", 1,
         "Główna izba z dziesięcioma stołami. Ognisko płonie nawet w lipcu."),
        ("trzech_krukow_stajnia", "Pod Trzema Krukami: Stajnia", "shop", 1,
         "Stajnia na dwadzieścia koni. Stary giermek pamięta każdego, kto przejeżdżał."),
        ("trzech_krukow_pokoje_kupcow", "Pod Trzema Krukami: Pokoje", "tavern", 1,
         "Pięć pokoi na piętrze. Drobny luksus za sztukę srebra."),
     ]),

    # ── FORESTS (4) ────────────────────────────────────────────────────────
    ("las_czarnych_drzew", "Las Czarnych Drzew", "forest", 3, 0, "forest", "haunted-forest",
     "Stary las, gdzie pnie są ciemne jak smoła, a liście szepczą imiona zmarłych. Wieśniacy obchodzą go z daleka.",
     [
        ("las_czarnych_polanka_starszych", "Las Czarnych Drzew: Polana Starszych", "shrine", 0,
         "Krąg pradawnych głazów. Czasem widać tu cienie, które nie mają właściciela."),
        ("las_czarnych_zlamany_dab", "Las Czarnych Drzew: Złamany Dąb", "ruin", 0,
         "Wielki dąb przepołowiony piorunem. W szczelinie świeci coś zielonego."),
        ("las_czarnych_chata_starej", "Las Czarnych Drzew: Chata Starej", "town", 0,
         "Krzywa chata na palach kurzych. Mieszka tu wiedźma Jaga, choć nie zawsze."),
        ("las_czarnych_grobowiec_kniazia", "Las Czarnych Drzew: Grobowiec Kniazia", "tomb", 0,
         "Stara mogiła zarosła brzozami. Mówią, że kniaź wstaje po pełni."),
     ]),
    ("bor_zmarlych", "Bór Zmarłych", "forest", 4, 0, "graveyard", "undead-forest",
     "Las nawiedzony przez nieumarłych. Po zmroku z ziemi wstają cienie, a żywi tu nie nocują.",
     [
        ("bor_cmentarz_przy_drodze", "Bór: Cmentarz Przy Drodze", "graveyard", 0,
         "Stary cmentarz z pochyłami nagrobkami. Jeden grób zawsze świeży, choć nikt go nie kopie."),
        ("bor_kostnica_lesna", "Bór: Leśna Kostnica", "ruin", 0,
         "Drewniana chata pełna kości. Kto je tu zwiózł — i po co?"),
        ("bor_swiete_zrodlo_krwi", "Bór: Krwawe Źródło", "river", 0,
         "Strumień, którego woda jest czerwona. Smakuje miedzi i strachu."),
        ("bor_kosciol_zapomniany", "Bór: Zapomniany Kościół", "ruin", 0,
         "Ruina kościółka z dziurawym dachem. Ołtarz nadal stoi — i nadal coś przyjmuje."),
     ]),
    ("bagienna_knieja", "Bagienna Knieja", "swamp", 3, 0, "water", "swamp-forest",
     "Mokradła pokryte gęstą mgłą. Drzewa rosną w wodzie, a komary wysysają krew szybciej niż utopce.",
     [
        ("bagienna_chatka_zielarki", "Bagienna Knieja: Chatka Zielarki", "town", 1,
         "Drewniana chatka na palach. Zielarka Mira sprzedaje mikstury — i wie wszystko o ziołach."),
        ("bagienna_wyspa_topielca", "Bagienna Knieja: Wyspa Topielca", "ruin", 0,
         "Mała wyspa pośród bagna. Tu utonął kupiec, który nie chciał oddać złota."),
        ("bagienna_pradawny_kamien", "Bagienna Knieja: Pradawny Kamień", "shrine", 0,
         "Wielki głaz z runami. Druidzi modlili się tu w czasach, których nikt nie pamięta."),
     ]),
    ("zloty_las", "Złoty Las", "forest", 2, 1, "forest", "elven-woods",
     "Lasy zawsze złociste, niezależnie od pory roku. Mówią, że elfy stworzyły je magią — i pilnują do dziś.",
     [
        ("zloty_polana_elfow", "Złoty Las: Polana Elfów", "shrine", 1,
         "Polana w sercu lasu. Czasem widać tam tańczące światła — to elfy, lub coś bardziej niebezpiecznego."),
        ("zloty_chata_lesnika", "Złoty Las: Chata Leśnika", "town", 1,
         "Stary leśnik Maciej zna las jak własną kieszeń. Można tu przenocować."),
        ("zloty_jezioro_lustro", "Złoty Las: Jezioro Lustro", "river", 1,
         "Krystaliczne jezioro, w którym widać przyszłość — albo to, czego się boisz."),
        ("zloty_oltarz_lesny", "Złoty Las: Leśny Ołtarz", "shrine", 1,
         "Kamienny ołtarz porośnięty mchem. Złożenie kwiatów daje błogosławieństwo na dzień."),
     ]),

    # ── MOUNTAINS (3) ──────────────────────────────────────────────────────
    ("krzyz_gor", "Krzyż Gór", "mountain", 3, 0, "mountain", "mountain-range",
     "Najwyższe pasmo w królestwie — szczyty zawsze w śniegu. Tylko najtwardsi wędrowcy wchodzą wyżej niż w doliny.",
     [
        ("krzyz_przelecz_swietej_jadwigi", "Krzyż Gór: Przełęcz Św. Jadwigi", "mountain", 0,
         "Wąska przełęcz na 2000 metrów. Burze potrafią uwięzić tu na tygodnie."),
        ("krzyz_chatka_pasterska", "Krzyż Gór: Chatka Pasterska", "town", 1,
         "Mała chatka pasterzy. Zostaje pusta zimą — można w niej przenocować."),
        ("krzyz_klasztor_szczytu", "Krzyż Gór: Klasztor Szczytu", "temple", 1,
         "Klasztor wbity w skałę. Mnisi nie schodzą w doliny od trzydziestu lat."),
        ("krzyz_kopalnia_kobaltu", "Krzyż Gór: Kopalnia Kobaltu", "cave", 0,
         "Stara kopalnia rzadkiego niebieskiego kamienia. Krasnoludy opuściły ją sto lat temu."),
        ("krzyz_jaskinia_smoka", "Krzyż Gór: Jaskinia Smoka", "cave", 0,
         "Wielka grota z opaleniznami na ścianach. Smok zniknął — ale czy na zawsze?"),
     ]),
    ("czarne_skaly", "Czarne Skały, Wulkan", "mountain", 4, 0, "mountain", "volcano",
     "Wulkaniczny stożek z popiołem na zboczach. Tu nawet trawa nie rośnie, a powietrze cuchnie siarką.",
     [
        ("czarne_krater_dymiacy", "Czarne Skały: Dymiący Krater", "mountain", 0,
         "Krater wulkanu, z którego unoszą się szare obłoki. Niektórzy słyszą stamtąd głosy."),
        ("czarne_swiatynia_ognia", "Czarne Skały: Świątynia Ognia", "temple", 0,
         "Mroczna świątynia kultu Czerwonego Ognia. Modlą się tu o erupcję."),
        ("czarne_grobowiec_kapłana", "Czarne Skały: Grobowiec Kapłana", "tomb", 0,
         "Kamienna krypta, w której pochowano złego kapłana. Jego pierścień podobno otwiera bramy piekła."),
     ]),
    ("lodowy_pas", "Lodowy Pas", "mountain", 4, 0, "mountain", "frozen-peaks",
     "Pasmo gór na dalekiej północy, gdzie zima nigdy się nie kończy. Tubylcy nazywają je 'Tronem Białej Bogini'.",
     [
        ("lodowy_jaskinia_lodu", "Lodowy Pas: Jaskinia Lodu", "cave", 0,
         "Lodowa grota z dziwnymi rzeźbami w ścianach. Wiele zaginęło tu na zawsze."),
        ("lodowy_dom_szamana", "Lodowy Pas: Chata Szamana", "town", 1,
         "Iglu z lodu i futer. Szaman Bjorn rozmawia z duchami zimy."),
        ("lodowy_kostnica_morsow", "Lodowy Pas: Kostnica Morsów", "graveyard", 0,
         "Wybrzeże usłane kośćmi olbrzymich morsów. Tradycyjne miejsce pochówku tubylców."),
        ("lodowy_kryształowa_komnata", "Lodowy Pas: Kryształowa Komnata", "ruin", 0,
         "Naturalna grota z lodu w kształcie kryształów. Echa tu nigdy nie cichną."),
     ]),

    # ── DUNGEONS / RUINS (5) ───────────────────────────────────────────────
    ("ruiny_klasztoru_pradawnego", "Ruiny Pradawnego Klasztoru", "dungeon", 3, 0, "ruin", "ruined-monastery",
     "Mury klasztoru zarosły mchem i bluszczem. W krużgankach echo niesie szepty modlitw, których nikt nie wypowiada.",
     [
        ("ruiny_klasztoru_kaplica_glowna", "Ruiny Klasztoru: Główna Kaplica", "temple", 0,
         "Sklepienie zawalone, ale ołtarz nienaruszony. Coś go strzeże."),
        ("ruiny_klasztoru_krypta", "Ruiny Klasztoru: Krypta Opata", "tomb", 0,
         "Schody w dół, do krypty. Trumna otwarta — i pusta."),
        ("ruiny_klasztoru_skryptorium", "Ruiny Klasztoru: Skryptorium", "library", 0,
         "Stara biblioteka pełna butwiejących ksiąg. Niektóre nadal czytelne — i niebezpieczne."),
        ("ruiny_klasztoru_studnia", "Ruiny Klasztoru: Studnia", "cave", 0,
         "Studnia bez dna. Wiadro spada — nie wraca."),
     ]),
    ("krypta_krwawego_hrabiego", "Krypta Krwawego Hrabiego", "dungeon", 4, 0, "tomb", "vampire-crypt",
     "Krypta wampira-hrabiego pod ruiną zamku. Cuchnie krwią pomimo wieków, a echo szepta w obcym języku.",
     [
        ("krypta_przedsionek", "Krypta: Przedsionek", "tomb", 0,
         "Kamienna komnata z mozaiką krwawego krzyża. Pułapki czekają na nieuważnych."),
        ("krypta_sala_uczt", "Krypta: Sala Krwawych Uczt", "ruin", 0,
         "Wielka sala ze stołem na pięćdziesiąt osób. Na stole nadal stoją kielichy — pełne."),
        ("krypta_grobowiec_hrabiego", "Krypta: Grobowiec Hrabiego", "tomb", 0,
         "Główna komnata z wielkim sarkofagiem z czarnego marmuru. Wieko zsunięte."),
        ("krypta_sale_służących", "Krypta: Sala Sług", "ruin", 0,
         "Komnaty pomniejszych nieumarłych. Niektórzy są jeszcze świadomi — i głodni."),
     ]),
    ("kopalnia_czarnego_hutmana", "Kopalnia Czarnego Hutmana", "dungeon", 3, 0, "cave", "cursed-mine",
     "Opuszczona kopalnia srebra. Krasnoludy odeszły dwadzieścia lat temu, ale ktoś — albo coś — nadal tam stuka.",
     [
        ("kopalnia_wejscie_glowne", "Kopalnia: Wejście Główne", "cave", 0,
         "Brama z dębowego drewna obita żelazem. Zamknięta od wewnątrz."),
        ("kopalnia_sztolnia_srebrna", "Kopalnia: Sztolnia Srebrna", "cave", 0,
         "Kręte korytarze pełne pajęczyn. Stare lampy nadal się palą — kto je zapala?"),
        ("kopalnia_komnata_brygadzisty", "Kopalnia: Komnata Brygadzisty", "ruin", 0,
         "Małe pomieszczenie z biurkiem. Pamiętnik leży otwarty na ostatniej stronie."),
        ("kopalnia_zalane_korytarze", "Kopalnia: Zalane Korytarze", "water", 0,
         "Dolne poziomy pod wodą. Coś tam pływa — i nie jest człowiekiem."),
        ("kopalnia_serce_kopalni", "Kopalnia: Serce Kopalni", "cave", 0,
         "Wielka komnata z czarnym kryształem w środku. Pulsuje światłem co kilka sekund."),
     ]),
    ("twierdza_bezimiennego", "Twierdza Bezimiennego", "dungeon", 5, 0, "castle", "haunted-fortress",
     "Zamek na klifie, opuszczony po klątwie. Mury są nienaruszone — ale nikt z tych, co weszli, nie wrócił.",
     [
        ("twierdza_dziedziniec", "Twierdza: Dziedziniec", "ruin", 0,
         "Pusty dziedziniec z fontanną pełną krwi. Czerwona ciecz nigdy nie wysycha."),
        ("twierdza_sala_tronowa", "Twierdza: Sala Tronowa", "castle", 0,
         "Wielka sala z tronem z kości. Korona nadal leży na siedzeniu."),
        ("twierdza_biblioteka_zakazana", "Twierdza: Zakazana Biblioteka", "library", 0,
         "Tysiące ksiąg o ciemnej magii. Niektóre się ruszają same."),
        ("twierdza_lochy", "Twierdza: Lochy", "dungeon", 0,
         "Cele z zakutymi szkieletami. Niektóre szkielety mają cele zamknięte od WEWNĄTRZ."),
        ("twierdza_szczyt_wiezy", "Twierdza: Szczyt Wieży", "tower", 0,
         "Najwyższa wieża z widokiem na morze. Tu spadali ci, którzy nie chcieli się modlić."),
     ]),
    ("swiatynia_pradawnych", "Świątynia Pradawnych", "dungeon", 5, 0, "temple", "ancient-temple",
     "Świątynia wyższych istot z czasów przed-ludzkich. Architektura przypomina wnętrze martwego boga.",
     [
        ("swiatynia_brama_dziwna", "Świątynia: Dziwna Brama", "ruin", 0,
         "Brama z metalu, którego nikt nie zna. Otwiera się tylko, gdy się ją uważnie zaprosi."),
        ("swiatynia_komnata_kapłanów", "Świątynia: Komnata Kapłanów", "temple", 0,
         "Wielkie figury skamieniałych kapłanów. Ich oczy nadal śledzą wędrowca."),
        ("swiatynia_ołtarz_glowny", "Świątynia: Główny Ołtarz", "shrine", 0,
         "Czarny ołtarz w kształcie spirali. Świeże ofiary... świeże."),
        ("swiatynia_podziemna_rzeka", "Świątynia: Podziemna Rzeka", "river", 0,
         "Rzeka czarnej wody pod świątynią. Płynie w obu kierunkach jednocześnie."),
     ]),

    # ── WILDERNESS (5) ─────────────────────────────────────────────────────
    ("trzesawiska_mgiel", "Trzęsawiska Mgieł", "swamp", 3, 0, "water", "misty-marsh",
     "Bezkresne bagna pokryte białą mgłą. Tu giną wędrowcy, którzy zboczyli z gościńca.",
     [
        ("trzesawiska_drzewo_powieszonych", "Trzęsawiska: Drzewo Powieszonych", "ruin", 0,
         "Stary dąb, na którym wieszano złodziei. Postronki wciąż wiszą — niektóre świeże."),
        ("trzesawiska_chata_topielcow", "Trzęsawiska: Chata Topielców", "ruin", 0,
         "Zatopiona chata. Po południu można w niej zobaczyć cienie rodziny."),
        ("trzesawiska_ognisty_kostkocian", "Trzęsawiska: Ognisty Kostkocian", "shrine", 0,
         "Mały szałas-mauzoleum starych ludów. Czaszki w środku świecą po zmroku."),
     ]),
    ("step_wilkow", "Step Wilków", "plains", 2, 0, "wilderness", "wolf-steppe",
     "Bezkresne stepy, gdzie po zmroku słychać tylko wycie watah. Trakt biegnie przez nie pięćdziesiąt mil.",
     [
        ("step_kurhan_chana", "Step Wilków: Kurhan Chana", "tomb", 0,
         "Wielki kurhan barbarzyńskiego wodza. Mogiła jeszcze nieotwarta — przez ostrożność."),
        ("step_obozowisko_koczownikow", "Step Wilków: Obozowisko Koczowników", "camp", 1,
         "Namioty plemienia konnego. Gościnni — póki ich nie obrażysz."),
        ("step_strazowanica", "Step Wilków: Strażownica", "tower", 1,
         "Stara strażnica królewska. Pusta od lat, ale dach jeszcze trzyma."),
     ]),
    ("pustkowie_solne", "Pustkowie Solne", "desert", 4, 0, "wilderness", "salt-desert",
     "Biała równina soli na południu. Słońce odbija się od kryształów tak, że oczy bolą — a wody nie ma na sto mil.",
     [
        ("pustkowie_oaza_zlodzieja", "Pustkowie: Oaza Złodzieja", "town", 1,
         "Jedyna oaza w okolicy. Kontrolują ją przemytnicy i wymagają opłaty za wodę."),
        ("pustkowie_zatopiony_okret", "Pustkowie: Zatopiony Okręt", "ruin", 0,
         "Stary statek na środku pustyni — pamiątka po dawnym morzu."),
        ("pustkowie_piaskowa_mogila", "Pustkowie: Piaskowa Mogiła", "tomb", 0,
         "Grobowiec z piaskowca, pół-pochłonięty przez wydmy. Wejście odkopano niedawno."),
     ]),
    ("wybrzeze_lez", "Wybrzeże Łez", "coast", 3, 0, "water", "sorrow-coast",
     "Skalisty brzeg, gdzie sztormy łamią statki o nadbrzeżne skały. Po każdej burzy znajduje się ciała.",
     [
        ("wybrzeze_wraki_starych_statkow", "Wybrzeże Łez: Wraki", "ruin", 0,
         "Cmentarzysko statków. Dziesiątki kadłubów na nieczytelnych nazwach."),
        ("wybrzeze_jaskinia_kontrabandy", "Wybrzeże Łez: Jaskinia Przemytników", "cave", 0,
         "Grota dostępna tylko z morza. Przemytnicy chowają tu towar."),
        ("wybrzeze_latarnia_starego", "Wybrzeże Łez: Latarnia Starego", "tower", 1,
         "Latarnia morska prowadzona przez starego rybaka. Można u niego przespać noc."),
        ("wybrzeze_świątynia_topielcow", "Wybrzeże Łez: Świątynia Topielców", "shrine", 0,
         "Kamienny ołtarz na skale. Modlą się tu o szczęście tych, którzy odeszli w morze."),
     ]),
    ("tundra_mrozu", "Tundra Wiecznego Mrozu", "tundra", 4, 0, "wilderness", "frozen-tundra",
     "Najdalsza północ — równina lodu i śniegu, gdzie słońce nie wschodzi przez pół roku.",
     [
        ("tundra_obozowisko_huskies", "Tundra: Obozowisko Łowców", "camp", 1,
         "Tymczasowy obóz łowców fok. Można u nich kupić ciepłe futra."),
        ("tundra_lodowiec_pradawny", "Tundra: Pradawny Lodowiec", "mountain", 0,
         "Wielki lodowiec ze szczelinami głębokimi na pół mili. W jednej zamarzł ktoś z mieczem."),
        ("tundra_swiete_kamienie", "Tundra: Święte Kamienie", "shrine", 0,
         "Krąg kamieni postawionych przez tubylców. Modły o przetrwanie zimy."),
     ]),
]


def main() -> int:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        n_macro = 0
        n_sub = 0
        for macro in LOCATIONS:
            (mkey, mlabel, mbiome, mtier, mrest, micon, msubtype, mdesc, subs) = macro
            # Insert macro — #1526 (fala 3): jedne drzwi, idempotentne po kluczu
            if create_location(
                conn,
                key=mkey, label=mlabel, source=LocationSource.SEED,
                description=mdesc, location_type="macro",
                biome=mbiome, tier=mtier, safe_for_rest=mrest,
                map_icon=micon, location_subtype=msubtype,
                commit=False,
            )["created"]:
                n_macro += 1
            macro_row = conn.execute("SELECT id FROM game_locations WHERE key = ?", (mkey,)).fetchone()
            if not macro_row:
                print(f"  ! Macro {mkey} not found after insert?")
                continue
            macro_id = int(macro_row["id"])

            for (skey, slabel, ssubtype, ssafe, sdesc) in subs:
                if create_location(
                    conn,
                    key=skey, label=slabel, source=LocationSource.SEED,
                    description=sdesc, location_type="sub",
                    parent_key=mkey, parent_id=macro_id,
                    biome=mbiome, tier=mtier, safe_for_rest=ssafe,
                    map_icon=micon, location_subtype=ssubtype,
                    commit=False,
                )["created"]:
                    n_sub += 1
        conn.commit()
        print(f"✓ Inserted {n_macro} macros + {n_sub} sub-locations = {n_macro + n_sub} total")
        cnt = conn.execute("SELECT COUNT(*) FROM game_locations WHERE is_active = 1").fetchone()[0]
        print(f"  Total active locations in DB: {cnt}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
