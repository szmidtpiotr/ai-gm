#!/usr/bin/env python3
"""Seed AI-GM DEV database with extra weapons, armor, items, and consumables.

Idempotent (INSERT OR REPLACE on canonical keys). Polish labels + descriptions.
Run inside backend container:
    docker exec ai-gm-dev-backend-1 python /app/scripts/seed_extra_content.py

Or from host:
    ssh claude@192.168.1.61 'docker exec ai-gm-dev-backend-1 python /tmp/seed_extra_content.py'
"""
import json
import sqlite3
import sys

DB_PATH = "/data/ai_gm.db"

# ── 30 WEAPONS ─────────────────────────────────────────────────────────────
# Schema: key, label, damage_die, linked_stat, allowed_classes (JSON),
#   description, weapon_type (melee|ranged|spell), two_handed, finesse,
#   range_m, weight_kg, note, value_gp, weapon_slot, approved=1
WEAPONS: list[dict] = [
    # ── melee swords ──
    {"key": "longsword", "label": "Długi miecz", "damage_die": "d8", "linked_stat": "STR",
     "allowed_classes": ["warrior"], "weapon_type": "melee", "two_handed": 0,
     "weight_kg": 1.5, "value_gp": 15,
     "description": "Klasyczny obosieczny miecz rycerski o smukłej, dobrze wyważonej klindze. Pewny towarzysz w pojedynku jeden na jednego."},
    {"key": "greatsword", "label": "Wielki miecz", "damage_die": "2d6", "linked_stat": "STR",
     "allowed_classes": ["warrior"], "weapon_type": "melee", "two_handed": 1,
     "weight_kg": 3.0, "value_gp": 50, "weapon_slot": "two_handed",
     "description": "Potężna, oburęczna broń długości człowieka. Każde uderzenie potrafi rozłupać tarczę albo zdjąć hełm."},
    {"key": "dagger", "label": "Sztylet", "damage_die": "d4", "linked_stat": "DEX",
     "allowed_classes": ["warrior", "rogue", "scholar"], "weapon_type": "melee", "finesse": 1,
     "weight_kg": 0.3, "value_gp": 3,
     "description": "Krótki, zakrzywiony nóż. Łatwy do ukrycia w cholewce buta lub za pasem; nieoceniony w ciasnych zaułkach."},
    {"key": "rapier", "label": "Rapier", "damage_die": "d8", "linked_stat": "DEX",
     "allowed_classes": ["warrior", "rogue"], "weapon_type": "melee", "finesse": 1,
     "weight_kg": 1.1, "value_gp": 25,
     "description": "Smukła, finezyjna broń kłująca z koszem na rękojeści. Stworzona do dźgnięć precyzyjnych jak kropla deszczu."},
    {"key": "scimitar", "label": "Bułat", "damage_die": "d6", "linked_stat": "DEX",
     "allowed_classes": ["warrior", "rogue"], "weapon_type": "melee", "finesse": 1,
     "weight_kg": 1.4, "value_gp": 25,
     "description": "Zakrzywiona klinga z dalekich, południowych krain. Tnie szybciej niż prosty miecz, choć trudniej parować nim ciosy."},
    {"key": "falchion", "label": "Tasak bojowy", "damage_die": "d8", "linked_stat": "STR",
     "allowed_classes": ["warrior"], "weapon_type": "melee",
     "weight_kg": 2.0, "value_gp": 18,
     "description": "Ciężka jednoręczna klinga z szerokim ostrzem. Bardziej tasak rzeźnicki niż miecz — i właśnie tak się nim walczy."},
    {"key": "sabre", "label": "Szabla", "damage_die": "d8", "linked_stat": "DEX",
     "allowed_classes": ["warrior", "rogue"], "weapon_type": "melee", "finesse": 1,
     "weight_kg": 1.3, "value_gp": 22,
     "description": "Zakrzywiona, jednoostrzowa klinga z prostą rękojeścią. Lekka i szybka, ulubiona broń kawalerzystów."},
    # ── melee axes ──
    {"key": "handaxe", "label": "Topór ręczny", "damage_die": "d6", "linked_stat": "STR",
     "allowed_classes": ["warrior", "rogue"], "weapon_type": "melee",
     "weight_kg": 1.0, "value_gp": 5,
     "description": "Lekki topór jednoręczny. Przydatny w walce, w obozie i przy ścinaniu zarośli na ścieżce."},
    {"key": "battleaxe", "label": "Topór bojowy", "damage_die": "d8", "linked_stat": "STR",
     "allowed_classes": ["warrior"], "weapon_type": "melee",
     "weight_kg": 1.8, "value_gp": 20,
     "description": "Solidny topór o szerokim ostrzu i drewnianym trzonku okutym żelazem. Brutalny w zwarciu, miażdży zarówno deski, jak i kości."},
    {"key": "greataxe", "label": "Wielki topór", "damage_die": "d12", "linked_stat": "STR",
     "allowed_classes": ["warrior"], "weapon_type": "melee", "two_handed": 1,
     "weight_kg": 3.2, "value_gp": 45, "weapon_slot": "two_handed",
     "description": "Oburęczna broń o długim trzonku i ostrzu jak półksiężyc. Cios trafia rzadko, ale gdy trafi — przerywa łańcuch zbroi i kręgosłup za nim."},
    {"key": "throwing_axe", "label": "Topór miotany", "damage_die": "d6", "linked_stat": "STR",
     "allowed_classes": ["warrior", "rogue"], "weapon_type": "ranged",
     "range_m": 10, "weight_kg": 0.8, "value_gp": 7,
     "description": "Mały topór zrównoważony do rzucania. Świszczy w powietrzu z chrapliwym jękiem zanim wbije się w cel."},
    # ── melee blunt ──
    {"key": "club", "label": "Maczuga", "damage_die": "d4", "linked_stat": "STR",
     "allowed_classes": ["warrior", "scholar", "rogue"], "weapon_type": "melee",
     "weight_kg": 1.0, "value_gp": 1,
     "description": "Prosty, ciężki kij. Broń biedaków i wieśniaków — ale solidne uderzenie po ciemku załatwia sprawę."},
    {"key": "mace", "label": "Buzdygan", "damage_die": "d6", "linked_stat": "STR",
     "allowed_classes": ["warrior"], "weapon_type": "melee",
     "weight_kg": 1.8, "value_gp": 12,
     "description": "Metalowa głowica z żebrami osadzona na drewnianym trzonku. Łamie zbroję płytową tam, gdzie miecz tylko ślizga się po niej."},
    {"key": "warhammer", "label": "Młot bojowy", "damage_die": "d8", "linked_stat": "STR",
     "allowed_classes": ["warrior"], "weapon_type": "melee",
     "weight_kg": 2.2, "value_gp": 25,
     "description": "Krótki młot z kolcem po drugiej stronie obucha. Stworzony do walki z opancerzonymi przeciwnikami — kolec szuka szczelin w zbroi."},
    {"key": "maul", "label": "Olbrzymi młot", "damage_die": "2d6", "linked_stat": "STR",
     "allowed_classes": ["warrior"], "weapon_type": "melee", "two_handed": 1,
     "weight_kg": 4.5, "value_gp": 35, "weapon_slot": "two_handed",
     "description": "Oburęczny młot z masywną głowicą. Każdy cios brzmi jak grom uderzający w żelazne wrota."},
    {"key": "flail", "label": "Cep bojowy", "damage_die": "d8", "linked_stat": "STR",
     "allowed_classes": ["warrior"], "weapon_type": "melee",
     "weight_kg": 1.6, "value_gp": 15,
     "description": "Kula nabita kolcami na łańcuchu, połączona z drewnianym trzonkiem. Niebezpieczna nawet dla użytkownika — ale omija tarcze."},
    {"key": "morningstar", "label": "Gwiazda zaranna", "damage_die": "d8", "linked_stat": "STR",
     "allowed_classes": ["warrior"], "weapon_type": "melee",
     "weight_kg": 1.8, "value_gp": 18,
     "description": "Buzdygan z głowicą najeżoną kolcami. Każde uderzenie zostawia rany kłute oprócz złamań."},
    # ── melee polearm ──
    {"key": "spear", "label": "Włócznia", "damage_die": "d6", "linked_stat": "STR",
     "allowed_classes": ["warrior", "scholar"], "weapon_type": "melee",
     "weight_kg": 1.5, "value_gp": 5,
     "description": "Długie drzewce zakończone żelaznym grotem. Można nią walczyć w zwarciu albo rzucać na średni dystans."},
    {"key": "halberd", "label": "Halabarda", "damage_die": "d10", "linked_stat": "STR",
     "allowed_classes": ["warrior"], "weapon_type": "melee", "two_handed": 1,
     "weight_kg": 2.8, "value_gp": 30, "weapon_slot": "two_handed",
     "description": "Hybrydowa broń drzewcowa: ostrze siekiery, grot włóczni i hak do ściągania jeźdźców z konia. Symbol straży miejskich."},
    {"key": "glaive", "label": "Glewia", "damage_die": "d10", "linked_stat": "STR",
     "allowed_classes": ["warrior"], "weapon_type": "melee", "two_handed": 1,
     "weight_kg": 2.6, "value_gp": 28, "weapon_slot": "two_handed",
     "description": "Długie drzewce zakończone pojedynczym, zakrzywionym ostrzem. Pozwala trzymać wrogów na dystans."},
    {"key": "pike", "label": "Pika", "damage_die": "d10", "linked_stat": "STR",
     "allowed_classes": ["warrior"], "weapon_type": "melee", "two_handed": 1,
     "weight_kg": 2.5, "value_gp": 22, "weapon_slot": "two_handed",
     "description": "Bardzo długa włócznia używana w szyku piechoty. Pojedyncza nie robi wrażenia — ale ściana pik zatrzyma każdą szarżę."},
    # ── ranged ──
    {"key": "longbow", "label": "Łuk długi", "damage_die": "d8", "linked_stat": "DEX",
     "allowed_classes": ["warrior", "rogue"], "weapon_type": "ranged", "two_handed": 1,
     "range_m": 50, "weight_kg": 1.0, "value_gp": 50, "weapon_slot": "two_handed",
     "description": "Wysoki łuk z cisu albo jaworu. Naciągnięty wymaga siły i wprawy — ale strzela dalej i celniej niż krótki."},
    {"key": "crossbow", "label": "Kusza", "damage_die": "d10", "linked_stat": "DEX",
     "allowed_classes": ["warrior", "rogue", "scholar"], "weapon_type": "ranged", "two_handed": 1,
     "range_m": 30, "weight_kg": 2.0, "value_gp": 35, "weapon_slot": "two_handed",
     "description": "Mechaniczny łuk o krótkim, sztywnym łuczysku. Powolna w przeładowaniu, ale jej bełty przebijają kolczugę."},
    {"key": "heavy_crossbow", "label": "Ciężka kusza", "damage_die": "d12", "linked_stat": "DEX",
     "allowed_classes": ["warrior"], "weapon_type": "ranged", "two_handed": 1,
     "range_m": 35, "weight_kg": 4.0, "value_gp": 75, "weapon_slot": "two_handed",
     "description": "Potężna kusza z wycyrklowaną korbą do napinania. Strzela raz na minutę, ale jej bełt przebije pełną zbroję."},
    {"key": "hand_crossbow", "label": "Ręczna kusza", "damage_die": "d6", "linked_stat": "DEX",
     "allowed_classes": ["rogue"], "weapon_type": "ranged",
     "range_m": 15, "weight_kg": 1.2, "value_gp": 75,
     "description": "Mała kusza dająca się obsługiwać jedną ręką. Ulubiona broń skrytobójców — łatwo ją ukryć pod płaszczem."},
    {"key": "throwing_knife", "label": "Nóż do rzucania", "damage_die": "d4", "linked_stat": "DEX",
     "allowed_classes": ["warrior", "rogue"], "weapon_type": "ranged", "finesse": 1,
     "range_m": 10, "weight_kg": 0.2, "value_gp": 2,
     "description": "Cienki, wyważony stalowy nóż. Wirując w locie szuka miękkiego brzucha albo gardła."},
    {"key": "javelin", "label": "Oszczep", "damage_die": "d6", "linked_stat": "STR",
     "allowed_classes": ["warrior"], "weapon_type": "ranged",
     "range_m": 20, "weight_kg": 1.2, "value_gp": 4,
     "description": "Lekka włócznia zaprojektowana do rzucania. Może też posłużyć w zwarciu, gdy zabraknie czasu."},
    {"key": "sling", "label": "Proca", "damage_die": "d4", "linked_stat": "DEX",
     "allowed_classes": ["warrior", "rogue", "scholar"], "weapon_type": "ranged",
     "range_m": 25, "weight_kg": 0.1, "value_gp": 1,
     "description": "Skórzany pasek z gniazdem na kamień. Broń pasterzy i biedoty — w doświadczonych dłoniach zabija orka jednym strzałem w skroń."},
    # ── spell focus (Scholar) ──
    {"key": "wand", "label": "Różdżka arkana", "damage_die": "d6", "linked_stat": "INT",
     "allowed_classes": ["scholar"], "weapon_type": "spell",
     "range_m": 20, "weight_kg": 0.2, "value_gp": 40,
     "description": "Wypolerowana różdżka z rdzeniem z rogu jednorożca albo zębu smoka. Skupia magiczną wolę kastującego w wąską wiązkę."},
    {"key": "orb", "label": "Sfera mocy", "damage_die": "d6", "linked_stat": "INT",
     "allowed_classes": ["scholar"], "weapon_type": "spell",
     "range_m": 15, "weight_kg": 0.5, "value_gp": 60,
     "description": "Szklana lub kryształowa kula wypełniona migoczącym mgiełką światłem. Trzymana w drugiej ręce — pozwala rzucać zaklęcia precyzyjniej."},
]

# ── 30 ARMORS (game_config_items with item_type='armor') ───────────────────
# Schema: key, label, item_type='armor', description, value_gp, weight_kg,
#   ac_bonus, armor_coverage, allowed_classes (JSON), note, approved=1
ARMORS: list[dict] = [
    # ── light armor ──
    {"key": "padded_armor", "label": "Pikowana zbroja", "ac_bonus": 1, "weight_kg": 4.0,
     "value_gp": 5, "armor_coverage": "torso", "allowed_classes": ["warrior", "rogue", "scholar"],
     "description": "Warstwa grubo pikowanej tkaniny z konopnym wypełnieniem. Tłumi cios maczugi, ale przed mieczem nie obroni."},
    {"key": "leather_armor", "label": "Skórzana zbroja", "ac_bonus": 1, "weight_kg": 5.0,
     "value_gp": 10, "armor_coverage": "torso", "allowed_classes": ["warrior", "rogue", "scholar"],
     "description": "Garbowana skóra wołowa naszywana na lnianą podkładkę. Cicha i wygodna — ulubiona zbroja zwiadowców i łowców."},
    {"key": "studded_leather", "label": "Skóra ćwiekowana", "ac_bonus": 2, "weight_kg": 6.0,
     "value_gp": 45, "armor_coverage": "torso", "allowed_classes": ["warrior", "rogue"],
     "description": "Skórzana zbroja wzmocniona setkami żelaznych ćwieków. Brzęczy ledwo słyszalnie i chroni przed cięciami."},
    {"key": "hide_armor", "label": "Zbroja ze skór", "ac_bonus": 2, "weight_kg": 6.5,
     "value_gp": 10, "armor_coverage": "torso", "allowed_classes": ["warrior", "rogue"],
     "description": "Surowe skóry zwierzęce zszyte i wzmocnione kośćmi. Cuchnie dziką zwierzyną, ale potrafi pochłonąć cios topora."},
    {"key": "cloth_robes", "label": "Szaty mędrca", "ac_bonus": 0, "weight_kg": 1.5,
     "value_gp": 8, "armor_coverage": "torso", "allowed_classes": ["scholar"],
     "description": "Luźne szaty z grubej wełny ze srebrnymi haftami runicznymi. Nie chronią ciała, ale pomagają skupić ducha podczas rzucania zaklęć."},
    # ── medium armor ──
    {"key": "chainmail_shirt", "label": "Koszulka kolcza", "ac_bonus": 3, "weight_kg": 9.0,
     "value_gp": 50, "armor_coverage": "torso", "allowed_classes": ["warrior", "rogue"],
     "description": "Krótka kolczuga sięgająca pasa, z rozcięciem do jazdy konnej. Zatrzymuje cięcia i większość pchnięć."},
    {"key": "scale_mail", "label": "Łuskowa zbroja", "ac_bonus": 3, "weight_kg": 11.0,
     "value_gp": 70, "armor_coverage": "torso", "allowed_classes": ["warrior"],
     "description": "Setki metalowych łusek naszytych na skórzaną podkładkę. Brzęczy przy każdym ruchu jak żmija."},
    {"key": "breastplate", "label": "Napierśnik", "ac_bonus": 3, "weight_kg": 8.0,
     "value_gp": 80, "armor_coverage": "torso", "allowed_classes": ["warrior"],
     "description": "Stalowa płyta chroniąca tors i brzuch, mocowana paskami. Nie ogranicza ruchów rąk."},
    {"key": "ringmail", "label": "Pierścieniówka", "ac_bonus": 3, "weight_kg": 12.0,
     "value_gp": 40, "armor_coverage": "torso", "allowed_classes": ["warrior"],
     "description": "Skóra z naszytymi stalowymi pierścieniami. Tańsza alternatywa kolczugi — i równie głośna."},
    {"key": "brigandine", "label": "Brygantyna", "ac_bonus": 3, "weight_kg": 10.0,
     "value_gp": 90, "armor_coverage": "torso", "allowed_classes": ["warrior", "rogue"],
     "description": "Płócienna kamizelka z wszytymi w środku stalowymi płytkami. Wygląda zwyczajnie, chroni jak średnia zbroja."},
    # ── heavy armor ──
    {"key": "chain_hauberk", "label": "Kolczuga długa", "ac_bonus": 4, "weight_kg": 16.0,
     "value_gp": 150, "armor_coverage": "torso", "allowed_classes": ["warrior"],
     "description": "Pełna kolczuga sięgająca kolan z kapturem. Standardowa zbroja zawodowych zbrojnych — ciężka, ale niezawodna."},
    {"key": "half_plate", "label": "Półpłytowa zbroja", "ac_bonus": 4, "weight_kg": 18.0,
     "value_gp": 400, "armor_coverage": "torso", "allowed_classes": ["warrior"],
     "description": "Pełen pancerz z płyt stalowych chroniących tors, ramiona i uda. Brak ochrony nóg pozwala szybko biegać."},
    {"key": "full_plate", "label": "Pełna zbroja płytowa", "ac_bonus": 5, "weight_kg": 25.0,
     "value_gp": 1500, "armor_coverage": "torso", "allowed_classes": ["warrior"],
     "description": "Kompletna zbroja rycerska z setkami precyzyjnie dopasowanych płyt. Wymaga giermka do założenia i miesięcy treningu, by walczyć w niej zręcznie."},
    # ── shields ──
    {"key": "buckler", "label": "Puklerz", "ac_bonus": 1, "weight_kg": 1.2,
     "value_gp": 5, "armor_coverage": "shield", "allowed_classes": ["warrior", "rogue"],
     "description": "Mała okrągła tarcza trzymana w pięści, dobra do parowania. Nie chroni ciała, ale odbija pchnięcia."},
    {"key": "kite_shield", "label": "Tarcza migdałowa", "ac_bonus": 2, "weight_kg": 4.0,
     "value_gp": 15, "armor_coverage": "shield", "allowed_classes": ["warrior"],
     "description": "Tarcza w kształcie kropli zwężającej się ku dołowi. Chroni rycerza pieszego i konnego od ramienia po udo."},
    {"key": "tower_shield", "label": "Pawęż", "ac_bonus": 3, "weight_kg": 6.0,
     "value_gp": 30, "armor_coverage": "shield", "allowed_classes": ["warrior"],
     "description": "Wielka prostokątna tarcza wysoka jak człowiek. Można za nią ukryć całe ciało — kosztem mobilności."},
    {"key": "round_shield", "label": "Tarcza okrągła", "ac_bonus": 2, "weight_kg": 3.0,
     "value_gp": 10, "armor_coverage": "shield", "allowed_classes": ["warrior", "rogue"],
     "description": "Drewniana okrągła tarcza okuta żelazem na krawędziach. Klasyczny ekwipunek najemnika i piechura."},
    # ── helmets ──
    {"key": "leather_cap", "label": "Skórzany kaptur", "ac_bonus": 0, "weight_kg": 0.5,
     "value_gp": 3, "armor_coverage": "head", "allowed_classes": ["warrior", "rogue", "scholar"],
     "description": "Prosty kaptur ze sztywnej skóry. Chroni przed wilgocią i lekkimi obrażeniami głowy."},
    {"key": "iron_helm", "label": "Hełm żelazny", "ac_bonus": 1, "weight_kg": 1.8,
     "value_gp": 12, "armor_coverage": "head", "allowed_classes": ["warrior"],
     "description": "Stożkowaty hełm z nosalem. Odbija ciosy z góry, choć ogranicza pole widzenia."},
    {"key": "great_helm", "label": "Hełm garnczkowy", "ac_bonus": 2, "weight_kg": 3.5,
     "value_gp": 35, "armor_coverage": "head", "allowed_classes": ["warrior"],
     "description": "Stalowy hełm zamknięty z wąskimi otworami na oczy. Chroni głowę całkowicie, ale tłumi słuch i głosy."},
    {"key": "hooded_cloak", "label": "Płaszcz z kapturem", "ac_bonus": 0, "weight_kg": 1.0,
     "value_gp": 5, "armor_coverage": "head", "allowed_classes": ["warrior", "rogue", "scholar"],
     "description": "Wełniany płaszcz z głębokim kapturem. Pomaga ukryć twarz w mieście i osłania przed deszczem."},
    {"key": "silver_circlet", "label": "Srebrny diadem", "ac_bonus": 0, "weight_kg": 0.2,
     "value_gp": 80, "armor_coverage": "head", "allowed_classes": ["scholar"],
     "description": "Cienki diadem ze srebra ozdobiony niewielkim turkusem. Skupia myśli kastującego, choć nie chroni głowy."},
    # ── gloves/boots ──
    {"key": "leather_gloves", "label": "Skórzane rękawice", "ac_bonus": 0, "weight_kg": 0.3,
     "value_gp": 2, "armor_coverage": "hands", "allowed_classes": ["warrior", "rogue", "scholar"],
     "description": "Miękkie rękawiczki dobrze chroniące skórę dłoni. Pozwalają trzymać miecz bez ślizgania się rękojeści."},
    {"key": "plate_gauntlets", "label": "Stalowe rękawice płytowe", "ac_bonus": 1, "weight_kg": 1.2,
     "value_gp": 40, "armor_coverage": "hands", "allowed_classes": ["warrior"],
     "description": "Rękawice z metalowych płytek na skórzanej podkładce. Można w nich zacisnąć pięść i przyjąć cios mieczem na grzbiet dłoni."},
    {"key": "leather_boots", "label": "Skórzane buty", "ac_bonus": 0, "weight_kg": 1.0,
     "value_gp": 4, "armor_coverage": "feet", "allowed_classes": ["warrior", "rogue", "scholar"],
     "description": "Wysokie buty ze sznurowaniem. Wytrzymują dni marszu w błocie i kamienistych ścieżkach."},
    {"key": "plate_sabatons", "label": "Płytowe sabatony", "ac_bonus": 1, "weight_kg": 2.5,
     "value_gp": 50, "armor_coverage": "feet", "allowed_classes": ["warrior"],
     "description": "Stalowe buty rycerskie z ostrymi noskami. Ciężkie, ale można nimi kopnąć tak, że pęka kolano."},
    {"key": "soft_slippers", "label": "Miękkie pantofle", "ac_bonus": 0, "weight_kg": 0.3,
     "value_gp": 6, "armor_coverage": "feet", "allowed_classes": ["rogue", "scholar"],
     "description": "Miękkie pantofle z owczej skóry. Pozwalają poruszać się bezgłośnie po deskach albo kamiennych korytarzach."},
    # ── mantles/cloaks ──
    {"key": "travelers_cloak", "label": "Płaszcz podróżnika", "ac_bonus": 0, "weight_kg": 1.5,
     "value_gp": 3, "armor_coverage": "back", "allowed_classes": ["warrior", "rogue", "scholar"],
     "description": "Wełniany płaszcz nasycony oliwą — chroni przed deszczem i wiatrem podczas długiej drogi."},
    {"key": "fur_mantle", "label": "Mantia z futra", "ac_bonus": 0, "weight_kg": 2.5,
     "value_gp": 25, "armor_coverage": "back", "allowed_classes": ["warrior", "scholar"],
     "description": "Gruba mantia uszyta z futra wilka. Niezbędna podczas zimowych wypraw na północ."},
    {"key": "wizard_robe", "label": "Szata maga", "ac_bonus": 1, "weight_kg": 2.0,
     "value_gp": 75, "armor_coverage": "torso", "allowed_classes": ["scholar"],
     "description": "Ciężka jedwabna szata z wszytymi srebrnymi runami. Nie zatrzymuje miecza, ale pochłania część obrażeń magicznych."},
]

# ── 50 ITEMS (misc — game_config_items, non-armor) ─────────────────────────
ITEMS: list[dict] = [
    # ── tools ──
    {"key": "rope_hemp", "label": "Lina konopna (15m)", "item_type": "gear", "value_gp": 1, "weight_kg": 4.5,
     "description": "Pleciona lina z konopi, długości piętnastu metrów. Niezbędna przy wspinaczce, krępowaniu więźniów i tysiącu innych zastosowań."},
    {"key": "grappling_hook", "label": "Hak z linką", "item_type": "gear", "value_gp": 2, "weight_kg": 1.5,
     "description": "Żelazny hak z trzema zębami na pięciometrowej lince. Zarzucony na mur z trzeciej próby — zazwyczaj się trzyma."},
    {"key": "climbing_kit", "label": "Zestaw wspinaczkowy", "item_type": "gear", "value_gp": 25, "weight_kg": 5.5,
     "description": "Hak, kliny, młotek i kawałek liny w skórzanej torbie. Pozwala wejść tam, gdzie mury wyglądają na nie do zdobycia."},
    {"key": "lockpicks", "label": "Wytrychy", "item_type": "tool", "value_gp": 25, "weight_kg": 0.1,
     "description": "Zestaw cienkich, hartowanych haczyków w skórzanym etui. W rękach łotrzyka otwierają drzwi szybciej niż prawdziwy klucz."},
    {"key": "crowbar", "label": "Łom", "item_type": "tool", "value_gp": 2, "weight_kg": 2.5,
     "description": "Stalowy pręt z rozdwojonym końcem. Otworzy zamknięte drzwi, podważy kamień grobowy albo rozłupie czaszkę."},
    {"key": "torch", "label": "Pochodnia", "item_type": "gear", "value_gp": 1, "weight_kg": 0.5,
     "description": "Pakuł nasycony smołą na drewnianym kiju. Płonie godzinę silnym, dymiącym płomieniem."},
    {"key": "lantern_hooded", "label": "Latarnia z zasłoną", "item_type": "gear", "value_gp": 7, "weight_kg": 1.0,
     "description": "Mosiężna latarnia ze szklanymi ścianami i metalową zasłoną. Pozwala kontrolować, gdzie pada światło."},
    {"key": "oil_flask", "label": "Bańka oleju", "item_type": "gear", "value_gp": 1, "weight_kg": 0.5, "charges": 1,
     "description": "Gliniana bańka pełna lampowego oleju. Zasili latarnię na sześć godzin, albo zapali wroga, jeśli rozbije się o niego."},
    {"key": "hammer_small", "label": "Mały młotek", "item_type": "tool", "value_gp": 1, "weight_kg": 1.0,
     "description": "Stalowy młotek z drewnianym trzonkiem. Wbije gwóźdź, klin lub piszczel."},
    {"key": "chisel", "label": "Dłuto", "item_type": "tool", "value_gp": 1, "weight_kg": 0.3,
     "description": "Ostre stalowe dłuto. Przydatne kamieniarzowi, włamywaczowi i każdemu, kto chce zostawić znak na ścianie."},
    {"key": "fishing_rod", "label": "Wędka", "item_type": "tool", "value_gp": 2, "weight_kg": 1.0,
     "description": "Prosta wędka z włókna lnianego. Cierpliwy rybak zdoła nią wyciągnąć kolację z byle strumienia."},
    {"key": "shovel", "label": "Łopata", "item_type": "tool", "value_gp": 2, "weight_kg": 2.5,
     "description": "Solidna łopata z drewnianym trzonkiem. Wykopie schron, grób, albo zakopany skarb."},
    {"key": "sickle", "label": "Sierp", "item_type": "tool", "value_gp": 1, "weight_kg": 0.7,
     "description": "Zakrzywione ostrze na krótkim trzonku. Tnie zboże, zioła i lekkie skóry — bywa też doraźną bronią."},
    # ── containers ──
    {"key": "backpack", "label": "Plecak", "item_type": "container", "value_gp": 2, "weight_kg": 2.0,
     "description": "Pojemny skórzany plecak na ramiączkach. Mieści zapas żywności na tydzień, koc i drobny ekwipunek."},
    {"key": "belt_pouch", "label": "Sakiewka przy pasie", "item_type": "container", "value_gp": 1, "weight_kg": 0.3,
     "description": "Skórzana sakiewka mocowana do pasa. Mieści garść monet i parę drobiazgów."},
    {"key": "waterskin", "label": "Bukłak", "item_type": "container", "value_gp": 1, "weight_kg": 2.0,
     "description": "Skórzany bukłak na cztery litry wody albo wina. Nieoceniony na pustkowiu."},
    {"key": "sack_large", "label": "Duży worek", "item_type": "container", "value_gp": 1, "weight_kg": 0.5,
     "description": "Płócienny worek na osiem kilogramów łupów. Zwinięty zajmuje miejsce ledwie chusteczki."},
    {"key": "satchel", "label": "Torba listonosza", "item_type": "container", "value_gp": 3, "weight_kg": 1.0,
     "description": "Skórzana torba na ramię z kilkoma przegródkami. Dobra na zwoje, mapy i drobny ekwipunek alchemika."},
    {"key": "small_chest", "label": "Mała szkatuła", "item_type": "container", "value_gp": 5, "weight_kg": 6.0,
     "description": "Drewniana szkatuła okuta żelazem, zamykana na zameczek. Mieści sto sztuk złota lub kilka cennych precjozów."},
    # ── quest/lore ──
    {"key": "ancient_scroll", "label": "Starożytny zwój", "item_type": "lore", "value_gp": 50, "weight_kg": 0.2,
     "description": "Pergamin pociemniały od wieków, zapisany pismem, którego dawno nikt nie używa. Może opisuje skarb, klątwę albo proroctwo."},
    {"key": "family_locket", "label": "Rodzinny medalion", "item_type": "lore", "value_gp": 30, "weight_kg": 0.05,
     "description": "Srebrny medalion z miniaturą kobiety i dziecka. Po wewnętrznej stronie wygrawerowano dwie litery, których właściciel nie pamięta."},
    {"key": "signet_ring", "label": "Pierścień herbowy", "item_type": "lore", "value_gp": 60, "weight_kg": 0.05,
     "description": "Złoty pierścień z grawerowanym wizerunkiem trzymającego miecz gryfa. Pozwala podszyć się pod członka rodu — albo ściągnąć jego wrogów."},
    {"key": "treasure_map", "label": "Mapa skarbu", "item_type": "lore", "value_gp": 25, "weight_kg": 0.1,
     "description": "Wytarta mapa narysowana na skrawku skóry. X zaznaczono w głębi lasu, ale ścieżki dawno zarosły mchem."},
    {"key": "cursed_amulet", "label": "Przeklęty amulet", "item_type": "lore", "value_gp": 0, "weight_kg": 0.2,
     "description": "Ciemny kamień oprawiony w żelazo. Wibruje cicho, jakby coś szeptało po drugiej stronie świata. Nie sposób się go pozbyć — wraca."},
    {"key": "holy_symbol", "label": "Symbol święty", "item_type": "lore", "value_gp": 5, "weight_kg": 0.3,
     "description": "Drewniany lub srebrny symbol bóstwa zawieszony na łańcuszku. Daje pocieszenie w mroku i — czasami — odpędza złe rzeczy."},
    {"key": "prayer_book", "label": "Modlitewnik", "item_type": "lore", "value_gp": 10, "weight_kg": 1.0,
     "description": "Mała oprawiona w skórę księga modlitw i psalmów. Czytanie po cichu pomaga zachować zdrowy umysł w upiornych miejscach."},
    {"key": "demon_skull", "label": "Czaszka demona", "item_type": "lore", "value_gp": 200, "weight_kg": 2.5,
     "description": "Czarna jak smoła czaszka z trzema oczodołami i parą zakrzywionych rogów. Cuchnie siarką, choć minęły lata, odkąd jej właściciel zginął."},
    # ── mundane ──
    {"key": "tinderbox", "label": "Hubka z krzesiwem", "item_type": "gear", "value_gp": 1, "weight_kg": 0.5,
     "description": "Mały skórzany etui z krzesiwem, hubką i suchą podpałką. Pozwala rozpalić ogień — nawet w deszczu, jeśli ma się wprawę."},
    {"key": "blanket", "label": "Koc", "item_type": "gear", "value_gp": 1, "weight_kg": 1.5,
     "description": "Gruby wełniany koc. Ratuje życie w zimną noc nawet bez ognia."},
    {"key": "bedroll", "label": "Posłanie", "item_type": "gear", "value_gp": 1, "weight_kg": 3.5,
     "description": "Skręcony siennik i koc. Wystarczy znaleźć kawałek równej ziemi, by przespać nawet w lesie."},
    {"key": "mess_kit", "label": "Zestaw kuchenny", "item_type": "gear", "value_gp": 2, "weight_kg": 0.5,
     "description": "Składany rondel, miska i sztućce w skórzanym etui. Pozwala ugotować zupę z byle czego."},
    {"key": "sewing_kit", "label": "Igielnik", "item_type": "tool", "value_gp": 1, "weight_kg": 0.1,
     "description": "Igły, nitki i kawałek płótna w drewnianym pudełku. Pozwala załatać ubranie, zszyć ranę albo zwabić kota."},
    {"key": "soap", "label": "Mydło", "item_type": "gear", "value_gp": 1, "weight_kg": 0.1,
     "description": "Twarda kostka szarego mydła pachnąca łojem. Po tygodniu w lesie warta dla bohatera tyle co miecz."},
    {"key": "mirror_small", "label": "Małe lusterko", "item_type": "gear", "value_gp": 5, "weight_kg": 0.1,
     "description": "Polerowane stalowe lusterko w drewnianej oprawie. Można sprawdzić, co czai się za rogiem, nie wystawiając głowy."},
    {"key": "whetstone", "label": "Osełka", "item_type": "tool", "value_gp": 1, "weight_kg": 0.5,
     "description": "Szary kamień do ostrzenia ostrzy. Tępy miecz to martwy miecz — każdy zawodowiec o tym wie."},
    {"key": "pipeweed_pouch", "label": "Sakiewka tytoniu fajkowego", "item_type": "gear", "value_gp": 3, "weight_kg": 0.1,
     "description": "Skórzana sakiewka z suszonymi liśćmi. Zapach gęsty i ziemisty — uspokaja nerwy po długiej walce."},
    {"key": "dice_set", "label": "Komplet kości", "item_type": "gear", "value_gp": 1, "weight_kg": 0.1,
     "description": "Cztery kostki rzeźbione z kości. Mogą wciągnąć w grę przy każdym ognisku — a niektórzy mówią, że są obciążone."},
    # ── magical (passive) ──
    {"key": "magic_compass", "label": "Kompas magiczny", "item_type": "magic", "value_gp": 250, "weight_kg": 0.3,
     "description": "Mosiężny kompas, którego igła nie wskazuje północy. Wskazuje to, czego najbardziej pragniesz — czasem na bezsensowną drogę."},
    {"key": "scrying_orb_small", "label": "Mała sfera wizji", "item_type": "magic", "value_gp": 400, "weight_kg": 1.0,
     "description": "Szklana kula o mlecznej powierzchni. Wpatrując się w nią koncentrująco, można czasem ujrzeć obrazy odległych miejsc."},
    {"key": "ring_of_protection", "label": "Pierścień ochrony", "item_type": "magic", "value_gp": 800, "weight_kg": 0.05,
     "description": "Cienki srebrny pierścień z runą wygrawerowaną od wewnątrz. Otacza noszącego niewidzialnym mgnieniem mocy, odbijającym ciosy."},
    {"key": "amulet_of_health", "label": "Amulet zdrowia", "item_type": "magic", "value_gp": 600, "weight_kg": 0.2,
     "description": "Bursztynowy amulet w oprawie z brązu. Noszący goi się szybciej — choć przy ciężkich ranach nie czyni cudów."},
    # ── instruments + entertainment ──
    {"key": "lute", "label": "Lutnia", "item_type": "gear", "value_gp": 35, "weight_kg": 2.0,
     "description": "Drewniana lutnia z sześcioma strunami. W rękach barda potrafi otworzyć drzwi, na które miecz nie ma rady."},
    {"key": "flute_wooden", "label": "Flet drewniany", "item_type": "gear", "value_gp": 2, "weight_kg": 0.2,
     "description": "Prosty flet wystrugany z bukowego drewna. Mała melodia odgania nudę i wilki na nocnym czuwaniu."},
    {"key": "deck_of_cards", "label": "Talia kart", "item_type": "gear", "value_gp": 1, "weight_kg": 0.1,
     "description": "Stara, podniszczona talia kart z dziwnymi symbolami. Czasem któraś karta zmienia obrazek między rozdaniami."},
    {"key": "smoking_pipe", "label": "Fajka", "item_type": "gear", "value_gp": 2, "weight_kg": 0.1,
     "description": "Wykonana z wrzośca fajka z długim cybuchem. Pomaga rozważyć trudne decyzje w spokoju."},
    {"key": "hourglass", "label": "Klepsydra", "item_type": "gear", "value_gp": 25, "weight_kg": 1.0,
     "description": "Szklana klepsydra w drewnianej oprawie. Piasek przesypuje się dokładnie godzinę — w pewnych miejscach szybciej lub wolniej."},
    {"key": "spyglass", "label": "Luneta", "item_type": "gear", "value_gp": 1000, "weight_kg": 1.0,
     "description": "Mosiężna luneta z trzema soczewkami. Pozwala dostrzec sztandar wroga z połowy mili."},
    {"key": "manacles", "label": "Kajdany", "item_type": "gear", "value_gp": 2, "weight_kg": 2.5,
     "description": "Ciężkie żelazne kajdany z kluczykiem. Krępują nadgarstki dorosłego człowieka — z byle wprawnym łotrzykiem mają większy kłopot."},
    {"key": "hunting_horn", "label": "Róg myśliwski", "item_type": "gear", "value_gp": 15, "weight_kg": 0.8,
     "description": "Polerowany róg bydlęcy z mosiężnym ustnikiem. Słychać go na pół godziny marszu — zbiera kompanów albo zwołuje wroga."},
    {"key": "fishing_net", "label": "Sieć rybacka", "item_type": "tool", "value_gp": 4, "weight_kg": 2.0,
     "description": "Pleciona sieć z węzłami co dłoń. Łapie ryby, ale w razie potrzeby unieruchomi też zaskoczonego przeciwnika."},
    {"key": "noble_garb", "label": "Strój szlachecki", "item_type": "gear", "value_gp": 75, "weight_kg": 2.5,
     "description": "Ubranie z bogatego sukna z futrzanym kołnierzem. Pozwala wejść tam, gdzie miecz by tylko sprowokował straże."},
    {"key": "merchant_garb", "label": "Strój kupiecki", "item_type": "gear", "value_gp": 15, "weight_kg": 2.0,
     "description": "Solidne, dyskretne ubranie z dobrego sukna. Idealny przebieg dla zwiadu w mieście."},
    {"key": "silk_scarf", "label": "Jedwabna chusta", "item_type": "gear", "value_gp": 5, "weight_kg": 0.1,
     "description": "Cienka, długa chusta z południowego jedwabiu. Zakrywa twarz przed pyłem — albo przed rozpoznaniem."},
    {"key": "incense_bundle", "label": "Pęczek kadzideł", "item_type": "gear", "value_gp": 3, "weight_kg": 0.2,
     "description": "Wiązka pachnących mirry i żywicy paliw. Spalone w komnacie odpędzają smród trupów — i czasem zwabiają duchy."},
    {"key": "silver_chalice", "label": "Srebrny kielich", "item_type": "lore", "value_gp": 50, "weight_kg": 0.5,
     "description": "Wytworny kielich ze srebrnej blachy z wygrawerowanymi rzędami żołądków. Bez napisu nie sposób ustalić, kto go używał."},
    {"key": "golden_idol", "label": "Złoty bożek", "item_type": "lore", "value_gp": 500, "weight_kg": 1.5,
     "description": "Mały złoty posążek bezimiennego bóstwa z dziwnymi oczyma. Im dłużej się go niesie, tym cięższy się wydaje."},
    {"key": "wolf_pelt", "label": "Skóra wilka", "item_type": "gear", "value_gp": 8, "weight_kg": 3.0,
     "description": "Surowa skóra czarnego wilka z głową i pazurami. Można ją sprzedać kupcom albo udowodnić nią zabicie bestii."},
    {"key": "wax_candle", "label": "Wosko­wa świeca", "item_type": "gear", "value_gp": 1, "weight_kg": 0.1,
     "description": "Pojedyncza świeca z białego wosku. Pali się sześć godzin łagodnym, czystym płomieniem."},
    {"key": "ink_quill_set", "label": "Atrament z piórem", "item_type": "tool", "value_gp": 3, "weight_kg": 0.2,
     "description": "Buteleczka czarnego atramentu i trzy zaostrzone pióra. Niezbędne, by spisać kontrakt, list albo proroctwo."},
    {"key": "parchment_sheets", "label": "Arkusze pergaminu (10)", "item_type": "gear", "value_gp": 5, "weight_kg": 0.3,
     "description": "Dziesięć starannie wygładzonych arkuszy pergaminu. Na każdym można narysować mapę albo zapisać list."},
    {"key": "iron_spikes_10", "label": "Żelazne kliny (10)", "item_type": "gear", "value_gp": 1, "weight_kg": 2.5,
     "description": "Dziesięć żelaznych klinów do podpierania drzwi, blokowania zamków i wbijania w skałę przy wspinaczce."},
    {"key": "caltrops_bag", "label": "Woreczek kolczastych", "item_type": "gear", "value_gp": 5, "weight_kg": 1.0, "charges": 3,
     "description": "Woreczek żelaznych kolców rozsypanych na ścieżce — kaleczy stopy ścigających. Wystarczy na trzy razy."},
]

# ── 30 CONSUMABLES ────────────────────────────────────────────────────────
# Schema: key, label, description, effect_type, effect_dice, effect_bonus,
#   effect_target (self|ally|enemy|area), weight_kg, charges, base_price, approved=1
CONSUMABLES: list[dict] = [
    # ── healing ──
    {"key": "potion_healing_small", "label": "Mała mikstura leczenia", "effect_type": "heal_hp",
     "effect_dice": "2d4", "effect_bonus": 2, "effect_target": "self", "base_price": 25, "weight_kg": 0.2,
     "description": "Mała szklana ampułka czerwonej cieczy o cierpkim posmaku ziół. Wypita zalewa rany ciepłem."},
    {"key": "potion_healing_medium", "label": "Mikstura leczenia", "effect_type": "heal_hp",
     "effect_dice": "4d4", "effect_bonus": 4, "effect_target": "self", "base_price": 75, "weight_kg": 0.3,
     "description": "Pełna fiolka rubinowej cieczy. Smakuje jak żelazo i kwiat lipy — goi nawet poważne rany."},
    {"key": "potion_healing_large", "label": "Wielka mikstura leczenia", "effect_type": "heal_hp",
     "effect_dice": "8d4", "effect_bonus": 8, "effect_target": "self", "base_price": 250, "weight_kg": 0.5,
     "description": "Duża flakon z mikstury alchemika. Przywróci do walki nawet człowieka konającego w kałuży krwi."},
    {"key": "healing_herb", "label": "Lecznicze zioła", "effect_type": "heal_hp",
     "effect_dice": "1d4", "effect_bonus": 1, "effect_target": "self", "base_price": 8, "weight_kg": 0.1,
     "description": "Pęczek suszonych ziół owinięty w len. Przyłożone do rany przyspieszają gojenie."},
    {"key": "bandage", "label": "Bandaż", "effect_type": "heal_hp",
     "effect_dice": "1d6", "effect_bonus": 0, "effect_target": "ally", "base_price": 2, "weight_kg": 0.2,
     "description": "Czysty zwój lnianego płótna. Pozwala opatrzyć ranę towarzysza w polu walki."},
    # ── mana ──
    {"key": "potion_mana_small", "label": "Mała mikstura many", "effect_type": "restore_mana",
     "effect_dice": "1d6", "effect_bonus": 2, "effect_target": "self", "base_price": 30, "weight_kg": 0.2,
     "description": "Lazurowa ciecz w okrągłej ampułce. Pachnie miętą i wapnem — przywraca część zużytej mocy magicznej."},
    {"key": "potion_mana_medium", "label": "Mikstura many", "effect_type": "restore_mana",
     "effect_dice": "2d6", "effect_bonus": 4, "effect_target": "self", "base_price": 90, "weight_kg": 0.3,
     "description": "Granatowy eliksir o przyjemnym ziołowym posmaku. Odnawia więcej many niż mała mikstura."},
    {"key": "potion_mana_large", "label": "Wielka mikstura many", "effect_type": "restore_mana",
     "effect_dice": "4d6", "effect_bonus": 8, "effect_target": "self", "base_price": 300, "weight_kg": 0.5,
     "description": "Wielki flakon ciemnogranatowej mikstury z migocącymi iskierkami. Niemal w pełni regeneruje arkany kastującego."},
    {"key": "focus_crystal", "label": "Kryształ skupienia", "effect_type": "restore_mana",
     "effect_dice": "1d4", "effect_bonus": 1, "effect_target": "self", "base_price": 15, "weight_kg": 0.1, "charges": 3,
     "description": "Mały szmaragdowy kryształ. Po skupieniu woli można z niego wydobyć trochę many — wystarczy na trzy razy."},
    # ── buffs ──
    {"key": "potion_strength", "label": "Mikstura siły", "effect_type": "buff_str",
     "effect_dice": "", "effect_bonus": 2, "effect_target": "self", "base_price": 60, "weight_kg": 0.2,
     "description": "Mętna brunatna mikstura o zapachu byczej krwi. Wypita daje na minutę siłę osiłka — i kaca na cały dzień."},
    {"key": "potion_haste", "label": "Mikstura pośpiechu", "effect_type": "buff_dex",
     "effect_dice": "", "effect_bonus": 2, "effect_target": "self", "base_price": 80, "weight_kg": 0.2,
     "description": "Bladozielona ciecz pulsująca delikatnym światłem. Wyostrza refleks i przyspiesza krok."},
    {"key": "potion_stealth", "label": "Mikstura skradania", "effect_type": "buff_stealth",
     "effect_dice": "", "effect_bonus": 3, "effect_target": "self", "base_price": 70, "weight_kg": 0.2,
     "description": "Szara ciecz bez zapachu. Wypita tłumi kroki i sprawia, że cienie zdają się garnąć do bohatera."},
    {"key": "potion_resistance", "label": "Mikstura odporności", "effect_type": "buff_resist",
     "effect_dice": "", "effect_bonus": 2, "effect_target": "self", "base_price": 100, "weight_kg": 0.2,
     "description": "Mętna biaława mikstura. Po wypiciu skóra twardnieje, a ciosy ślizgają się po niej jakby były tępe."},
    {"key": "potion_giant_strength", "label": "Mikstura siły olbrzyma", "effect_type": "buff_str",
     "effect_dice": "", "effect_bonus": 4, "effect_target": "self", "base_price": 250, "weight_kg": 0.3,
     "description": "Gęsta brązowa mikstura w kamiennym dzbanuszku. Daje krótko siłę pozwalającą podnieść wóz albo wyrwać drzwi z zawiasów."},
    # ── scrolls (single-use spells) ──
    {"key": "scroll_magic_bolt", "label": "Zwój: Magiczna Strzała", "effect_type": "cast_spell",
     "effect_dice": "1d10", "effect_bonus": 0, "effect_target": "enemy", "base_price": 40, "weight_kg": 0.1,
     "description": "Zwitek pergaminu zapisany świetlistym inkaustem. Czytanie wyzwala pojedynczy pocisk mocy w wybrany cel."},
    {"key": "scroll_mend", "label": "Zwój: Zaszycie Ran", "effect_type": "cast_spell",
     "effect_dice": "2d4", "effect_bonus": 2, "effect_target": "ally", "base_price": 35, "weight_kg": 0.1,
     "description": "Pergamin zapisany srebrnym pismem. Rozwinięcie i wypowiedzenie formuły zalecza ranę towarzysza."},
    {"key": "scroll_shield", "label": "Zwój: Arkana Tarcza", "effect_type": "cast_spell",
     "effect_dice": "", "effect_bonus": 3, "effect_target": "self", "base_price": 50, "weight_kg": 0.1,
     "description": "Zwój oprawiony w cienki bambus. Wypowiedziane słowa otaczają kastującego półprzeźroczystą tarczą mocy."},
    {"key": "scroll_light", "label": "Zwój: Światło", "effect_type": "cast_spell",
     "effect_dice": "", "effect_bonus": 0, "effect_target": "self", "base_price": 15, "weight_kg": 0.1,
     "description": "Krótka formuła wypisana na pergaminie. Sprawia, że trzymany przedmiot zaczyna świecić jak pochodnia."},
    {"key": "scroll_fireball", "label": "Zwój: Kula Ognia", "effect_type": "cast_spell",
     "effect_dice": "8d6", "effect_bonus": 0, "effect_target": "area", "base_price": 350, "weight_kg": 0.2,
     "description": "Gruby zwój zapisany czerwonym pigmentem. Wypowiedzenie formuły wyzwala kulę ognia, która eksploduje wśród wrogów."},
    # ── food/drink ──
    {"key": "bread_loaf", "label": "Bochenek chleba", "effect_type": "food",
     "effect_dice": "", "effect_bonus": 1, "effect_target": "self", "base_price": 1, "weight_kg": 0.6,
     "description": "Świeży bochenek żytniego chleba. Zaspokoi głód na cały dzień marszu."},
    {"key": "dried_meat", "label": "Suszone mięso", "effect_type": "food",
     "effect_dice": "", "effect_bonus": 1, "effect_target": "self", "base_price": 2, "weight_kg": 0.3,
     "description": "Solone, suszone mięso wieprzowe albo z dziczyzny. Zachowuje świeżość tygodniami."},
    {"key": "cheese_wheel", "label": "Krąg sera", "effect_type": "food",
     "effect_dice": "", "effect_bonus": 1, "effect_target": "self", "base_price": 3, "weight_kg": 1.5,
     "description": "Mały krąg owczego sera w wosku. Sycący i odporny na zepsucie."},
    {"key": "apple", "label": "Jabłko", "effect_type": "food",
     "effect_dice": "", "effect_bonus": 0, "effect_target": "self", "base_price": 1, "weight_kg": 0.2,
     "description": "Soczyste czerwone jabłko. Niewielki posiłek, ale orzeźwia po długim marszu."},
    {"key": "hardtack", "label": "Suchar", "effect_type": "food",
     "effect_dice": "", "effect_bonus": 1, "effect_target": "self", "base_price": 1, "weight_kg": 0.2,
     "description": "Twardy, prawie niezniszczalny suchar. Można nim wybić ząb, ale wytrzyma rok w plecaku."},
    {"key": "wineskin", "label": "Bukłak wina", "effect_type": "buff_misc",
     "effect_dice": "", "effect_bonus": 1, "effect_target": "self", "base_price": 5, "weight_kg": 1.5, "charges": 4,
     "description": "Skórzany bukłak wypełniony cierpkim czerwonym winem. Cztery porządne łyki — odwagi przed walką lub nocy zapomnienia."},
    # ── poisons/throwables ──
    {"key": "vial_of_acid", "label": "Fiolka kwasu", "effect_type": "dmg",
     "effect_dice": "2d6", "effect_bonus": 0, "effect_target": "enemy", "base_price": 25, "weight_kg": 0.2,
     "description": "Szklana fiolka z mętnym, parującym kwasem. Rzucona na cel parzy ciało i metal — alchemik zna jej nazwę i unika dotyku."},
    {"key": "holy_water", "label": "Woda święcona", "effect_type": "dmg_undead",
     "effect_dice": "2d6", "effect_bonus": 0, "effect_target": "enemy", "base_price": 25, "weight_kg": 0.2,
     "description": "Mała ampułka z modlitwą wyrytą na korku. Wylana albo rozbita na nieumarłym spala go jak ogień."},
    {"key": "alchemist_fire", "label": "Ogień alchemika", "effect_type": "dmg_fire",
     "effect_dice": "1d4", "effect_bonus": 0, "effect_target": "enemy", "base_price": 50, "weight_kg": 0.5,
     "description": "Gęsta oleista substancja w szklanym pojemniku. Rzucona na cel zapala go i pali przez kilka chwil."},
    {"key": "smoke_bomb", "label": "Bomba dymna", "effect_type": "obscure",
     "effect_dice": "", "effect_bonus": 0, "effect_target": "area", "base_price": 30, "weight_kg": 0.3,
     "description": "Mała gliniana kulka z sproszkowanymi ziołami. Rzucona o podłogę wybucha kłębem szarego dymu — idealna na ucieczkę."},
    {"key": "antitoxin_vial", "label": "Antydot", "effect_type": "remove_poison",
     "effect_dice": "", "effect_bonus": 0, "effect_target": "self", "base_price": 50, "weight_kg": 0.1,
     "description": "Mętna ciecz o gorzkim posmaku w małej fiolce. Neutralizuje większość znanych trucizn — jeśli wypić w porę."},
]

# ── INSERT logic ───────────────────────────────────────────────────────────

def seed_weapons(conn: sqlite3.Connection) -> int:
    n = 0
    for w in WEAPONS:
        conn.execute(
            """
            INSERT OR REPLACE INTO game_config_weapons
                (key, label, damage_die, linked_stat, allowed_classes, description,
                 weapon_type, two_handed, finesse, range_m, weight_kg, value_gp,
                 weapon_slot, approved, is_active, ai_generated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 0)
            """,
            (
                w["key"], w["label"], w["damage_die"], w["linked_stat"],
                json.dumps(w.get("allowed_classes", ["warrior"])),
                w.get("description", ""),
                w.get("weapon_type", "melee"),
                int(w.get("two_handed", 0)), int(w.get("finesse", 0)),
                w.get("range_m"), float(w.get("weight_kg", 0)),
                int(w.get("value_gp", 0)),
                w.get("weapon_slot", "main_hand"),
            ),
        )
        n += 1
    return n


def seed_items(conn: sqlite3.Connection, rows: list[dict], default_type: str) -> int:
    n = 0
    for it in rows:
        conn.execute(
            """
            INSERT OR REPLACE INTO game_config_items
                (key, label, item_type, description, value_gp, weight_kg,
                 ac_bonus, armor_coverage, allowed_classes, charges,
                 approved, is_active, ai_generated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 0)
            """,
            (
                it["key"], it["label"], it.get("item_type", default_type),
                it.get("description", ""), int(it.get("value_gp", 0)),
                float(it.get("weight_kg", 0)),
                int(it.get("ac_bonus", 0)),
                it.get("armor_coverage", "torso"),
                json.dumps(it.get("allowed_classes", ["warrior", "rogue", "scholar"])),
                int(it.get("charges", 1)),
            ),
        )
        n += 1
    return n


def seed_consumables(conn: sqlite3.Connection) -> int:
    n = 0
    for c in CONSUMABLES:
        conn.execute(
            """
            INSERT OR REPLACE INTO game_config_consumables
                (key, label, description, effect_type, effect_dice, effect_bonus,
                 effect_target, weight_kg, charges, base_price, approved, is_active, ai_generated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 0)
            """,
            (
                c["key"], c["label"], c.get("description", ""),
                c.get("effect_type", "misc"),
                c.get("effect_dice", ""),
                int(c.get("effect_bonus", 0)),
                c.get("effect_target", "self"),
                float(c.get("weight_kg", 0)),
                int(c.get("charges", 1)),
                int(c.get("base_price", 0)),
            ),
        )
        n += 1
    return n


def main() -> int:
    print(f"Connecting to {DB_PATH}…")
    conn = sqlite3.connect(DB_PATH)
    try:
        w = seed_weapons(conn)
        a = seed_items(conn, ARMORS, default_type="armor")
        i = seed_items(conn, ITEMS, default_type="misc")
        c = seed_consumables(conn)
        conn.commit()
        print(f"✓ Seeded: {w} weapons, {a} armors, {i} items, {c} consumables")
        print(f"  Total: {w + a + i + c} entries")
        # Sanity counts
        for tbl in ("game_config_weapons", "game_config_items", "game_config_consumables"):
            cnt = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            print(f"  {tbl}: {cnt} rows total")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
