PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE npcs (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        key                 TEXT NOT NULL UNIQUE,
        label               TEXT NOT NULL,
        npc_type            TEXT NOT NULL DEFAULT 'neutral'
                              CHECK (npc_type IN ('neutral', 'merchant', 'quest_giver', 'ally')),
        description         TEXT,
        personality_json    TEXT NOT NULL DEFAULT '{}',
        is_shop             INTEGER NOT NULL DEFAULT 0,
        shop_inventory_json TEXT NOT NULL DEFAULT '[]',
        is_active           INTEGER NOT NULL DEFAULT 1,
        created_at          TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
    , personality_prompt TEXT DEFAULT NULL, keyword_triggers TEXT NOT NULL DEFAULT '[]', review_status TEXT NOT NULL DEFAULT 'permanent', is_quest_giver INTEGER NOT NULL DEFAULT 0, is_ally INTEGER NOT NULL DEFAULT 0, image_url TEXT DEFAULT NULL, is_crafter INTEGER NOT NULL DEFAULT 0);
INSERT INTO npcs VALUES(1,'merchant_aldric','Aldric, kupiec','merchant','Wędrowny kupiec z towarami pierwszej potrzeby.','{"personality":"sknerski, podejrzliwy, lubi plotki o lokalnych sprawach","topics":["handel","ceny","lokalne wiadomości"],"secret":null}',1,'[{"type":"weapon","key":"shortsword"},{"type":"item","key":"health_potion"},{"type":"item","key":"torch"}]',1,'2026-05-24 17:01:53','2026-06-10 15:43:04',NULL,'[]','permanent',0,0,'/images/tiles/aigm_1780160513_aigm_00043_.png',0);
INSERT INTO npcs VALUES(2,'innkeeper_marta','Marta, karczmarka','neutral','Gospodyni lokalnej karczmy, zna wszystkie plotki.','{"personality":"gadatliwa, serdeczna, dobra gospodyni","topics":["plotki","noclegi","jedzenie","lokalni mieszkańcy"],"secret":null}',0,'[]',1,'2026-05-24 17:01:53','2026-05-30 16:15:07',NULL,'[]','permanent',0,0,'/images/tiles/aigm_1780157701_aigm_00036_.png',0);
INSERT INTO npcs VALUES(3,'quest_giver_eldran','Eldran, mag','quest_giver','Tajemniczy mag szukający odważnych poszukiwaczy.','{"personality":"enigmatyczny, mówi zagadkami, zna starą wiedzę","topics":["magia","zadania","artefakty","historia świata"],"secret":"szuka zaginionego tomu zaklinarzy"}',0,'[]',1,'2026-05-24 17:01:53','2026-05-24 17:01:53',NULL,'[]','permanent',1,0,NULL,0);
INSERT INTO npcs VALUES(4,'blacksmith_goran','Goran, kowal','merchant','Kowal specjalizujący się w broni i zbroi.','{"personality":"lakoniczny, konkretny, dumny ze swojego rzemiosła","topics":["broń","zbroja","naprawa ekwipunku"],"secret":null}',1,'[{"type":"weapon","key":"shortsword"},{"type":"weapon","key":"shortbow"},{"type":"armor","key":"leatherarmor"}]',1,'2026-05-24 17:01:53','2026-06-10 15:43:04',NULL,'[]','permanent',0,0,'/images/tiles/aigm_1780157666_aigm_00035_.png',0);
INSERT INTO npcs VALUES(151,'seed_pending_npc_borys','Borys Kowal','merchant','Stary kowal z Białowilki.','{}',1,'[{"type":"consumable","key":"healing_potion"},{"type":"item","key":"rope_hemp"},{"type":"consumable","key":"torch"},{"type":"item","key":"bandage"}]',1,'2026-05-25 08:20:18','2026-05-30 16:14:03','Mówi krótko.','[]','discarded',0,0,'/images/tiles/aigm_1780157638_refined_aigm_i2i_00005_.png',0);
INSERT INTO npcs VALUES(152,'seed_pending_npc_strazniczka','Strażniczka Lyra','neutral','Młoda strażniczka bramy.','{}',0,'[]',1,'2026-05-25 08:20:18','2026-05-30 16:44:56','Trzyma się regulaminu.','[]','discarded',0,0,'/images/tiles/aigm_1780159488_aigm_00039_.png',0);
INSERT INTO npcs VALUES(153,'seed_pending_npc_zielarka','Zielarka Anya','quest_giver','Mieszka w samotnej chacie.','{}',0,'[]',1,'2026-05-25 08:20:18','2026-05-25 08:20:18','Cicha, mistyczna.','[]','discarded',1,0,NULL,0);
INSERT INTO npcs VALUES(154,'seed_pending_npc_pijak','Pijak Krzywy Olaf','neutral','Stały bywalec karczmy.','{}',0,'[]',1,'2026-05-25 08:20:18','2026-05-30 16:46:05','Wymienia plotki za piwo.','[]','discarded',0,0,'/images/tiles/aigm_1780159545_aigm_00040_.png',0);
INSERT INTO npcs VALUES(155,'seed_pending_npc_sojusznik','Łowca Ravan','ally','Doświadczony łowca z południa.','{}',0,'[]',1,'2026-05-25 08:20:18','2026-05-30 16:47:48','Małomówny, lojalny.','[]','discarded',0,1,'/images/tiles/aigm_1780159656_refined_aigm_i2i_00007_.png',0);
INSERT INTO npcs VALUES(1024,'burmistrz_edrik_voss','Burmistrz Edrik Voss','quest_giver','Przywódca miasteczka, wyczerpany i coraz bardziej desperacki. Publicznie nawołuje do wybicia wampirów, prywatnie zaś panicznie boi się prawdy o tym, co jego przodkowie ukryli pod miastem.','{"description": "Przywódca miasteczka, wyczerpany i coraz bardziej desperacki. Publicznie nawołuje do wybicia wampirów, prywatnie zaś panicznie boi się prawdy o tym, co jego przodkowie ukryli pod miastem."}',0,'[]',1,'2026-05-30T06:42:59.845673','2026-05-30T06:42:59.845673','Lokalny przywódca i obrońca ludzi w oczach tłumu. Mówi stanowczo, lecz zdradza oznaki zmęczenia i narastającej paniki. Ukrywa księgę rodową opisującą dawne rytuały i część paktu. Chce ocalić miasteczko bez ujawniania winy własnego rodu.','[]','permanent',1,0,NULL,0);
COMMIT;
