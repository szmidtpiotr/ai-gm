-- S3: XP system + economy config seed (#491)
-- Tables: game_config_xp_awards, game_config_xp_rewards, game_config_services
-- Generated from canonical live DEV rows. Idempotent: INSERT OR IGNORE.
-- Depends on S1 (meta config). 8 gold-sink services for [SPEND_GOLD:key] tags.


-- game_config_xp_awards
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('campaign','beat_complete','Cel kampanii ukończony','[BEAT_COMPLETE] tag',30,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('campaign','campaign_ending','Zakończenie kampanii','[CAMPAIGN_END] tag',200,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('campaign','dungeon_cleared','Loch wyczyszczony','[DUNGEON_CLEAR] tag',75,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('campaign','side_quest','Zlecenie poboczne ukończone','[QUEST_COMPLETE] tag',40,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('combat','death_save_survived','Przeżycie rzutu na śmierć','Po każdym przeżytym rzucie na śmierć',15,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('combat','kill_boss','Zabicie bossa','Wróg tier=boss',150,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('combat','kill_elite','Zabicie elitarnego wroga','Wróg tier=elite',50,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('combat','kill_standard','Zabicie standardowego wroga','Wróg tier=standard',25,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('combat','kill_weak','Zabicie słabego wroga','Wróg tier=weak',10,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('combat','outnumbered_victory','Zwycięstwo w przewadze (3+ wrogów)','Wszyscy wrogowie pokonani przy 3+ na starcie',20,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('exploration','hidden_room','Odkrycie ukrytego przejścia','[DISCOVERY:secret_location] tag',10,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('exploration','location_new','Odkrycie nowej lokacji','Pierwsza wizyta w makrolokacji',15,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('exploration','npc_first_talk','Pierwsza rozmowa z NPC','Pierwszy DIALOGUE z danym kluczem NPC',5,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('exploration','secret','Odkrycie sekretu / wskazówki','[DISCOVERY:lore_key] tag',10,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('narrative','_cap_per_session','Limit narracyjnych PD / sesję','Maksymalna kwota z kategorii narracja na sesję',50,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('narrative','clever_environment','Kreatywne użycie otoczenia','Nieoczekiwane rozwiązanie z użyciem otoczenia',10,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('narrative','heroic_sacrifice','Bohaterskie poświęcenie','Obrażenia przyjęte celowo dla ochrony NPC',25,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('narrative','major_discovery','Odkrycie kluczowej prawdy','Ważna tajemnica kampanii ujawniona',15,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('narrative','moral_choice','Trudny wybór moralny','Decyzja z realnym kosztem dla bohatera',15,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('narrative','nonviolent_solution','Rozwiązanie bez walki','Konflikt zakończony bez walki',20,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('narrative','unexpected_ally','Pozyskanie niespodziewanego sojusznika','Wróg przekonany do współpracy',10,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('session','session_20turns','Sesja 20–39 tur','Przyznawane przy długim odpoczynku',10,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('session','session_40turns','Sesja 40+ tur','Przyznawane przy długim odpoczynku',20,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('skills','opposed_major_npc','Wygrana w teście z ważną postacią','NPC importance=critical lub supporting',10,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('skills','skill_dc_12','Test umiejętności DC 12–15','Sukces w teście DC w zakresie 12-15',3,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('skills','skill_dc_16','Test umiejętności DC 16–19','Sukces w teście DC w zakresie 16-19',8,1,1);
INSERT OR IGNORE INTO game_config_xp_awards (category, source_key, label, description, xp_amount, is_active, is_locked) VALUES('skills','skill_dc_20','Test umiejętności DC 20+','Wyjątkowy sukces w teście',15,1,1);

-- game_config_xp_rewards
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('enemy_tier_weak','enemy_tier','Wróg: ślaby / tło','Pas [S10b]: 2–5 XP — domyślnie 3',3,10,1);
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('enemy_tier_standard','enemy_tier','Wróg: standard','Pas [S10b]: 5–12 XP — domyślnie 8',8,20,1);
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('enemy_tier_elite','enemy_tier','Wróg: elita / mały boss','Pas [S10b]: 25–50 XP — domyślnie 30',30,30,1);
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('enemy_tier_boss','enemy_tier','Wróg: boss / wyjątkowe zagrożenie','Pas [S10b]: 50–120 XP — domyślnie 70',70,40,1);
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('quest_minor','quest','Quest / wątek poboczny','Szacunek [S10b]: 10–25 XP',15,50,1);
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('quest_main','quest','Quest / cel główny kampanii','Szacunek [S10b]: 40–100 XP (po modelu questów)',70,60,1);
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('mg_grant_small','mg_grant','MG: drobny plus fabularny','Pas [S10b]: 3–8 XP',5,100,1);
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('mg_grant_scene','mg_grant','MG: mini-cel / postęp sceny','Pas [S10b]: 5–15 XP',10,110,1);
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('mg_grant_breakthrough','mg_grant','MG: istotny przełom','Pas [S10b]: 15–35 XP',25,120,1);
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('mg_grant_exceptional','mg_grant','MG: wybitny sukces (rzadko)','Pas [S10b]: 35–60 XP',45,130,1);
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('campaign.beat_complete','campaign','Cel bitu ukończony','XS1: +30 XP za ukończenie bitu narracyjnego',30,200,1);
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('campaign.side_quest','campaign','Quest poboczny ukończony','XS2: +40 XP za [QUEST_COMPLETE]',40,210,1);
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('campaign.dungeon_cleared','campaign','Loch oczyszczony','XS3: +75 XP za [DUNGEON_CLEAR]',75,220,1);
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('campaign.campaign_ending','campaign','Koniec kampanii','XS4: +200 XP za [CAMPAIGN_END]',200,230,1);
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('exploration.location_new','exploration','Pierwsza wizyta w lokacji','XS5: +15 XP — pierwsza makro-lokacja',15,300,1);
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('exploration.npc_first_talk','exploration','Pierwsza rozmowa z NPC','XS6: +5 XP za DIALOGUE z nowym npc_key',5,310,1);
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('exploration.secret','exploration','Odkrycie: lore/tajemnica','XS7: +10 XP za [DISCOVERY:lore_key]',10,320,1);
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('exploration.hidden_room','exploration','Odkrycie: ukryta lokacja','XS8: +10 XP za [DISCOVERY:secret_location]',10,330,1);
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('skills.skill_dc_12','skills','Test biegłości DC 12-15','XS9: +3 XP za sukces DC ∈ [12-15]',3,400,1);
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('skills.skill_dc_16','skills','Test trudny DC 16-19','XS10: +8 XP za sukces DC ∈ [16-19]',8,410,1);
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('skills.skill_dc_20','skills','Test legendarny DC ≥ 20','XS11: +15 XP za sukces DC ≥ 20',15,420,1);
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('narrative.free_grant','narrative','Nagroda narracyjna (LLM tag)','XS12: [XP_GRANT:powód:ilość] — kap 50 XP/sesja',10,500,1);
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('combat.outnumbered_victory','combat','Zwycięstwo w przewadze wroga','XS13: +20 XP — walka z 3+ wrogami',20,600,1);
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('combat.death_save_survived','combat','Przeżycie rzutu na śmierć','XS14: +15 XP za przeżycie death save',15,610,1);
INSERT OR IGNORE INTO game_config_xp_rewards (key, category, label, description, xp_amount, sort_order, is_active) VALUES('session.start_bonus','session','Bonus za powrót do sesji','XS15: +10 XP za nową sesję po ≥30 min przerwie',10,700,1);

-- game_config_services
INSERT OR IGNORE INTO game_config_services (key, label, cost_gp, description, is_active) VALUES('blacksmith_repair','Kowal: naprawa ekwipunku',15,'Naprawa uszkodzonej broni lub zbroi',1);
INSERT OR IGNORE INTO game_config_services (key, label, cost_gp, description, is_active) VALUES('guide_day','Przewodnik: jeden dzień',12,'Miejscowy przewodnik przez niebezpieczny teren',1);
INSERT OR IGNORE INTO game_config_services (key, label, cost_gp, description, is_active) VALUES('healer_heavy','Uzdrowiciel: ciężkie rany',50,'Leczenie poważnych ran wymagające magii lub chirurgii',1);
INSERT OR IGNORE INTO game_config_services (key, label, cost_gp, description, is_active) VALUES('healer_light','Uzdrowiciel: lekkie rany',10,'Opatrzenie ran niegroźnych: skaleczenia, stłuczenia',1);
INSERT OR IGNORE INTO game_config_services (key, label, cost_gp, description, is_active) VALUES('inn_night','Gospoda: jedna noc',5,'Nocleg i posiłek w gospodzie — standardowy pokój',1);
INSERT OR IGNORE INTO game_config_services (key, label, cost_gp, description, is_active) VALUES('inn_night_fine','Gospoda: luksusowy pokój',20,'Nocleg w prywatnym pokoju z pościelą i śniadaniem',1);
INSERT OR IGNORE INTO game_config_services (key, label, cost_gp, description, is_active) VALUES('messenger','Posłaniec: wiadomość',8,'Wysłanie wiadomości do pobliskiego miasta',1);
INSERT OR IGNORE INTO game_config_services (key, label, cost_gp, description, is_active) VALUES('stable_night','Stajnia: jedna noc',3,'Nocleg i pasza dla konia lub wierzchowca',1);
