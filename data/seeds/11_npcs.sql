-- S11: NPCs seed (#499)
-- Depends on S10 (game_locations must exist for npc_locations refs).
-- Inserts into npcs + npc_locations join table.
-- Safe to re-run: INSERT OR IGNORE + upsert pattern.
-- npc_type enum: neutral | merchant | quest_giver | ally

-- ── 1. Assign location to the 4 existing permanent NPCs ──────────────────────

INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'vilnograd_stolica' FROM npcs WHERE key = 'blacksmith_goran';

INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'vilnograd_stolica' FROM npcs WHERE key = 'quest_giver_eldran';

INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'volhynia_kupiecka' FROM npcs WHERE key = 'merchant_aldric';

INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'trzech_krukow' FROM npcs WHERE key = 'innkeeper_marta';

-- ── 2. Vilnograd, Stolica ─────────────────────────────────────────────────────

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'kowal_vilnograd',
    'Teodor Żelazny',
    'merchant',
    'Stary kowal z Vilnogradu. Jego kuźnia słynie z trwałego oręża i napraw bez zbędnych pytań.',
    1, 0, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'vilnograd_stolica' FROM npcs WHERE key = 'kowal_vilnograd';

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'uzdrowiciel_vilnograd',
    'Brat Kazimierz',
    'ally',
    'Leczy rany i sprzedaje miksturki. Mówi mało, ale wie dużo — długo służył w klasztorze Iskry.',
    1, 0, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'vilnograd_stolica' FROM npcs WHERE key = 'uzdrowiciel_vilnograd';

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'kupiec_vilnograd',
    'Mirna Zbożowa',
    'merchant',
    'Zamożna kupczyni z koneksjami na całym wybrzeżu. Handluje wszystkim, co przynosi zysk.',
    1, 0, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'vilnograd_stolica' FROM npcs WHERE key = 'kupiec_vilnograd';

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'kapitan_krolewski',
    'Kapitan Henryk Miecław',
    'quest_giver',
    'Dowódca straży królewskiej. Szuka wiarygodnych najemników do dyskretnych zadań dla Korony.',
    0, 1, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'vilnograd_stolica' FROM npcs WHERE key = 'kapitan_krolewski';

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'kronikarz_vilnograd',
    'Archiwiusz Dobromił',
    'neutral',
    'Kronikarz królewski. Zna historię każdego szlacheckiego rodu i każdej starożytnej ruin w okolicy.',
    0, 0, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'vilnograd_stolica' FROM npcs WHERE key = 'kronikarz_vilnograd';

-- ── 3. Volhynia, Miasto Kupieckie ─────────────────────────────────────────────

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'kowal_volhynia',
    'Sidor Ognisty',
    'merchant',
    'Kowal z Volhynii. Specjalizuje się w broni i zbrojach przeznaczonych na handel, nie wytrzymałości.',
    1, 0, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'volhynia_kupiecka' FROM npcs WHERE key = 'kowal_volhynia';

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'aptekarka_volhynia',
    'Wdowa Aldona',
    'merchant',
    'Aptekarze z doświadczeniem w truciznach i antidotach. Prowadzi dyskretny handel ziołami.',
    1, 0, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'volhynia_kupiecka' FROM npcs WHERE key = 'aptekarka_volhynia';

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'gildmistrz_volhynia',
    'Brat Aleksy Złotnik',
    'quest_giver',
    'Gildmistrz kupców. Płaci dobrze za informacje o nowych szlakach handlowych i wyeliminowanie konkurencji.',
    0, 1, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'volhynia_kupiecka' FROM npcs WHERE key = 'gildmistrz_volhynia';

-- ── 4. Czarnogród, Port ───────────────────────────────────────────────────────

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'kowal_czarnogrod',
    'Ruda Magda',
    'merchant',
    'Kowalka portowa. Naprawia broń, zbroje i kotwice — bez pytań o to, skąd noszą ślady krwi.',
    1, 0, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'czarnogrod_port' FROM npcs WHERE key = 'kowal_czarnogrod';

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'chirurg_czarnogrod',
    'Doktor Marcin Szkalpel',
    'neutral',
    'Okrętowy chirurg na emeryturze. Leczy rany za złoto, a za podwójną stawkę nie pyta o przyczynę.',
    1, 0, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'czarnogrod_port' FROM npcs WHERE key = 'chirurg_czarnogrod';

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'kapitan_smolny',
    'Kapitan Jacek Smolny',
    'quest_giver',
    'Stary kapitan z portu. Ma mapę każdego ukrytego klifu i każdej zatopionej łodzi na tym wybrzeżu.',
    0, 1, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'czarnogrod_port' FROM npcs WHERE key = 'kapitan_smolny';

-- ── 5. Klasztor Iskry, Centrum Wiary ─────────────────────────────────────────

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'matka_klasztor',
    'Matka Urszula',
    'ally',
    'Przeorysza Klasztoru Iskry. Leczy rannych i przyjmuje pielgrzymów, ale żąda w zamian pomocy w świętych zadaniach.',
    1, 1, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'klasztor_iskry_centrum' FROM npcs WHERE key = 'matka_klasztor';

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'brat_tomasz_kronikarz',
    'Brat Tomasz Kronikarz',
    'quest_giver',
    'Mnich archiwista. Zbiera relikwie i stare manuskrypty — zapłaci za każdy artefakt z dawnych czasów.',
    0, 1, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'klasztor_iskry_centrum' FROM npcs WHERE key = 'brat_tomasz_kronikarz';

-- ── 6. Zatoka Topielców ───────────────────────────────────────────────────────

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'kowal_zatoka',
    'Wielki Borek',
    'merchant',
    'Kowal i kotwiarz z Zatoki. Jego wyroby są ciężkie jak kamień i trwają dziesięciolecia.',
    1, 0, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'zatoka_topielcow' FROM npcs WHERE key = 'kowal_zatoka';

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'uzdrowiciel_zatoka',
    'Halina Morska',
    'neutral',
    'Zna wszystkie morskie ziółka i trucizny. Leczy choroby morza i ukąszenia potworów z głębin.',
    1, 0, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'zatoka_topielcow' FROM npcs WHERE key = 'uzdrowiciel_zatoka';

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'rybak_stary_zatoka',
    'Dziadek Florian',
    'quest_giver',
    'Stary rybak z Zatoki. Twierdzi, że widział coś dużego pod wodą i szuka kogoś, kto sprawdzi jego słowa.',
    0, 1, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'zatoka_topielcow' FROM npcs WHERE key = 'rybak_stary_zatoka';

-- ── 7. Brzezino, Wioska Drwali ───────────────────────────────────────────────

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'kowal_brzezino',
    'Stary Paweł Kowal',
    'merchant',
    'Jedyny kowal w wiosce drwali. Naprawia siekiery i zbroje, choć woli pracę w drewnie od metalu.',
    1, 0, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'brzezino' FROM npcs WHERE key = 'kowal_brzezino';

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'soltys_brzezino',
    'Sołtys Benedykt',
    'quest_giver',
    'Sołtys Brzezina. Spokojny, ale martwi się o drwali, którzy nie wracają z Boru Umarłych.',
    0, 1, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'brzezino' FROM npcs WHERE key = 'soltys_brzezino';

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'zielarka_brzezino',
    'Zielarka Agata',
    'neutral',
    'Zbiera zioła na skraju Boru. Zna remedium na większość leśnych dolegliwości i kilka trucizn.',
    1, 0, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'brzezino' FROM npcs WHERE key = 'zielarka_brzezino';

-- ── 8. Wolanka, Wioska Górnicza ───────────────────────────────────────────────

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'kowal_wolanka',
    'Grubas Miron',
    'merchant',
    'Górnik i kowal w jednym. Specjalizuje się w narzędziach górniczych, ale potrafi też wykuć miecz.',
    1, 0, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'wolanka' FROM npcs WHERE key = 'kowal_wolanka';

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'zielarka_wolanka',
    'Zofia Górska',
    'neutral',
    'Zna każde górskie zioło i kamień leczniczy. Handluje runą i miksturami dla górników.',
    1, 0, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'wolanka' FROM npcs WHERE key = 'zielarka_wolanka';

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'starszy_gornik_wolanka',
    'Starszy Konrad',
    'quest_giver',
    'Doświadczony górnik. Zna każdy korytarz w Czarnym Hutmanie i szuka kogoś, kto wyjaśni co grasuje w głębinach.',
    0, 1, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'wolanka' FROM npcs WHERE key = 'starszy_gornik_wolanka';

-- ── 9. Strażyn, Twierdza Graniczna ───────────────────────────────────────────

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'kowal_strazyn',
    'Kuźnik Władysław',
    'merchant',
    'Kowal twierdzy. Specjalizuje się w naprawie i ostrzeniu broni wojskowej.',
    1, 0, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'strazyn' FROM npcs WHERE key = 'kowal_strazyn';

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'komendant_strazyn',
    'Komendant Bożena Groźna',
    'quest_giver',
    'Komendant Twierdzy Granicznej. Szuka wiarygodnych ludzi do rozpoznania aktywności za granicą.',
    0, 1, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'strazyn' FROM npcs WHERE key = 'komendant_strazyn';

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'medyk_strazyn',
    'Felczer Ryszard',
    'neutral',
    'Felczer twierdzy. Leczy żołnierzy i przybyszów, choć metodami nieco brutalniejszymi niż klasztorne.',
    1, 0, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'strazyn' FROM npcs WHERE key = 'medyk_strazyn';

-- ── 10. Karczma Pod Trzema Krukami ────────────────────────────────────────────

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'karczmarz_krukow',
    'Bartłomiej Kruk',
    'merchant',
    'Karczmarz. Wie wszystko o każdym, kto przejeżdżał przez skrzyżowanie. Informacje za piwo.',
    1, 1, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'trzech_krukow' FROM npcs WHERE key = 'karczmarz_krukow';

-- ── 11. Cieszowice ────────────────────────────────────────────────────────────

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'kowal_cieszowice',
    'Józef Bednarz-Kowal',
    'merchant',
    'Kowal i bednarz wioski. Skromny, ale uczciwy — ceny niskie, robota solidna.',
    1, 0, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'cieszowice' FROM npcs WHERE key = 'kowal_cieszowice';

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'znachorka_cieszowice',
    'Babcia Marta',
    'neutral',
    'Wiejska znachorka. Leczy ziołami i zaklęciami, w które sama nie wierzy, ale które działają.',
    1, 0, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'cieszowice' FROM npcs WHERE key = 'znachorka_cieszowice';

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'soltys_cieszowice',
    'Sołtys Wiktor',
    'quest_giver',
    'Sołtys Cieszowic. Spokojny człowiek z niepokojem w oczach — coś niepokoi wioskę od tygodni.',
    0, 1, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'cieszowice' FROM npcs WHERE key = 'soltys_cieszowice';

-- ── 12. Pustelnia Świętego Marcina ────────────────────────────────────────────

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'pustelnik_marcin',
    'Pustelnik Marcin',
    'quest_giver',
    'Legendarny asceta. Żyje sam od dekad, ale zna odpowiedź na każde pytanie o pradawny świat i jego tajemnice.',
    0, 1, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'pustelnia_marcina' FROM npcs WHERE key = 'pustelnik_marcin';

-- ── 13. Step Wilków ───────────────────────────────────────────────────────────

INSERT OR IGNORE INTO npcs (key, label, npc_type, description, is_shop, is_quest_giver, is_active, review_status)
VALUES (
    'lowczy_step',
    'Łowczy Oleg',
    'quest_giver',
    'Samotny łowca ze Stepu Wilków. Śledzi bestie przez tygodnie i płaci za informacje o nowych tropach.',
    0, 1, 1, 'permanent'
);
INSERT OR IGNORE INTO npc_locations (npc_id, location_key)
SELECT id, 'step_wilkow' FROM npcs WHERE key = 'lowczy_step';

-- ── End of seed ───────────────────────────────────────────────────────────────
