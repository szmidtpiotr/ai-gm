"""TDD: Issue #1085 — forge generate-plan auto-creates key_enemies in game_config_enemies."""
import json
import sqlite3
import sys

sys.path.insert(0, "/app")
from _fixtures_schema import table_sql


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
        """ + table_sql("game_config_enemies") + """
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
        """ + table_sql("game_config_enemies") + """
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


# ─── Clamp HP/AC per tier + difficulty (#1085 rozszerzenie) ──────────────────

def test_clamp_enemy_stats_caps_hp_for_low_difficulty():
    """Dla difficulty=1, elite nie może mieć HP > scaled_max = 60 * 0.6 = 36."""
    from app.routers.adventure_forge import _clamp_enemy_stats
    hp, ac = _clamp_enemy_stats(hp=80, ac=15, tier="elite", difficulty=1)
    assert hp <= 36, f"Elite diff=1: HP powinno być ≤36, jest {hp}"
    assert hp >= 30, f"Elite diff=1: HP nie może spaść poniżej min=30, jest {hp}"


def test_clamp_enemy_stats_caps_hp_for_difficulty_2():
    """Dla difficulty=2, standard nie może przekroczyć 28 * 0.7 = 19."""
    from app.routers.adventure_forge import _clamp_enemy_stats
    hp, ac = _clamp_enemy_stats(hp=50, ac=14, tier="standard", difficulty=2)
    assert hp <= 19, f"Standard diff=2: HP powinno być ≤19, jest {hp}"
    assert hp >= 8, f"Standard diff=2: HP nie może spaść poniżej min=8, jest {hp}"


def test_clamp_enemy_stats_does_not_reduce_below_tier_min():
    """Clamp nie może zejść poniżej tier_min nawet dla difficulty=1."""
    from app.routers.adventure_forge import _clamp_enemy_stats
    hp, ac = _clamp_enemy_stats(hp=5, ac=8, tier="elite", difficulty=1)
    assert hp >= 30, f"Elite min HP to 30, got {hp}"


def test_clamp_enemy_stats_passes_through_on_difficulty_5():
    """Difficulty=5 — maksymalny zakres, HP w normie przechodzi bez zmian."""
    from app.routers.adventure_forge import _clamp_enemy_stats
    hp, ac = _clamp_enemy_stats(hp=55, ac=15, tier="elite", difficulty=5)
    assert hp == 55, f"Diff=5, HP 55 mieści się w elite max=60, nie powinno być clampowane, got {hp}"


def test_auto_create_forge_enemies_applies_clamp():
    """_auto_create_forge_enemies() clampuje HP/AC przez _clamp_enemy_stats."""
    from app.routers.adventure_forge import _auto_create_forge_enemies
    import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        """ + table_sql("game_config_enemies") + """
    """)

    # Difficulty=1, standard — LLM halucynuje HP=100 i AC=20
    enemies = [{"key": "big_bad", "name": "Big Bad", "tier": "standard",
                "hp_base": 100, "ac_base": 20, "damage_die": "2d10"}]
    _auto_create_forge_enemies(conn, template_id=1, enemies=enemies, difficulty=1)

    row = conn.execute("SELECT hp_base, ac_base FROM game_config_enemies WHERE key='big_bad'").fetchone()
    assert row["hp_base"] <= 16, f"HP powinno być clampowane (standard diff=1 max≈16), got {row['hp_base']}"
    assert row["ac_base"] <= 11, f"AC powinno być clampowane (standard diff=1 max≈11), got {row['ac_base']}"
