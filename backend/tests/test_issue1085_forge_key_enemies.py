"""TDD: Issue #1085 — forge generate-plan auto-creates key_enemies in game_config_enemies."""
import json
import sqlite3
import sys

sys.path.insert(0, "/app")


# ─── Test główny 1: CampaignPlan zachowuje key_enemies po walidacji ───────────

def test_campaign_plan_preserves_key_enemies():
    """CampaignPlan.model_validate() z key_enemies → model_dump() zawiera key_enemies."""
    from app.services.campaign_plan_service import CampaignPlan

    plan_dict = {
        "title": "Test",
        "premise": "Test premise",
        "acts": [
            {
                "number": 1,
                "title": "Akt 1",
                "summary": "Opis aktu",
                "key_beats": [
                    {"beat_key": "beat_1", "summary": "Coś się dzieje", "optional": False}
                ],
                "completed": False,
            }
        ],
        "endings": [
            {"id": "e1", "title": "Koniec", "type": "primary", "description": "Opis", "requirements": []},
            {"id": "e2", "title": "Koniec Alt", "type": "alternate", "description": "Opis", "requirements": []},
        ],
        "key_npcs": [
            {
                "key": "npc_boss",
                "name": "Szef",
                "role": "antagonist",
                "importance": "critical",
                "deviation_consequence": "branch",
                "alive": True,
            }
        ],
        "key_locations": [
            {"key": "loc_start", "name": "Start", "role": "start", "visited": False}
        ],
        "key_enemies": [
            {
                "key": "goblin_warlord",
                "name": "Gobliński Wódz",
                "tier": "elite",
                "hp_base": 40,
                "ac_base": 14,
                "damage_die": "1d8+2",
                "description": "Groźny przywódca goblinów",
                "note": "Może przywołać posiłki",
            }
        ],
        "active_act": 1,
        "scene_log": [],
        "deviations": [],
        "branches": [],
        "engine_private": {
            "secret_predisposition_hint": "hint",
            "hidden_twist": "twist",
            "contingency": "contingency",
        },
    }

    plan = CampaignPlan.model_validate(plan_dict)
    dumped = plan.model_dump()

    assert "key_enemies" in dumped, "key_enemies musi być w model_dump()"
    assert len(dumped["key_enemies"]) == 1, "Musi być 1 wróg"
    enemy = dumped["key_enemies"][0]
    assert enemy["key"] == "goblin_warlord"
    assert enemy["tier"] == "elite"
    assert enemy["hp_base"] == 40


# ─── Test główny 2: helper _auto_create_forge_enemies tworzy wpisy w DB ───────

def test_auto_create_forge_enemies_inserts_pending_rows():
    """_auto_create_forge_enemies() tworzy wiersze w game_config_enemies z review_status='pending' i created_by='forge'."""
    from app.routers.adventure_forge import _auto_create_forge_enemies

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE game_config_enemies (
            key TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            hp_base INTEGER NOT NULL,
            ac_base INTEGER NOT NULL,
            attack_bonus INTEGER NOT NULL DEFAULT 0,
            dex_modifier INTEGER NOT NULL DEFAULT 0,
            damage_die TEXT NOT NULL,
            description TEXT,
            note TEXT,
            tier TEXT NOT NULL DEFAULT 'standard',
            damage_type TEXT NOT NULL DEFAULT 'physical',
            attacks_per_turn INTEGER NOT NULL DEFAULT 1,
            damage_bonus INTEGER NOT NULL DEFAULT 0,
            xp_award INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            review_status TEXT NOT NULL DEFAULT 'permanent',
            created_by TEXT DEFAULT NULL,
            template_id INTEGER DEFAULT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    enemies = [
        {
            "key": "goblin_warlord",
            "name": "Gobliński Wódz",
            "tier": "elite",
            "hp_base": 40,
            "ac_base": 14,
            "damage_die": "1d8+2",
            "description": "Groźny przywódca",
            "note": "Przywołuje posiłki",
        }
    ]

    result = _auto_create_forge_enemies(conn, template_id=99, enemies=enemies)

    assert len(result) == 1, "Jeden wróg powinien być stworzony"
    assert result[0]["key"] == "goblin_warlord"
    assert result[0]["name"] == "Gobliński Wódz"

    row = conn.execute("SELECT * FROM game_config_enemies WHERE key='goblin_warlord'").fetchone()
    assert row is not None, "Wróg musi być w bazie"
    assert row["review_status"] == "pending", "Status musi być pending"
    assert row["created_by"] == "forge", "created_by musi być 'forge'"
    assert row["template_id"] == 99, "template_id musi być ustawiony"
    assert row["hp_base"] == 40
    assert row["tier"] == "elite"


# ─── Test główny 3: duplikat key — nie crashuje, używa innego klucza ────────

def test_auto_create_forge_enemies_handles_key_conflict():
    """Jeśli klucz już istnieje w DB, helper nadaje suffix zamiast crashować."""
    from app.routers.adventure_forge import _auto_create_forge_enemies

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE game_config_enemies (
            key TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            hp_base INTEGER NOT NULL DEFAULT 20,
            ac_base INTEGER NOT NULL DEFAULT 12,
            attack_bonus INTEGER NOT NULL DEFAULT 0,
            dex_modifier INTEGER NOT NULL DEFAULT 0,
            damage_die TEXT NOT NULL DEFAULT '1d6',
            description TEXT,
            note TEXT,
            tier TEXT NOT NULL DEFAULT 'standard',
            damage_type TEXT NOT NULL DEFAULT 'physical',
            attacks_per_turn INTEGER NOT NULL DEFAULT 1,
            damage_bonus INTEGER NOT NULL DEFAULT 0,
            xp_award INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            review_status TEXT NOT NULL DEFAULT 'permanent',
            created_by TEXT DEFAULT NULL,
            template_id INTEGER DEFAULT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("INSERT INTO game_config_enemies (key, label, damage_die) VALUES ('goblin', 'Goblin stary', '1d4')")

    enemies = [{"key": "goblin", "name": "Goblin nowy", "tier": "standard", "hp_base": 10, "ac_base": 10, "damage_die": "1d4"}]
    result = _auto_create_forge_enemies(conn, template_id=1, enemies=enemies)

    assert len(result) == 1
    # Key musi być inny niż 'goblin' (już zajęty)
    assert result[0]["key"] != "goblin", "Klucz duplikatu musi być zmieniony"
    count = conn.execute("SELECT COUNT(*) FROM game_config_enemies").fetchone()[0]
    assert count == 2, "Oba wiersze muszą być w DB"


# ─── Backward compat: CampaignPlan bez key_enemies nadal przechodzi ─────────

def test_campaign_plan_without_key_enemies_still_valid():
    """CampaignPlan bez pola key_enemies (stary format) nadal jest walidowany poprawnie."""
    from app.services.campaign_plan_service import CampaignPlan

    plan_dict = {
        "title": "Stary format",
        "premise": "Bez wrogów",
        "acts": [
            {
                "number": 1,
                "title": "Akt 1",
                "summary": "Opis",
                "key_beats": [{"beat_key": "b1", "summary": "Beat"}],
                "completed": False,
            }
        ],
        "endings": [
            {"id": "e1", "title": "Koniec", "type": "primary", "description": "Opis", "requirements": []},
            {"id": "e2", "title": "Alt", "type": "alternate", "description": "Opis", "requirements": []},
        ],
        "key_npcs": [
            {"key": "npc1", "name": "NPC", "role": "guide", "importance": "supporting",
             "deviation_consequence": "ignore", "alive": True}
        ],
        "key_locations": [{"key": "loc1", "name": "Miejsce", "role": "start", "visited": False}],
        # brak key_enemies
        "active_act": 1,
        "scene_log": [],
        "deviations": [],
        "branches": [],
        "engine_private": {
            "secret_predisposition_hint": "h",
            "hidden_twist": "t",
            "contingency": "c",
        },
    }

    plan = CampaignPlan.model_validate(plan_dict)
    dumped = plan.model_dump()
    assert "key_enemies" in dumped, "key_enemies musi istnieć (pusta lista)"
    assert dumped["key_enemies"] == [], "Pusta lista gdy brak w JSON"
