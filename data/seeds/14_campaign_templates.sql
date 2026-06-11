-- S14: Campaign templates seed (#502)
-- Tables: campaign_templates
-- Depends on S10 (locations for start_hex context), S11 (NPCs for required_npc_keys).
-- campaign_templates table created by migration (migrations_admin.py S13/S14 block).
-- Safe to re-run: INSERT OR IGNORE (by title uniqueness via status+title combination is not unique,
-- so we use a named approach — check by created_by='seed' and title match).
-- Using INSERT OR IGNORE won't work without a UNIQUE constraint, so we guard with NOT EXISTS.

INSERT INTO campaign_templates
    (title, description, difficulty_rating, atmosphere, gm_plan_json, hook_ids,
     status, created_by, required_npc_keys, required_beats, player_visible)
SELECT
    'Pierwsze Kroki',
    'Kampania tutorialowa dla nowych graczy. Bohater poznaje świat, mechaniki walki i handlu w bezpiecznym otoczeniu miasta Vilnograd i okolic. Idealna jako wprowadzenie do systemu.',
    1,
    'Przyjazny, bezpieczny świat z wyraźnymi wskazówkami. Powoli odkrywane możliwości.',
    '{"arcs":[{"id":"arc_tutorial","label":"Tutorial","key_beats":[{"beat_key":"first_combat","label":"Pierwsza walka"},{"beat_key":"first_merchant","label":"Pierwszy handel"},{"beat_key":"first_exploration","label":"Pierwsza eksploracja"}],"status":"active"}]}',
    '[]',
    'published',
    'seed',
    '["innkeeper_marta","blacksmith_goran"]',
    '["first_combat","first_merchant","first_exploration"]',
    1
WHERE NOT EXISTS (
    SELECT 1 FROM campaign_templates WHERE title = 'Pierwsze Kroki' AND created_by = 'seed'
);

INSERT INTO campaign_templates
    (title, description, difficulty_rating, atmosphere, gm_plan_json, hook_ids,
     status, created_by, required_npc_keys, required_beats, player_visible)
SELECT
    'Przeklęte Ziemie',
    'Mroczna kraina dotknięta starą klątwą. Bohater musi odkryć źródło zła nawiedzającego okoliczne wioski i stawić mu czoła. Eksploracja, intrygi i walka z nieumarłymi.',
    3,
    'Mroczny, gotycki klimat. Mgła, ruiny, duchy przeszłości. Moralnie niejednoznaczne wybory.',
    '{"arcs":[{"id":"arc_curse","label":"Klątwa","key_beats":[{"beat_key":"discover_curse","label":"Odkrycie klątwy"},{"beat_key":"seek_origin","label":"Poszukiwanie źródła"},{"beat_key":"confront_evil","label":"Konfrontacja ze złem"},{"beat_key":"lift_curse","label":"Zdjęcie klątwy"}],"status":"active"}]}',
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
    '{"arcs":[{"id":"arc_awakening","label":"Przebudzenie","key_beats":[{"beat_key":"lich_awakens","label":"Przebudzenie Licza"},{"beat_key":"seek_allies","label":"Poszukiwanie sojuszników"}],"status":"active"},{"id":"arc_phylactery","label":"Filar Duszy","key_beats":[{"beat_key":"locate_phylactery","label":"Lokalizacja filaru"},{"beat_key":"destroy_phylactery","label":"Zniszczenie filaru"},{"beat_key":"final_battle","label":"Ostateczna bitwa"}],"status":"planned"}]}',
    '[]',
    'published',
    'seed',
    '["kronikarz_vilnograd","kapitan_krolewski"]',
    '["lich_awakens","seek_allies","locate_phylactery","destroy_phylactery","final_battle"]',
    1
WHERE NOT EXISTS (
    SELECT 1 FROM campaign_templates WHERE title = 'Cień Licza' AND created_by = 'seed'
);
