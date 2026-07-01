-- S14: Campaign templates seed (#502, updated HF-8 #539)
-- Tables: campaign_templates
-- Depends on S10 (locations for start_hex context), S11 (NPCs for required_npc_keys).
-- campaign_templates table created by migration (migrations_admin.py S13/S14 block).
-- Safe to re-run: NOT EXISTS guard by title+created_by.
-- HF-8: key_beats now include objective_type for U8 auto-complete (empty = match any target).
-- Pierwsze Kroki removed — replaced by proper auto-onboarding (see issue #XXXX).

INSERT INTO campaign_templates
    (title, description, difficulty_rating, atmosphere, gm_plan_json, hook_ids,
     status, created_by, required_npc_keys, required_beats, player_visible)
SELECT
    'Przeklęte Ziemie',
    'Mroczna kraina dotknięta starą klątwą. Bohater musi odkryć źródło zła nawiedzającego okoliczne wioski i stawić mu czoła. Eksploracja, intrygi i walka z nieumarłymi.',
    3,
    'Mroczny, gotycki klimat. Mgła, ruiny, duchy przeszłości. Moralnie niejednoznaczne wybory.',
    '{"arcs":[{"id":"arc_curse","label":"Klątwa","key_beats":[{"beat_key":"discover_curse","label":"Odkrycie klątwy","objective_type":"visit_location"},{"beat_key":"seek_origin","label":"Poszukiwanie źródła","objective_type":"talk_to_npc","optional":true},{"beat_key":"confront_evil","label":"Konfrontacja ze złem","objective_type":"kill_enemy"},{"beat_key":"lift_curse","label":"Zdjęcie klątwy","objective_type":"visit_location"}],"status":"active"}],"endings":[{"id":"ending_primary","type":"primary","title":"Klątwa zdjęta","summary":"Źródło zła zostało odnalezione i zniszczone. Mgła opada znad wiosek, a duchy przeszłości w końcu zaznają spokoju. Kraina powoli wraca do życia.","requirements":["lift_curse"]}]}',
    '[]',
    'published',
    'seed',
    '["kapitan_krolewski","brat_tomasz_kronikarz"]',
    '["discover_curse","seek_origin","confront_evil","lift_curse"]',
    1
WHERE NOT EXISTS (
    SELECT 1 FROM campaign_templates WHERE title = 'Przeklęte Ziemie' AND created_by = 'seed'
);

INSERT INTO campaign_templates
    (title, description, difficulty_rating, atmosphere, gm_plan_json, hook_ids,
     status, created_by, required_npc_keys, required_beats, player_visible)
SELECT
    'Cień Licza',
    'Epicka kampania dla doświadczonych bohaterów. Starożytny lich przebudził się po wiekach uśpienia i jego cień pada na cały kontynent. Tylko drużyna zdolna odszukać jego filar duszy może go pokonać.',
    5,
    'Epicki, apokaliptyczny. Armie nieumarłych, padające królestwa, ostatnia nadzieja świata.',
    '{"arcs":[{"id":"arc_awakening","label":"Przebudzenie","key_beats":[{"beat_key":"lich_awakens","label":"Przebudzenie Licza"},{"beat_key":"seek_allies","label":"Poszukiwanie sojuszników","objective_type":"talk_to_npc","optional":true}],"status":"active"},{"id":"arc_phylactery","label":"Filar Duszy","key_beats":[{"beat_key":"locate_phylactery","label":"Lokalizacja filaru","objective_type":"visit_location"},{"beat_key":"destroy_phylactery","label":"Zniszczenie filaru","objective_type":"kill_enemy"},{"beat_key":"final_battle","label":"Ostateczna bitwa","objective_type":"kill_enemy"}],"status":"planned"}],"endings":[{"id":"ending_primary","type":"primary","title":"Cień rozwiany","summary":"Filar duszy Licza legł w gruzach, a starożytne zło rozsypało się w proch. Armie nieumarłych padają bez swojego pana — kontynent ocalony, a imię bohatera przejdzie do legendy.","requirements":["final_battle"]}]}',
    '[]',
    'published',
    'seed',
    '["kronikarz_vilnograd","kapitan_krolewski"]',
    '["lich_awakens","seek_allies","locate_phylactery","destroy_phylactery","final_battle"]',
    1
WHERE NOT EXISTS (
    SELECT 1 FROM campaign_templates WHERE title = 'Cień Licza' AND created_by = 'seed'
);
