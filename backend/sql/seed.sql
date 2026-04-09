INSERT OR IGNORE INTO users (id, username, password_hash, display_name)
VALUES (1, 'demo', 'demo', 'Demo Player');

INSERT OR IGNORE INTO campaigns (id, title, system_id, model_id, owner_user_id, mode, status)
VALUES (1, 'Fantasy Test', 'fantasy', 'gemma3:1b', 1, 'solo', 'active');

INSERT OR IGNORE INTO campaign_members (campaign_id, user_id, role)
VALUES (1, 1, 'owner');

INSERT OR IGNORE INTO characters (
    id,
    campaign_id,
    user_id,
    name,
    system_id,
    sheet_json,
    location,
    is_active
) VALUES (
    1,
    1,
    1,
    'Arthos',
    'fantasy',
    '{"name":"Arthos","class":"adventurer","level":1,"xp":0,"attributes":{"might":2,"agility":1,"wits":1,"will":0},"skills":{"melee":2,"ranged":0,"athletics":2,"stealth":0,"lore":0,"notice":2,"survival":0,"persuasion":0,"intimidation":0,"craft":0,"magic":0,"healing":0},"resources":{"health":{"current":12,"max":12},"focus":{"current":5,"max":5},"defense":11},"inventory":{"slots_max":10,"coins":10},"conditions":[],"equipped":{"weapon":"rusty sword","armor":"leather jack"},"notes":[]}',
    'Roadside inn',
    1
);
