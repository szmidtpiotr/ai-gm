#!/usr/bin/env python3
"""Seed 50 enemies (4 tiers) + per-enemy loot tables (tiered) + 50 NPCs.
Polish labels and descriptions. Idempotent (INSERT OR REPLACE).
Run inside backend container.
"""
import json
import sqlite3
import sys

DB_PATH = "/data/ai_gm.db"

# ── 50 ENEMIES ─────────────────────────────────────────────────────────────
# Fields: key, label, tier (weak|standard|elite|boss), hp_base, ac_base,
#   attack_bonus, damage_die, damage_bonus, attacks_per_turn, xp_award,
#   description, fear_aura(boss only), dex_modifier
ENEMIES = [
    # ── WEAK (15) — fodder, no fear, low damage ──
    {"key": "rat",            "label": "Szczur",                "tier": "weak", "hp_base": 3, "ac_base": 10, "attack_bonus": 0, "damage_die": "d2", "xp_award": 5,
     "description": "Wielki, garbaty szczur z żółtymi kłami. Roznosi choroby — zatop go, póki nie zbliżył się do worków z prowiantem."},
    {"key": "giant_rat",      "label": "Olbrzymi szczur",       "tier": "weak", "hp_base": 5, "ac_base": 11, "attack_bonus": 1, "damage_die": "d4", "xp_award": 10,
     "description": "Wielkości kota, z włosami sztywnymi jak druty. Atakuje w stadach z kanałów i piwnic."},
    {"key": "plague_rat",     "label": "Zarażony szczur",       "tier": "weak", "hp_base": 4, "ac_base": 10, "attack_bonus": 1, "damage_die": "d3", "xp_award": 10,
     "description": "Łysy szczur z różowymi wrzodami. Ugryzienie może spowodować gorączkę dziesięcioletnich."},
    {"key": "bat",            "label": "Nietoperz",             "tier": "weak", "hp_base": 2, "ac_base": 12, "dex_modifier": 2, "attack_bonus": 0, "damage_die": "d2", "xp_award": 5,
     "description": "Mały, czarny nietoperz wirujący nad głową. Nieszkodliwy w pojedynkę — w stadzie potrafi oślepić."},
    {"key": "crow_familiar",  "label": "Wronie chowańce",       "tier": "weak", "hp_base": 4, "ac_base": 11, "dex_modifier": 1, "attack_bonus": 0, "damage_die": "d3", "xp_award": 8,
     "description": "Dziwnie inteligentne wrony z czerwonymi oczyma. Krążą wokół wiedźm i odwiedzają ich wrogów."},
    {"key": "spider_small",   "label": "Pająk jaskiniowy",      "tier": "weak", "hp_base": 5, "ac_base": 11, "attack_bonus": 1, "damage_die": "d4", "xp_award": 10,
     "description": "Pająk wielkości dłoni z bladymi oczyma. Jad obezwładnia — nawet ofiara silna jak wół potrafi zasłabnąć."},
    {"key": "snake",          "label": "Wąż leśny",             "tier": "weak", "hp_base": 4, "ac_base": 12, "dex_modifier": 2, "attack_bonus": 1, "damage_die": "d4", "xp_award": 10,
     "description": "Cienki, ciemny wąż. Trudno go dostrzec wśród liści — atakuje znienacka z gałęzi."},
    {"key": "marsh_eel",      "label": "Bagienna mureno-rybka", "tier": "weak", "hp_base": 6, "ac_base": 11, "attack_bonus": 1, "damage_die": "d4", "xp_award": 12,
     "description": "Półmetrowy węgorz z błyszczącą śluzem skórą. Wyskakuje z mętnej wody i przyssawkami chwyta kostkę."},
    {"key": "kobold",         "label": "Kobold",                "tier": "weak", "hp_base": 6, "ac_base": 12, "attack_bonus": 1, "damage_die": "d4", "xp_award": 15,
     "description": "Mały gad-humanoid w skórzanych łachach. Chytry i tchórzliwy, ale w grupie potrafi zarzucić sieć z dachu."},
    {"key": "goblin",         "label": "Goblin",                "tier": "weak", "hp_base": 8, "ac_base": 11, "attack_bonus": 2, "damage_die": "d6", "xp_award": 25,
     "description": "Karłowaty zielonoskóry napastnik o żółtych kłach. Pojedynczo żałosny — w bandzie potrafi zalać karawanę."},
    {"key": "imp_minor",      "label": "Mały chochlik",         "tier": "weak", "hp_base": 6, "ac_base": 13, "dex_modifier": 2, "attack_bonus": 1, "damage_die": "d4", "xp_award": 15,
     "description": "Maleńki demonek z fioletową skórą. Niewart strachu, ale jego ukłucia parzą jak żarzące igły."},
    {"key": "wild_boar_young","label": "Młody dzik",            "tier": "weak", "hp_base": 9, "ac_base": 11, "attack_bonus": 2, "damage_die": "d6", "xp_award": 20,
     "description": "Roczny dzik z dopiero rosnącymi szabelkami. Szarżuje na każdą postać w czerwonym płaszczu."},
    {"key": "drowned_man",    "label": "Utopiec",               "tier": "weak", "hp_base": 7, "ac_base": 10, "attack_bonus": 1, "damage_die": "d4", "xp_award": 15,
     "description": "Ciało utopione od miesięcy, wstające z dna jeziora. Cuchnie błotem i siarką."},
    {"key": "swamp_creeper",  "label": "Bagienny pełzacz",      "tier": "weak", "hp_base": 6, "ac_base": 10, "attack_bonus": 1, "damage_die": "d4", "xp_award": 12,
     "description": "Bezkształtna masa zielonej galaretki sunąca po mokradle. Pochłania martwe zwierzęta — i nieuważnych podróżników."},
    {"key": "hedgehog_demon", "label": "Diabelski jeż",         "tier": "weak", "hp_base": 5, "ac_base": 14, "attack_bonus": 1, "damage_die": "d3", "xp_award": 12,
     "description": "Pulchny jeż z kolcami jak igły kowala. Toczy się jak kulka, parzy jak ogień."},

    # ── STANDARD (20) — bread-and-butter mid combat ──
    {"key": "wolf_standard",  "label": "Wilk",                  "tier": "standard", "hp_base": 11, "ac_base": 13, "dex_modifier": 1, "attack_bonus": 3, "damage_die": "d6", "xp_award": 40,
     "description": "Dorosły szary wilk z głodem zimowym w oczach. Atakuje, gdy zwęszy strach."},
    {"key": "dire_wolf",      "label": "Wilk-mocarz",           "tier": "standard", "hp_base": 18, "ac_base": 13, "attack_bonus": 4, "damage_die": "d8", "damage_bonus": 1, "xp_award": 65,
     "description": "Wilk wielkości konia, z czarną sierścią. Jego wycie słychać przez całą dolinę."},
    {"key": "bandit_lvl2",    "label": "Bandyta",               "tier": "standard", "hp_base": 12, "ac_base": 13, "attack_bonus": 3, "damage_die": "d6", "xp_award": 35,
     "description": "Najemny rzezimieszek z brudnym sztyletem i pożółkłymi zębami. Walczy o monetę, zabija dla przyjemności."},
    {"key": "brigand",        "label": "Rozbójnik",             "tier": "standard", "hp_base": 14, "ac_base": 13, "attack_bonus": 3, "damage_die": "d6", "damage_bonus": 1, "xp_award": 45,
     "description": "Wieloletni weteran leśnych zasadzek. Twarz pokryta starymi bliznami, wzrok zimny."},
    {"key": "archer",         "label": "Łucznik",               "tier": "standard", "hp_base": 11, "ac_base": 12, "dex_modifier": 2, "attack_bonus": 4, "damage_die": "d8", "xp_award": 50,
     "description": "Pasoży lasów — strzela ze średniej odległości i znika między drzewami zanim się zorientujesz."},
    {"key": "mercenary",      "label": "Najemnik",              "tier": "standard", "hp_base": 16, "ac_base": 14, "attack_bonus": 4, "damage_die": "d8", "xp_award": 60,
     "description": "Zawodowy zbrojny w kolczudze z herbem dawno zapomnianego rodu. Walczy systematycznie i bez emocji."},
    {"key": "skeleton_warrior","label":"Szkielet wojownik",     "tier": "standard", "hp_base": 13, "ac_base": 13, "attack_bonus": 3, "damage_die": "d6", "xp_award": 40,
     "description": "Stary szkielet w pordzewiałej kolczudze. Klęka tylko gdy się go zburzy."},
    {"key": "zombie",         "label": "Zombie",                "tier": "standard", "hp_base": 16, "ac_base": 10, "attack_bonus": 2, "damage_die": "d6", "xp_award": 35,
     "description": "Świeży trup nieumarły, ledwie posklejany. Wolno chodzi, ale uderza bez bólu i wstaje po obaleniu."},
    {"key": "ghoul",          "label": "Ghul",                  "tier": "standard", "hp_base": 14, "ac_base": 13, "attack_bonus": 3, "damage_die": "d6", "xp_award": 50,
     "description": "Stworzenie żywiące się padliną — paznokcie jak haki, oczy jak węgielki. Skrada się po cmentarzach."},
    {"key": "gravedigger_zombie","label":"Zombie grabarza",     "tier": "standard", "hp_base": 18, "ac_base": 11, "attack_bonus": 3, "damage_die": "d8", "xp_award": 50,
     "description": "Wstały zmarły z łopatą w dłoni i pierścieniami świętych medalików na palcach. Wstrząsająco silny."},
    {"key": "hobgoblin",      "label": "Hobgoblin",             "tier": "standard", "hp_base": 14, "ac_base": 14, "attack_bonus": 3, "damage_die": "d6", "damage_bonus": 1, "xp_award": 50,
     "description": "Wyższy, mądrzejszy goblin w spiżowej zbroi. Dowodzi mniejszymi zielonoskórymi i posługuje się taktyką."},
    {"key": "lizardman",      "label": "Człowiek-jaszczur",     "tier": "standard", "hp_base": 16, "ac_base": 13, "attack_bonus": 3, "damage_die": "d8", "xp_award": 55,
     "description": "Wysoki gad-humanoid z bagien południa. Ogon jak bicz, język jak nóż — mówi sykiem w języku ludzi."},
    {"key": "kobold_warrior", "label": "Kobold wojownik",       "tier": "standard", "hp_base": 11, "ac_base": 13, "attack_bonus": 3, "damage_die": "d6", "xp_award": 35,
     "description": "Kobold w skórzanej zbroi z toporkiem. Sprytny i zdradziecki, podkłada pułapki nim staniesz do walki."},
    {"key": "cultist",        "label": "Sekciarz",              "tier": "standard", "hp_base": 12, "ac_base": 11, "attack_bonus": 3, "damage_die": "d6", "xp_award": 40,
     "description": "Owinięty w czarne szaty wyznawca zapomnianego boga. Modli się szepcząc imię, którego nie powinieneś znać."},
    {"key": "smuggler",       "label": "Przemytnik",            "tier": "standard", "hp_base": 13, "ac_base": 12, "dex_modifier": 1, "attack_bonus": 3, "damage_die": "d6", "xp_award": 40,
     "description": "Mężczyzna z bliznami po nożach i kieszeniami pełnymi ciemnych precjozów. Walczy tylko gdy nie da się uciec."},
    {"key": "ogre_young",     "label": "Młody ogr",             "tier": "standard", "hp_base": 22, "ac_base": 12, "attack_bonus": 4, "damage_die": "d10", "damage_bonus": 2, "xp_award": 80,
     "description": "Bydlęcego wzrostu ogr z maczugą zrobioną z kości słupa. Głupi, ale potężnie silny."},
    {"key": "mountain_lion",  "label": "Pantera górska",        "tier": "standard", "hp_base": 14, "ac_base": 14, "dex_modifier": 2, "attack_bonus": 4, "damage_die": "d8", "xp_award": 60,
     "description": "Cicha jak cień, bez ostrzeżenia spada z głazu. Pazury jak brzytwy, zęby długie na palec."},
    {"key": "swamp_witch_apprentice","label":"Uczennica bagiennej wiedźmy","tier":"standard","hp_base":11,"ac_base":12,"attack_bonus":3,"damage_die":"d6","xp_award":50,
     "description": "Młoda kobieta z błotem we włosach i woskową świecą w ręku. Zna kilka rzucanych klątw."},
    {"key": "cave_spider",    "label": "Pająk jaskiniowy duży", "tier": "standard", "hp_base": 13, "ac_base": 13, "dex_modifier": 2, "attack_bonus": 3, "damage_die": "d6", "xp_award": 50,
     "description": "Wielkości dorosłego psa, z włochatymi nogami i okrągłymi oczyma. Sieci grube jak liny — nie dasz się tak łatwo wyrwać."},
    {"key": "crow_swarm",     "label": "Stado wron",            "tier": "standard", "hp_base": 9, "ac_base": 13, "dex_modifier": 2, "attack_bonus": 2, "damage_die": "d6", "attacks_per_turn": 2, "xp_award": 50,
     "description": "Setki wron nadlatujących z krzykiem. Oślepiają i drapią — trzeba się rzucić na ziemię i okryć."},

    # ── ELITE (10) — serious threats, low fear ──
    {"key": "orc_warrior",    "label": "Orkowy wojownik",       "tier": "elite", "hp_base": 28, "ac_base": 15, "attack_bonus": 5, "damage_die": "d10", "damage_bonus": 2, "xp_award": 120,
     "description": "Postawny ork w żelaznej kolczudze z toporem dwuręcznym. Krzyczy z wściekłością przy każdym ciosie."},
    {"key": "ogre",           "label": "Ogr",                   "tier": "elite", "hp_base": 35, "ac_base": 13, "attack_bonus": 5, "damage_die": "d12", "damage_bonus": 3, "xp_award": 150,
     "description": "Trzymetrowy potwór z maczugą zbitą z całego pnia. Każde uderzenie strzaska deski, wytnie konia."},
    {"key": "troll_standard", "label": "Troll",                 "tier": "elite", "hp_base": 42, "ac_base": 15, "attack_bonus": 5, "damage_die": "d10", "damage_bonus": 2, "attacks_per_turn": 2, "xp_award": 200,
     "description": "Czterometrowy potwór z zielonkawą skórą. Regeneruje rany — chyba że zadasz mu obrażenia ogniem albo kwasem."},
    {"key": "dark_knight",    "label": "Czarny rycerz",         "tier": "elite", "hp_base": 38, "ac_base": 17, "attack_bonus": 6, "damage_die": "d10", "damage_bonus": 2, "xp_award": 180, "fear_aura": 0,
     "description": "Pełna pancerz płytowa, czarna jak smoła. Hełm zamknięty, w środku tylko cienie. Mówi szeptem, ale słyszysz to wyraźnie."},
    {"key": "vampire_spawn",  "label": "Pomiot wampira",        "tier": "elite", "hp_base": 30, "ac_base": 15, "dex_modifier": 2, "attack_bonus": 6, "damage_die": "d8", "damage_bonus": 2, "xp_award": 175,
     "description": "Wymizerowany trup z bladą skórą i czerwonymi oczyma. Pije krew, rzuca się jak zwierzę."},
    {"key": "mage_apprentice","label": "Uczeń maga",            "tier": "elite", "hp_base": 22, "ac_base": 12, "attack_bonus": 4, "damage_die": "d8", "damage_bonus": 1, "xp_award": 130,
     "description": "Młody adept w wełnianej szacie z krwawym brzegiem. Rzuca strzały z arkany i tworzy iluzje."},
    {"key": "gargoyle",       "label": "Gargulec",              "tier": "elite", "hp_base": 32, "ac_base": 17, "attack_bonus": 5, "damage_die": "d8", "damage_bonus": 2, "xp_award": 160,
     "description": "Wybudzony kamienny posąg z dachu katedry. Skrzydła z bazaltu, pazury jak dłuto rzeźbiarza."},
    {"key": "basilisk_young", "label": "Młody bazyliszek",      "tier": "elite", "hp_base": 26, "ac_base": 15, "attack_bonus": 5, "damage_die": "d10", "xp_award": 175,
     "description": "Dwumetrowy gad z grzywą kolców. Wzrok zmienia ciało w kamień — nie patrz wprost na jego oczy."},
    {"key": "dire_bear",      "label": "Niedźwiedź ogromny",    "tier": "elite", "hp_base": 40, "ac_base": 14, "attack_bonus": 5, "damage_die": "d12", "damage_bonus": 3, "xp_award": 180,
     "description": "Najwyższy niedźwiedź w lesie, z poszarpaną szczęką. Broni terytorium do ostatniego tchu."},
    {"key": "witch",          "label": "Wiedźma",               "tier": "elite", "hp_base": 24, "ac_base": 12, "attack_bonus": 4, "damage_die": "d8", "damage_bonus": 2, "xp_award": 165,
     "description": "Starka z czarnymi paznokciami i workiem z rzemiosła. Rzuca klątwy, które trudniej zdjąć niż założyć."},

    # ── BOSS (5) — final encounters, fear aura active ──
    {"key": "troll_lord",     "label": "Władca trolli",         "tier": "boss", "hp_base": 80, "ac_base": 16, "attack_bonus": 7, "damage_die": "2d8", "damage_bonus": 4, "attacks_per_turn": 2, "xp_award": 500, "fear_aura": 1, "fear_dc": 14,
     "description": "Pięciometrowy troll w skórzanym pancerzu z koron żelaznych. Trzyma w jednej dłoni maczugę z czaszką starego króla."},
    {"key": "dragon_young",   "label": "Młody smok",            "tier": "boss", "hp_base": 110, "ac_base": 18, "attack_bonus": 8, "damage_die": "2d10", "damage_bonus": 4, "attacks_per_turn": 2, "xp_award": 800, "fear_aura": 1, "fear_dc": 16,
     "description": "Niedoskonale rozwinięty smok wielkości stodoły. Łuski miedziane, oddech zostawia spalone połacie lasu."},
    {"key": "lich",           "label": "Lich",                  "tier": "boss", "hp_base": 90, "ac_base": 17, "attack_bonus": 7, "damage_die": "2d8", "damage_bonus": 3, "xp_award": 700, "fear_aura": 1, "fear_dc": 15,
     "description": "Nieumarły mag spętany własną złą wolą. W oczodołach migoczą zielone płomienie, dłoń kostna trzyma berło z czaszek."},
    {"key": "demon_lord",     "label": "Pan demonów",           "tier": "boss", "hp_base": 130, "ac_base": 18, "attack_bonus": 8, "damage_die": "2d10", "damage_bonus": 5, "attacks_per_turn": 2, "xp_award": 900, "fear_aura": 1, "fear_dc": 17,
     "description": "Pomarańczowoskóry demon z czterema ramionami i koroną z ognia. Mówi w języku, którego twoje uszy nie powinny słyszeć."},
    {"key": "ancient_vampire","label": "Pradawny wampir",       "tier": "boss", "hp_base": 100, "ac_base": 17, "dex_modifier": 3, "attack_bonus": 8, "damage_die": "2d8", "damage_bonus": 4, "attacks_per_turn": 2, "xp_award": 800, "fear_aura": 1, "fear_dc": 15,
     "description": "Tysiącletnia istota w szlacheckim stroju. Porusza się tak szybko, że niemal nie widać kroków, a ofiara rozumie zbyt późno, dlaczego cisza była zbyt cisza."},
]

# ── 50 NPCs ────────────────────────────────────────────────────────────────
# Fields: key, label, npc_type (neutral|merchant|quest_giver|ally), description,
#   personality_prompt (free-text Polish), is_shop
NPCS = [
    # ── Merchants (10) ──
    {"key": "blacksmith_radomir", "label": "Radomir Kowal", "npc_type": "merchant", "is_shop": 1,
     "description": "Krępy kowal z poparzonymi rękami i siwą brodą. Prowadzi kuźnię od trzech pokoleń.",
     "personality_prompt": "Mało gadatliwy. Mówi krótkimi zdaniami. Lubi dobrą stal, nie znosi marnotrawstwa. Jeśli gracz okaże szacunek dla rzemiosła, da zniżkę."},
    {"key": "alchemist_helena", "label": "Helena Alchemiczka", "npc_type": "merchant", "is_shop": 1,
     "description": "Smukła kobieta z czerwoną chustą na włosach i palcami poplamionymi ziołami. Zna każdą truciznę i każdy antydot.",
     "personality_prompt": "Profesjonalna i precyzyjna. Ostrożnie dobiera słowa. Nie pyta klientów po co potrzebują jej mikstur."},
    {"key": "fletcher_juriy",    "label": "Jurij Strzelnik",  "npc_type": "merchant", "is_shop": 1,
     "description": "Były łowczy, teraz wyrabia łuki i strzały. Lewe oko pokryte mleczną zasłoną.",
     "personality_prompt": "Spokojny i obserwujący. Zaczyna rozmowę od pytania o wagę i równowagę łuku. Nie cierpi pychy."},
    {"key": "scribe_tomislaw",   "label": "Tomislaw Skryba",  "npc_type": "merchant", "is_shop": 1,
     "description": "Łysiejący mężczyzna w pomiętej szacie. Pisze listy dla niepiśmiennych za skromną zapłatę.",
     "personality_prompt": "Plotkarski i ciekawski — wszystko spisuje, wszystko zapamiętuje. Czasem wymienia tajemnice za rabaty."},
    {"key": "herbalist_baba",    "label": "Babka Mira",       "npc_type": "merchant", "is_shop": 1,
     "description": "Staruszka z zakrzywionym nosem i workiem suszonych ziół. Mieszka samotnie na skraju lasu.",
     "personality_prompt": "Bezpośrednia i bez ogródek. Lubi nazywać rzeczy po imieniu. Patrzy dłużej niż wypada — wie więcej niż mówi."},
    {"key": "fishmonger_olek",   "label": "Olek Rybak",       "npc_type": "merchant", "is_shop": 1,
     "description": "Gruby człowiek o czerwonej twarzy, cuchnący rybą o każdej porze dnia.",
     "personality_prompt": "Głośny i gadatliwy. Krzyczy ceny zamiast je mówić. Zna każdą plotkę z portu."},
    {"key": "weaver_jadwiga",    "label": "Jadwiga Tkaczka",  "npc_type": "merchant", "is_shop": 1,
     "description": "Wdowa po żołnierzu, prowadzi mały warsztat tkacki. Sprzedaje ubrania i koce.",
     "personality_prompt": "Cicha i pracowita. Mówi tylko gdy zapytasz. Ma trzy córki na wydaniu — czasem zerka oceniająco."},
    {"key": "baker_florian",     "label": "Florian Piekarz",  "npc_type": "merchant", "is_shop": 1,
     "description": "Krzepki mężczyzna w białym fartuchu z plamami mąki. Wypieka chleb przed świtem.",
     "personality_prompt": "Dobroduszny, częstuje świeżymi bułkami zmęczonych wędrowców. Plotkarz na sposób dobrotliwy."},
    {"key": "jeweler_aleksand",  "label": "Aleksander Złotnik","npc_type":"merchant", "is_shop": 1,
     "description": "Wytwornie ubrany mężczyzna z lupą wciśniętą w oko. Prowadzi sklep z biżuterią pod znakiem trzech pereł.",
     "personality_prompt": "Wytrawny negocjator. Z każdą propozycją się kłóci, ale zawsze zostawia margines. Lubi piękne historie."},
    {"key": "fence_krukowski",   "label": "Krukowski",        "npc_type": "merchant", "is_shop": 1,
     "description": "Chudy mężczyzna z bliznami na rękach. Sprzedaje 'drobne pamiątki znalezione na drogach'.",
     "personality_prompt": "Podejrzliwy, mówi w pół-żartach. Nigdy nie pyta skąd ma się rzeczy. Przyjmie każdą rzecz bez świadków."},

    # ── Guards/officials (5) ──
    {"key": "captain_marek",     "label": "Kapitan Marek",    "npc_type": "neutral",
     "description": "Dowódca straży miejskiej. Wysoki, w pełnej zbroi z czerwonym pióropuszem.",
     "personality_prompt": "Surowy, sprawiedliwy. Nie znosi łapówek, ale uznaje prawdziwe zasługi. Mówi zwięźle."},
    {"key": "sergeant_borys",    "label": "Sierżant Borys",   "npc_type": "neutral",
     "description": "Bary jak beczki, twarz pomięta jak skóra wojownika. Drugi człowiek straży.",
     "personality_prompt": "Praktyczny i bezpośredni. Łatwo go przekupić piwem albo dobrą historią z pola walki."},
    {"key": "gate_keeper_bronek","label": "Bronek Bramowy",   "npc_type": "neutral",
     "description": "Niski, przebiegły strażnik bramy z notesem w dłoni. Notuje każdego, kto wchodzi i wychodzi.",
     "personality_prompt": "Wścibski, ale przekupny. Drobna moneta otwiera mu usta szerzej niż wino. Lubi wiedzieć."},
    {"key": "magistrate_iliasz", "label": "Iliasz Sędzia",    "npc_type": "neutral",
     "description": "Stary urzędnik w pomarańczowej szacie z herbem miasta. Sędzia od czterdziestu lat.",
     "personality_prompt": "Cyniczny i zmęczony. Słyszał wszystkie kłamstwa świata. Czasem przymyka oczy na drobne sprawy — gdy ktoś naprawdę nie ma wyjścia."},
    {"key": "tax_collector_pius","label": "Pius Poborca",     "npc_type": "neutral",
     "description": "Tłusty mężczyzna z księgą rachunkową pod pachą. Towarzyszą mu dwaj uzbrojeni pomocnicy.",
     "personality_prompt": "Chciwy, oślizgły. Mówi miodowo, ale każde słowo to kalkulacja. Pożycza sobie z miejskiej kasy."},

    # ── Peasants/villagers (10) ──
    {"key": "farmer_jacek",      "label": "Jacek Rolnik",     "npc_type": "neutral",
     "description": "Krzepki gospodarz z brudnymi rękami i siwą bródką. Uprawia jęczmień za miastem.",
     "personality_prompt": "Spokojny, mało gadatliwy. Skarży się na pogodę i podatki — zawsze. Dobrosąsiedzki, gdy potrzebują się czegoś dowiedzieć."},
    {"key": "washerwoman_anka",  "label": "Anka Praczka",     "npc_type": "neutral",
     "description": "Mocna kobieta z czerwonymi od mydlin rękami. Pierze dla bogatych domów.",
     "personality_prompt": "Wie wszystko o wszystkich — bo pierze ich brudne ubrania. Plotkuje za drobnostki."},
    {"key": "milkmaid_basia",    "label": "Basia Dojarka",    "npc_type": "neutral",
     "description": "Młoda dziewczyna z koszem na ramieniu, wracająca z gospodarstwa. Często śpiewa pod nosem.",
     "personality_prompt": "Wesoła i ufna. Łatwo zaufa nieznajomemu, czasem opowie więcej niż powinna."},
    {"key": "beggar_grzybek",    "label": "Grzybek Żebrak",   "npc_type": "neutral",
     "description": "Pomarszczony człowiek bez nogi, siedzący przy bramach świątyni. Twierdzi że służył w wojnie czterech baronów.",
     "personality_prompt": "Sprytny, choć udaje głupiego. Słyszy wszystko, bo nikt nie zauważa, że tam jest. Sprzedaje informacje za miedziaki."},
    {"key": "drunkard_witek",    "label": "Witek Pijaczyna",  "npc_type": "neutral",
     "description": "Były ławnik, teraz mieszka pod murem karczmy. Pamięta lepsze dni — i wie wiele.",
     "personality_prompt": "Bełkotliwy i sentymentalny. Trzeba mu postawić kufel, by zaczął gadać. Wtedy mówi rzeczy, których nie powinieneś znać."},
    {"key": "woodcutter_jerzy",  "label": "Jerzy Drwal",      "npc_type": "neutral",
     "description": "Postawny człowiek z siekierą w pasie. Zna las jak własne podwórko.",
     "personality_prompt": "Cichy i wytrwały. Mówi krótko, ale jego rady o lesie ratują życie."},
    {"key": "fishwife_dorota",   "label": "Dorota Targowa",   "npc_type": "neutral",
     "description": "Krzykliwa baba o czerwonej twarzy, sprzedaje ryby na rynku.",
     "personality_prompt": "Głośna i wulgarna. Krzyczy ceny na pół ulicy. W rzeczywistości obserwuje wszystko, choć udaje, że nie."},
    {"key": "stable_boy_pawelek","label": "Pawełek Stajenny", "npc_type": "neutral",
     "description": "Chudy chłopak około dwunastu lat, zawsze umorusany. Karmi konie w karczmie pod 'Złotym Dzikiem'.",
     "personality_prompt": "Cichy i nieśmiały. Boi się dorosłych, ale lubi konie. Da nieoczekiwane wskazówki, gdy zaufa."},
    {"key": "herald_witold",     "label": "Witold Heroldowy", "npc_type": "neutral",
     "description": "Mężczyzna w jaskrawej szacie z miedzianym rogiem. Ogłasza dekrety na rynku.",
     "personality_prompt": "Patetyczny, lubi własny głos. Recytuje obwieszczenia z całym dramatyzmem. Plotkarz zawodowy."},
    {"key": "child_marcyś",      "label": "Marcyś (chłopiec)","npc_type": "neutral",
     "description": "Sześcioletni chłopiec z brudną twarzą i drewnianym mieczem. Bawi się sam przy studni.",
     "personality_prompt": "Ciekawski i bezpośredni. Pyta o wszystko. Czasem widział rzeczy, których dorośli nie chcą uwierzyć."},

    # ── Nobles (5) ──
    {"key": "baron_włodzimierz", "label": "Baron Włodzimierz","npc_type": "neutral",
     "description": "Wytwornie ubrany szlachcic w średnim wieku. Włada okolicznymi wioskami z surową ręką.",
     "personality_prompt": "Wyniosły, choć formalnie uprzejmy. Mówi z chłodnym dystansem. Nie cierpi nieuległości."},
    {"key": "baroness_kaczanska","label":"Baronowa Kaczańska","npc_type":"neutral",
     "description":"Wdowa po baronie, ubrana w czarne aksamity. Słynie z mądrości i siły woli.",
     "personality_prompt":"Inteligentna i skupiona. Mówi mało, ale precyzyjnie. Czasem testuje rozmówcę zaskakującymi pytaniami."},
    {"key": "courtier_donald",   "label": "Donald Dworak",    "npc_type": "neutral",
     "description": "Wymuskany dworzanin w jedwabnych szatach. Wyposażony w sztylet w bucie i tysiąc pochlebstw.",
     "personality_prompt": "Lizodupski i fałszywy. Komplementy płyną mu z ust jak woda, ale każde słowo to gra. Niebezpieczny, gdy go obrazisz."},
    {"key": "knight_errant_radek","label":"Radek Rycerz Wędrowny","npc_type":"ally",
     "description":"Wysoki rycerz w wytartej kolczudze, jadący od zamku do zamku w poszukiwaniu czynów.",
     "personality_prompt":"Honorowy, ale zbankrutowany. Mówi z dumą, choć torba bez monet. Pomoże w słusznej sprawie."},
    {"key": "exiled_lord_szymon","label":"Szymon — wygnaniec","npc_type":"neutral",
     "description":"Mężczyzna w pomiętej szlacheckiej szacie z bliznami od miecza. Stracił ziemie w wojnie domowej.",
     "personality_prompt":"Gorzki i zawiedziony. Pije za dużo, mówi o zemście, gdy się napije."},

    # ── Priests/mystics (5) ──
    {"key": "priest_anatol",     "label": "Anatol Kapłan",    "npc_type": "ally",
     "description": "Starszy kapłan w wełnianej szacie z drewnianym medalionem. Prowadzi małą świątynię na wzgórzu.",
     "personality_prompt": "Łagodny i cierpliwy. Słucha każdej spowiedzi bez osądu. Czasem prosi o przysługę w zamian za błogosławieństwo."},
    {"key": "monk_brat_serapion","label":"Brat Serapion (mnich)","npc_type":"neutral",
     "description":"Łysy mnich w brązowej habicie z różańcem z kości. Przemierza kraj pieszo.",
     "personality_prompt":"Spokojny, mądry. Mówi sentencjami, które wydają się banalne — ale po dwóch dniach zaczynają mieć sens."},
    {"key": "hermit_pankracy",   "label": "Pankracy Pustelnik","npc_type":"neutral",
     "description":"Brodaty starzec mieszkający w skalnej grocie nad wodospadem. Karmi dzikie zwierzęta i mówi do drzew.",
     "personality_prompt":"Dziwny, ale życzliwy. Mówi w zagadkach i parabolach. Zna lokalne legendy lepiej niż ktokolwiek."},
    {"key": "oracle_xena",       "label": "Wieszczka Xenia",  "npc_type": "quest_giver",
     "description": "Bladolica kobieta z białymi oczyma. Mieszka w wieży na skraju miasta, przyjmuje na seansach.",
     "personality_prompt": "Patrzy w jakąś dal nie z tego świata. Mówi krótkimi zdaniami, czasem proroctwami. Bierze monety za seans."},
    {"key": "witch_jaga",        "label": "Jaga (czarownica)","npc_type":"neutral",
     "description":"Czarownica mieszkająca w chacie z kości w głębi lasu. Lokalne dzieci straszone są jej imieniem.",
     "personality_prompt":"Sarkastyczna i zgryźliwa. Pomoże, ale za swoją cenę — i nigdy w sposób, jaki się spodziewasz."},

    # ── Criminals (5) ──
    {"key": "pickpocket_zenon",  "label": "Zenon Kieszonkowiec","npc_type":"neutral",
     "description":"Cieniutki młodzieniec z szerokim uśmiechem. Pracuje na rynku w godzinach szczytu.",
     "personality_prompt":"Czarujący i bezczelny. Kłamie ze stylem. Można go najmować do drobnych zadań."},
    {"key": "fence_smuggler_wlad","label":"Władek Paser",     "npc_type":"merchant","is_shop":1,
     "description":"Człowiek z czarną przepaską na oku. Prowadzi 'sklep ze starociami' za karczmą.",
     "personality_prompt":"Bezduszny i wyrachowany. Płaci grosze, sprzedaje za majątek. Lojalny tylko wobec własnego portfela."},
    {"key": "brigand_leader_rolf","label":"Rolf — herszt rozbójników","npc_type":"neutral",
     "description":"Wielki brodacz z czerwonym kapeluszem. Dowodzi bandą w lasach na północ od miasta.",
     "personality_prompt":"Ryzykant, ale racjonalny. Negocjuje, gdy widzi większy zysk. Nie znosi zdrady wśród swoich."},
    {"key": "cutthroat_milena",  "label": "Milena Skrytobójczyni","npc_type":"neutral",
     "description":"Cicha kobieta w ciemnym płaszczu. Twarz częściowo zakryta chustą, oczy zielone.",
     "personality_prompt":"Mówi minimum. Każde słowo kalkulowane. Przyjmuje zlecenia, nie pyta o powody."},
    {"key": "thief_jurek",       "label": "Jurek Włamywacz",  "npc_type": "neutral",
     "description": "Smukły mężczyzna z czarną maską na pasie. Specjalista od kłódek i bramek.",
     "personality_prompt": "Profesjonalny i zorganizowany. Nie pije w pracy. Płaci dobrze za informację o wartościowych celach."},

    # ── Mysterious/quest-givers (10) ──
    {"key": "wanderer_grim",     "label": "Grim Wędrowiec",   "npc_type": "neutral",
     "description": "Wysoki człowiek w szarym płaszczu z kapturem. Nie zdejmuje go nawet przy ognisku.",
     "personality_prompt": "Tajemniczy. Odpowiada pytaniami. Wie zaskakująco dużo o miejscach, gdzie nie powinien być."},
    {"key": "stranger_pale",     "label": "Bladolicy Nieznajomy","npc_type":"neutral",
     "description":"Wysoki chudy mężczyzna z bladą cerą. Zawsze siedzi sam w karczmie, gapi się w ogień.",
     "personality_prompt":"Wypowiada krótkie zdania o dziwnej treści. Wydaje się być nie z tego świata."},
    {"key": "dying_messenger",   "label": "Konający Posłaniec","npc_type":"quest_giver",
     "description":"Ranny człowiek leżący przy drodze, z listem zaklejonym pieczęcią lakową w dłoni.",
     "personality_prompt":"Mówi z trudem. Prosi gracza o dostarczenie listu konkretnej osobie. Umiera w ciągu godziny."},
    {"key": "masked_figure",     "label": "Postać w masce",   "npc_type": "neutral",
     "description": "Osoba o niemożliwym do określenia płci, w czarnym płaszczu i białej masce z porcelany.",
     "personality_prompt": "Mówi z zaskakująco głębokim głosem (zmienionym). Płaci za usługi w złocie, znika bez śladu."},
    {"key": "prophet_madman",    "label": "Prorok Szaleniec", "npc_type": "neutral",
     "description": "Bosy mężczyzna w łachmanach, krzyczący na placu o końcu świata. Bywa wyrzucany przez straż.",
     "personality_prompt": "Niespójny, ale czasem mówi prawdziwe rzeczy. Trzeba przesłuchać dziesięć szaleństw, by wyłapać jedno proroctwo."},
    {"key": "retired_knight_tym","label":"Sir Tymoteusz (emerytowany rycerz)","npc_type":"quest_giver",
     "description":"Stary rycerz prowadzący teraz karczmę 'Pod Słomianym Lwem'. Tarcza wisi nad kominkiem.",
     "personality_prompt":"Ojcowski, gawędziarski. Opowiada anegdoty z młodości. Czasem prosi gracza o pomoc w sprawach 'jakimi sam dawno by się zajął'."},
    {"key": "widow_amelia",      "label": "Amelia — wdowa po zabitym","npc_type":"quest_giver",
     "description":"Kobieta w czarnych szatach. Mąż został zabity przez rozbójników. Szuka sprawiedliwości — albo zemsty.",
     "personality_prompt":"Twarda i zdeterminowana. Zapłaci złotem ze sprzedanej biżuterii za zlikwidowanie morderców."},
    {"key": "scholar_dziekan",   "label": "Dziekan Skarbowski","npc_type":"quest_giver",
     "description":"Stary akademik z trzęsącymi się rękami. Szuka konkretnej księgi w zaginionej bibliotece klasztoru.",
     "personality_prompt":"Roztargniony, ale precyzyjny w detalach. Płaci dobrze za każdy stary tom, który mu przyniesiesz."},
    {"key": "captain_seeking",   "label": "Kapitan Frydrich (poszukuje załogi)","npc_type":"quest_giver",
     "description":"Brodaty kapitan statku w skórzanym kaftanie. Stoi przed gospodą z wywieszką 'Marynarze potrzebni!'.",
     "personality_prompt":"Bezceremonialny i prosty. Płaci po skończonej misji. Nie znosi tchórzy."},
    {"key": "father_lost_child", "label": "Eustachy — ojciec zaginionego dziecka","npc_type":"quest_giver",
     "description":"Mężczyzna w średnim wieku z czerwonymi od łez oczyma. Trzyma w dłoni małą lalkę.",
     "personality_prompt":"Rozpaczliwy. Mówi szybko, połyka słowa. Odda wszystko, co ma — i więcej — za córkę."},
]

# ── Loot composition per tier ─────────────────────────────────────────────
# (gold_min, gold_max, drop_chance, [(slot, key, weight, qty_min, qty_max), ...])
# slot is "items" | "consumables" | "weapons" (mapped to *_key column).
LOOT_BY_TIER = {
    "weak": {
        "gold": (0, 3), "drop_chance": 0.5,
        "drops": [
            ("consumables", "hardtack", 40, 1, 1),
            ("consumables", "bandage", 25, 1, 1),
            ("consumables", "apple", 20, 1, 1),
            ("items",       "rope_hemp", 10, 1, 1),
        ],
    },
    "standard": {
        "gold": (3, 12), "drop_chance": 0.75,
        "drops": [
            ("consumables", "potion_healing_small", 35, 1, 1),
            ("consumables", "bandage", 20, 1, 2),
            ("consumables", "antitoxin_vial", 10, 1, 1),
            ("weapons",     "dagger", 15, 1, 1),
            ("weapons",     "handaxe", 10, 1, 1),
            ("items",       "torch", 15, 1, 2),
            ("items",       "rope_hemp", 10, 1, 1),
            ("items",       "leather_gloves", 8, 1, 1),
        ],
    },
    "elite": {
        "gold": (15, 50), "drop_chance": 0.9,
        "drops": [
            ("consumables", "potion_healing_medium", 30, 1, 1),
            ("consumables", "potion_mana_small", 15, 1, 1),
            ("consumables", "alchemist_fire", 12, 1, 1),
            ("consumables", "vial_of_acid", 10, 1, 1),
            ("weapons",     "longsword", 12, 1, 1),
            ("weapons",     "battleaxe", 10, 1, 1),
            ("weapons",     "shortbow", 8, 1, 1),
            ("items",       "chainmail_shirt", 8, 1, 1),
            ("items",       "studded_leather", 8, 1, 1),
            ("items",       "iron_helm", 8, 1, 1),
            ("items",       "lockpicks", 5, 1, 1),
        ],
    },
    "boss": {
        "gold": (75, 250), "drop_chance": 1.0,
        "drops": [
            ("consumables", "potion_healing_large", 25, 1, 2),
            ("consumables", "potion_mana_large", 20, 1, 1),
            ("consumables", "scroll_fireball", 10, 1, 1),
            ("consumables", "scroll_shield", 12, 1, 1),
            ("weapons",     "greatsword", 12, 1, 1),
            ("weapons",     "greataxe", 10, 1, 1),
            ("weapons",     "longbow", 8, 1, 1),
            ("items",       "half_plate", 8, 1, 1),
            ("items",       "ring_of_protection", 5, 1, 1),
            ("items",       "amulet_of_health", 5, 1, 1),
            ("items",       "signet_ring", 15, 1, 1),
            ("items",       "ancient_scroll", 12, 1, 1),
            ("items",       "magic_compass", 5, 1, 1),
        ],
    },
}


def main() -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        # 1) Seed enemies
        n_enem = 0
        for e in ENEMIES:
            conn.execute(
                """
                INSERT OR REPLACE INTO game_config_enemies
                    (key, label, hp_base, ac_base, attack_bonus, damage_die, description,
                     tier, attacks_per_turn, damage_bonus, damage_type, xp_award,
                     dex_modifier, fear_aura, fear_dc, is_active, review_status, drop_chance)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'physical', ?, ?, ?, ?, 1, 'permanent', ?)
                """,
                (
                    e["key"], e["label"], int(e["hp_base"]), int(e["ac_base"]),
                    int(e["attack_bonus"]), e["damage_die"], e["description"],
                    e["tier"], int(e.get("attacks_per_turn", 1)),
                    int(e.get("damage_bonus", 0)),
                    int(e.get("xp_award", 0)),
                    int(e.get("dex_modifier", 0)),
                    int(e.get("fear_aura", 0)),
                    int(e.get("fear_dc", 12)),
                    float(LOOT_BY_TIER.get(e["tier"], {}).get("drop_chance", 0.75)),
                ),
            )
            n_enem += 1
        print(f"✓ Enemies: {n_enem}")

        # 2) Loot tables — one per enemy
        n_loot = 0
        n_entries = 0
        for e in ENEMIES:
            tier_cfg = LOOT_BY_TIER.get(e["tier"], LOOT_BY_TIER["standard"])
            table_key = f"loot_{e['key']}"
            # Insert/update the loot table itself
            conn.execute(
                """
                INSERT OR REPLACE INTO game_config_loot_tables
                    (key, label, description, gold_min, gold_max, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (
                    table_key,
                    f"Łupy: {e['label']}",
                    f"Auto-generowana tabela łupów dla {e['label']} (tier {e['tier']}).",
                    int(tier_cfg["gold"][0]), int(tier_cfg["gold"][1]),
                ),
            )
            # Link enemy → loot_table
            conn.execute(
                "UPDATE game_config_enemies SET loot_table_key = ? WHERE key = ?",
                (table_key, e["key"]),
            )
            # Wipe existing entries (idempotent re-seed)
            conn.execute(
                "DELETE FROM game_config_loot_entries WHERE loot_table_key = ?",
                (table_key,),
            )
            for slot, item_key, weight, qmin, qmax in tier_cfg["drops"]:
                col_key = {"items": "item_key", "consumables": "consumable_key", "weapons": "weapon_key"}[slot]
                conn.execute(
                    f"""
                    INSERT INTO game_config_loot_entries
                        (loot_table_key, {col_key}, weight, qty_min, qty_max)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (table_key, item_key, int(weight), int(qmin), int(qmax)),
                )
                n_entries += 1
            n_loot += 1
        print(f"✓ Loot tables: {n_loot} (with {n_entries} entries total)")

        # 3) Seed NPCs
        n_npc = 0
        for n in NPCS:
            conn.execute(
                """
                INSERT OR REPLACE INTO npcs
                    (key, label, npc_type, description, personality_json,
                     personality_prompt, is_shop, shop_inventory_json,
                     is_active, review_status, keyword_triggers)
                VALUES (?, ?, ?, ?, '{}', ?, ?, '[]', 1, 'permanent', '[]')
                """,
                (
                    n["key"], n["label"], n["npc_type"], n["description"],
                    n.get("personality_prompt", ""),
                    int(n.get("is_shop", 0)),
                ),
            )
            n_npc += 1
        print(f"✓ NPCs: {n_npc}")

        conn.commit()

        # Sanity
        for tbl in ("game_config_enemies", "game_config_loot_tables",
                    "game_config_loot_entries", "npcs"):
            cnt = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            print(f"  {tbl}: {cnt} rows total")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
