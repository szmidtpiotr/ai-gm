"""TDD: Issue #674 (L5) — Walka: absolutna skala D1–D5 (koniec rubber-bandingu).

Weryfikuje:
- TIER_ENEMY_LEVELS: 5 wpisów D1-D5; boss_level > max_level dla D1-D4
- D3 enemy ma wyższe HP niż D1 enemy (ten sam base)
- Poziom bohatera nie wpływa na staty wroga w lochu (tier decyduje)
- Endless cycle: +1 level/cykl do cap 10, potem +15% HP/dmg_bonus per overflow cykl
- resolve_tile_content używa dungeon_tier, nie hero_level
- _reroll_repeated_tile_enemies zmienia wrogów na powtórzonym kafelku
- enter_dungeon_tiles przechowuje dungeon_difficulty w run
"""
from __future__ import annotations

import json
import sqlite3
import sys
import os
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, "/app")

import app.services.dungeon_tile_service as dts


# ─── Schema pomocnicze (in-memory) ────────────────────────────────────────────

SCHEMA = """
CREATE TABLE dungeon_tile_categories (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE dungeon_tiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_key TEXT NOT NULL,
    label TEXT NOT NULL,
    image_url TEXT,
    doors_json TEXT DEFAULT '[]',
    room_description TEXT DEFAULT '',
    enemies_json TEXT DEFAULT '[]',
    items_json TEXT DEFAULT '[]',
    active_states_json TEXT DEFAULT '[]',
    riddle_key TEXT,
    exit_conditions_json TEXT DEFAULT '[]',
    is_boss_tile INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE game_config_enemies (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    hp_base INTEGER DEFAULT 5,
    ac_base INTEGER DEFAULT 8,
    attack_bonus INTEGER DEFAULT 0,
    damage_die TEXT DEFAULT '1d6',
    damage_bonus INTEGER DEFAULT 0,
    dex_modifier INTEGER DEFAULT 0,
    tier TEXT DEFAULT 'standard',
    stats_json TEXT DEFAULT NULL,
    xp_award INTEGER DEFAULT 0,
    loot_table_key TEXT DEFAULT NULL,
    drop_chance REAL DEFAULT 1.0,
    loot_tier TEXT DEFAULT NULL,
    skills_json TEXT DEFAULT NULL
);

CREATE TABLE game_config_items (key TEXT PRIMARY KEY, label TEXT NOT NULL);
CREATE TABLE game_config_weapons (key TEXT PRIMARY KEY, label TEXT NOT NULL);
CREATE TABLE game_config_consumables (key TEXT PRIMARY KEY, label TEXT NOT NULL);
CREATE TABLE game_config_riddles (
    key TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    answer TEXT NOT NULL,
    answer_alts TEXT DEFAULT '[]',
    hints TEXT DEFAULT '[]',
    is_active INTEGER DEFAULT 1,
    difficulty INTEGER DEFAULT 1,
    theme TEXT DEFAULT NULL
);
CREATE TABLE game_dungeons (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    location_key TEXT,
    rooms INTEGER DEFAULT 4,
    enemy_pool TEXT DEFAULT '[]',
    boss_enemy TEXT,
    loot_tier TEXT DEFAULT 'standard',
    atmosphere TEXT,
    cooldown_hours INTEGER DEFAULT 72,
    min_level INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    chest_loot_table_key TEXT,
    boss_loot_table_key TEXT,
    room_loot_chance REAL DEFAULT 0.5,
    room_types_json TEXT DEFAULT '{}',
    riddle_source TEXT,
    riddle_max_hints INTEGER DEFAULT 2,
    dungeon_difficulty INTEGER DEFAULT 1,
    tile_category_key TEXT,
    tile_count INTEGER DEFAULT 4,
    boss_tile_id INTEGER,
    endless_growth_n INTEGER DEFAULT 0
);
CREATE TABLE game_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    session_flags TEXT DEFAULT '{}'
);
CREATE TABLE world_state_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    source TEXT,
    snapshot_json TEXT
);
CREATE TABLE character_dungeon_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL,
    dungeon_key TEXT NOT NULL,
    completed_at TEXT,
    UNIQUE(character_id, dungeon_key)
);
"""


@pytest.fixture
def db(tmp_path):
    """In-memory SQLite with full tile+dungeon schema."""
    db_file = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO dungeon_tile_categories VALUES ('krypta','Krypta',1)")
    conn.commit()
    return db_file


# ─── T1: TIER_ENEMY_LEVELS table ──────────────────────────────────────────────

def test_tier_enemy_levels_table():
    """TIER_ENEMY_LEVELS musi mieć wpisy D1–D5; boss_level > max_level dla D1–D4."""
    tbl = dts.TIER_ENEMY_LEVELS
    assert len(tbl) == 5, f"Expected 5 tiers, got {len(tbl)}"
    for tier in range(1, 6):
        assert tier in tbl, f"Missing tier {tier}"
        min_lvl, max_lvl, boss_lvl = tbl[tier]
        assert min_lvl <= max_lvl, f"D{tier}: min_lvl > max_lvl"
        if tier < 5:
            assert boss_lvl > max_lvl, f"D{tier}: boss_lvl must be > max_lvl"
    # Spot checks from Decyzja 8
    assert tbl[1] == (1, 2, 3), f"D1 expected (1,2,3), got {tbl[1]}"
    assert tbl[3][2] == 7, f"D3 boss must be level 7, got {tbl[3][2]}"
    assert tbl[5][2] == 10, f"D5 boss must be level 10, got {tbl[5][2]}"


# ─── T2: D3 > D1 HP ───────────────────────────────────────────────────────────

def test_scale_d1_enemy_lower_than_d3():
    """D3 enemy ma wyższe HP niż D1 enemy przy tym samym base (CON=14 → CON_mod=2)."""
    base = {"hp_base": 5, "ac_base": 8, "attack_bonus": 0, "damage_bonus": 0,
            "stats_json": '{"CON": 14}'}  # CON_mod=2, skalowanie widoczne
    # Use boss=False, cycle=1; fix random for determinism
    with patch("app.services.dungeon_tile_service.random") as mock_rnd:
        mock_rnd.randint.side_effect = [1, 5]  # D1→lvl1, D3→lvl5
        mock_rnd.choice = __import__("random").choice
        mock_rnd.sample = __import__("random").sample
        scaled_d1 = dts.scale_enemy_for_dungeon_tier(dict(base), 1, is_boss=False, cycle=1)
        scaled_d3 = dts.scale_enemy_for_dungeon_tier(dict(base), 3, is_boss=False, cycle=1)

    # D1 lvl1: HP = 5 + 2*1 = 7; D3 lvl5: HP = 5 + 2*5 = 15
    assert scaled_d3["hp_base"] > scaled_d1["hp_base"], (
        f"D3 HP ({scaled_d3['hp_base']}) should be > D1 HP ({scaled_d1['hp_base']})"
    )
    assert scaled_d3["attack_bonus"] >= scaled_d1["attack_bonus"]


# ─── T3: Hero level nie wpływa na staty ───────────────────────────────────────

def test_hero_level_does_not_affect_stats():
    """scale_enemy_for_dungeon_tier nie przyjmuje hero_level — tier decyduje."""
    base = {"hp_base": 8, "ac_base": 10, "attack_bonus": 1, "damage_bonus": 0,
            "stats_json": '{"CON": 12}'}
    # Wywołaj dwa razy z tym samym tier — wyniki muszą być w tym samym zakresie tierowym
    # (nie muszą być identyczne bo level losowy, ale oboje muszą być >= base + CON_mod * D3_min)
    d3_min_level = dts.TIER_ENEMY_LEVELS[3][0]  # 5
    con_mod = max(0, (12 - 10) // 2)  # 1

    for _ in range(5):
        scaled = dts.scale_enemy_for_dungeon_tier(dict(base), 3, is_boss=False, cycle=1)
        min_expected_hp = 8 + con_mod * d3_min_level
        assert scaled["hp_base"] >= min_expected_hp, (
            f"HP {scaled['hp_base']} < min expected {min_expected_hp} for D3"
        )
    # Brak parametru hero_level w sygnaturze — sprawdź że nie ma
    import inspect
    sig = inspect.signature(dts.scale_enemy_for_dungeon_tier)
    assert "hero_level" not in sig.parameters, "hero_level should NOT be a parameter"


# ─── T4: Endless level cap ────────────────────────────────────────────────────

def test_endless_level_cap_at_10():
    """Endless cycle=6 z D1 (base lvl 1–2) nie przekracza poziomu 10."""
    base = {"hp_base": 5, "ac_base": 8, "attack_bonus": 0, "damage_bonus": 0,
            "stats_json": '{"CON": 10}'}
    # D1 boss level = 3, + 5 cykli = 8 (≤10); żaden test nie ma % bonusu
    scaled = dts.scale_enemy_for_dungeon_tier(dict(base), 1, is_boss=True, cycle=6)
    # Boss D1 = 3, +5 cycles = capped at min(8, 10) = 8
    # L18 (#729): boss base softened by BOSS_TIER_FACTOR[1]=0.45 → base_hp round(5*.45)=2.
    # HP = 2 + 0*8 = 2 (CON=10 → CON_mod=0); no % bonus
    # Attack = round(0*.45) + 8//2 = 4
    assert scaled["attack_bonus"] == 4, f"Expected attack 4, got {scaled['attack_bonus']}"
    assert scaled["hp_base"] == 2, f"Expected hp 2, got {scaled['hp_base']}"


# ─── L18 (#729): tier-relative boss softening ─────────────────────────────────

def test_boss_softened_at_d1_not_at_d5():
    """A strong boss (lich-like) is a weakened echo at D1, full power at D5."""
    lich = {"hp_base": 90, "ac_base": 17, "attack_bonus": 9, "damage_bonus": 2,
            "damage_die": "2d8", "stats_json": '{"CON": 10}'}
    d1 = dts.scale_enemy_for_dungeon_tier(dict(lich), 1, is_boss=True, cycle=1)
    d5 = dts.scale_enemy_for_dungeon_tier(dict(lich), 5, is_boss=True, cycle=1)
    # D1: 90 HP → no longer a 90-HP wall vs a 12-HP hero
    assert d1["hp_base"] < 50, f"D1 boss HP {d1['hp_base']} still too high"
    assert d1["ac_base"] < 17, f"D1 boss AC {d1['ac_base']} not softened"
    assert d1["damage_die"] == "1d8+0" or d1["damage_die"].startswith("1d8"), d1["damage_die"]
    # D5: full power preserved (factor 1.0)
    assert d5["hp_base"] == 90 and d5["ac_base"] == 17 and d5["damage_die"] == "2d8"
    # Monotonic: D1 < D5 across HP/AC/attack
    assert d1["hp_base"] < d5["hp_base"]
    assert d1["ac_base"] < d5["ac_base"]
    assert d1["attack_bonus"] < d5["attack_bonus"]


def test_regular_enemy_unaffected_by_boss_softening():
    """is_boss=False enemies keep their authored base (no boss factor applied)."""
    e = {"hp_base": 35, "ac_base": 14, "attack_bonus": 7, "damage_bonus": 2,
         "damage_die": "1d6", "stats_json": '{"CON": 10}'}
    d1 = dts.scale_enemy_for_dungeon_tier(dict(e), 1, is_boss=False, cycle=1)
    assert d1["hp_base"] == 35  # base preserved; only level/CON add
    assert d1["damage_die"] == "1d6"


def test_scale_damage_die_floor():
    assert dts._scale_damage_die("2d8", 0.45) == "1d8"
    assert dts._scale_damage_die("2d8+2", 0.45) == "1d8+2"
    assert dts._scale_damage_die("4d6", 0.5) == "2d6"
    assert dts._scale_damage_die("1d6", 0.45) == "1d6"   # floor at 1 die
    assert dts._scale_damage_die("bogus", 0.5) == "bogus"


def test_tile_enemies_allowed_gating():
    weak = {"enemies_json": '[{"enemy_key":"skeleton","count":2}]'}
    elite = {"enemies_json": '[{"enemy_key":"shadow_stalker","count":1}]'}
    empty = {"enemies_json": "[]"}
    pool = {"skeleton", "zombie", "ghoul"}
    assert dts._tile_enemies_allowed(weak, pool) is True
    assert dts._tile_enemies_allowed(elite, pool) is False
    assert dts._tile_enemies_allowed(empty, pool) is True   # enemy-free always drawable


# ─── T5: Endless % bonus above level 10 ───────────────────────────────────────

def test_endless_percent_bonus_above_10():
    """Endless cycle=15 z D5 boss (base=10) → % bonus aktywny, HP > CON*10."""
    base = {"hp_base": 5, "ac_base": 8, "attack_bonus": 0, "damage_bonus": 2,
            "stats_json": '{"CON": 14}'}  # CON_mod = 2
    # D5 boss level = 10; cycle=15 → +14 cycle bumps, 0 head room → 14 overflow cykli
    # HP bez bonusu = 5 + 2*10 = 25; % bonus = 14 * 15% = 210%; HP ≈ round(25 * 3.1) ≈ 77
    scaled = dts.scale_enemy_for_dungeon_tier(dict(base), 5, is_boss=True, cycle=15)
    base_hp_at_lvl10 = 5 + 2 * 10  # 25
    assert scaled["hp_base"] > base_hp_at_lvl10, (
        f"HP {scaled['hp_base']} should be > {base_hp_at_lvl10} with % bonus"
    )


# ─── T6: resolve_tile_content używa dungeon_tier ──────────────────────────────

def test_resolve_tile_content_uses_tier(db, monkeypatch):
    """resolve_tile_content z dungeon_tier=3 daje wyższe HP niż z dungeon_tier=1."""
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "INSERT INTO game_config_enemies (key, label, hp_base, stats_json) "
        "VALUES ('skeleton','Szkielet',5,'{\"CON\":14}')"  # CON_mod=2 → widoczne skalowanie
    )
    tile_id = conn.execute(
        "INSERT INTO dungeon_tiles (category_key, label, enemies_json, doors_json) "
        "VALUES ('krypta','Test','[{\"enemy_key\":\"skeleton\",\"count\":1}]','[\"N\",\"S\"]')"
    ).lastrowid
    conn.commit()
    conn.close()

    monkeypatch.setattr(dts, "_get_db", lambda: (lambda c: (setattr(c, 'row_factory', sqlite3.Row), c)[1])(sqlite3.connect(db)))

    with patch("app.services.dungeon_tile_service.random") as mock_rnd:
        mock_rnd.randint.return_value = 1  # D1 → level 1
        mock_rnd.choice = __import__("random").choice
        mock_rnd.sample = __import__("random").sample
        content_d1 = dts.resolve_tile_content(tile_id, dungeon_tier=1, cycle=1)

    with patch("app.services.dungeon_tile_service.random") as mock_rnd:
        mock_rnd.randint.return_value = 5  # D3 → level 5
        mock_rnd.choice = __import__("random").choice
        mock_rnd.sample = __import__("random").sample
        content_d3 = dts.resolve_tile_content(tile_id, dungeon_tier=3, cycle=1)

    hp_d1 = content_d1["enemies"][0]["stats"]["hp_base"]
    hp_d3 = content_d3["enemies"][0]["stats"]["hp_base"]
    assert hp_d3 > hp_d1, f"D3 HP ({hp_d3}) should be > D1 HP ({hp_d1})"


# ─── T7: Re-roll na powtórzonym kafelku ───────────────────────────────────────

def test_reroll_changes_enemies_on_repeated_tile(db):
    """_reroll_repeated_tile_enemies zmienia wrogów na 2+ wystąpieniu tile_id."""
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "INSERT INTO game_config_enemies (key, label, hp_base) VALUES ('goblin','Goblin',5)"
    )
    conn.execute(
        "INSERT INTO game_config_enemies (key, label, hp_base) VALUES ('orc','Ork',10)"
    )
    conn.commit()

    # Graf z powtórzonym tile_id=1
    graph = {
        "entry_node": "n0",
        "nodes": {
            "n0": {"tile_id": 1, "content": {"enemies": [{"enemy_key": "goblin", "count": 1}]}, "doors_open": {"N": "n1"}},
            "n1": {"tile_id": 1, "content": {"enemies": [{"enemy_key": "goblin", "count": 1}]}, "doors_open": {}},
            "n2": {"tile_id": 2, "content": {"enemies": [{"enemy_key": "goblin", "count": 1}]}, "doors_open": {}},
        }
    }
    enemy_pool = ["goblin", "orc"]

    result = dts._reroll_repeated_tile_enemies(graph, enemy_pool, conn)
    conn.close()

    # n0 to pierwsze wystąpienie tile_id=1 → BEZ zmiany
    # n1 to drugie wystąpienie tile_id=1 → POWINNO być zmienione (re-rolled z pool)
    n0_enemies = result["nodes"]["n0"]["content"]["enemies"]
    n1_enemies = result["nodes"]["n1"]["content"]["enemies"]

    # Oba muszą mieć wrogów
    assert len(n0_enemies) > 0
    assert len(n1_enemies) > 0

    # n1 re-rolled z enemy_pool (klucz musi być z pool)
    for e in n1_enemies:
        assert e["enemy_key"] in enemy_pool, f"Re-rolled enemy {e['enemy_key']} not in pool"

    # n2 (tile_id=2, nie powtórzony) → bez zmian
    assert result["nodes"]["n2"]["content"]["enemies"][0]["enemy_key"] == "goblin"


# ─── T8: enter_dungeon_tiles przechowuje dungeon_difficulty ───────────────────

def test_enter_dungeon_stores_difficulty(db, monkeypatch):
    """enter_dungeon_tiles przechowuje dungeon_difficulty=3 w run dict."""
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    # Minimalne dane lochu
    conn.execute("""INSERT INTO game_dungeons
        (key, label, dungeon_difficulty, tile_category_key, tile_count, is_active, cooldown_hours)
        VALUES ('test_loch','Test Loch',3,'krypta',4,1,0)""")
    # Kafelki min. 4 szt. (bez boss) + 1 boss do sequence
    for i in range(5):
        conn.execute(
            "INSERT INTO dungeon_tiles (category_key, label, doors_json, is_boss_tile) "
            f"VALUES ('krypta','Tile {i}','[\"N\",\"S\"]',{1 if i==4 else 0})"
        )
    # Session
    conn.execute("INSERT INTO game_sessions (campaign_id, session_flags) VALUES (1, '{}')")
    conn.commit()

    saved_runs = []

    def mock_load_flags(campaign_id):
        return conn, {}

    def mock_save_flags(c, campaign_id, flags):
        saved_runs.append(flags.get("dungeon_run", {}))

    monkeypatch.setattr(dts, "_get_db", lambda: conn)
    monkeypatch.setattr(dts, "_load_flags", mock_load_flags)
    monkeypatch.setattr(dts, "_save_flags", mock_save_flags)
    monkeypatch.setattr(dts, "check_cooldown", lambda *a, **kw: {"on_cooldown": False})
    monkeypatch.setattr(dts, "get_dungeon", lambda key: {
        "key": "test_loch",
        "label": "Test Loch",
        "dungeon_difficulty": 3,
        "tile_category_key": "krypta",
        "tile_count": 4,
        "boss_tile_id": None,
        "cooldown_hours": 0,
        "endless_growth_n": 0,
        "enemy_pool": "[]",
    })

    dts.enter_dungeon_tiles(
        campaign_id=1,
        character_id=42,
        dungeon_key="test_loch",
        hero_level=5,
    )

    assert saved_runs, "enter_dungeon_tiles should save a run"
    run = saved_runs[-1]
    assert run.get("dungeon_difficulty") == 3, (
        f"Expected dungeon_difficulty=3, got {run.get('dungeon_difficulty')}"
    )


# ─── L18 (#729 follow-up): dungeon-only victory sustain drop ───────────────────

def _dungeon_run(is_boss=False, tier=1):
    return {
        "system": "tiles_v2",
        "dungeon_difficulty": tier,
        "positions": {"7": "node_1"},
        "graph": {"nodes": {"node_1": {"is_boss": is_boss,
                                       "content": {"is_boss_tile": is_boss}}}},
    }


def _sustain_db(tmp_path, run):
    """Temp-file DB with game_sessions + consumables; returns (db_file, grants list).

    `grant_dungeon_victory_sustain` opens its own _get_db() connection and grants via
    loot_service.grant_loot_to_character — both are monkeypatched by the caller.
    """
    db_file = str(tmp_path / "sustain.db")
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE game_sessions (campaign_id INTEGER, session_flags TEXT)")
    conn.execute(
        "CREATE TABLE game_config_consumables (key TEXT PRIMARY KEY, label TEXT, "
        "effect_type TEXT, is_active INTEGER DEFAULT 1, rarity INTEGER DEFAULT 1)"
    )
    for k, lbl in [
        ("potion_healing_minor", "Mała mikstura leczenia"),
        ("bandage", "Bandaż"), ("healing_herb", "Lecznicze zioła"),
        ("potion_healing_standard", "Mikstura leczenia"),
        ("potion_healing_major", "Wielka mikstura leczenia"),
    ]:
        conn.execute(
            "INSERT INTO game_config_consumables (key,label,effect_type) VALUES (?,?,'heal_hp')",
            (k, lbl),
        )
    conn.execute(
        "INSERT INTO game_sessions (campaign_id, session_flags) VALUES (1, ?)",
        (json.dumps({"dungeon_run": run}) if run else "{}",),
    )
    conn.commit(); conn.close()
    return db_file


def _patch(monkeypatch, db_file):
    """Point dts._get_db at the temp DB and capture grant_loot_to_character calls."""
    def _gdb():
        c = sqlite3.connect(db_file); c.row_factory = sqlite3.Row; return c
    monkeypatch.setattr(dts, "_get_db", _gdb)
    grants = []
    import app.services.loot_service as ls
    monkeypatch.setattr(ls, "grant_loot_to_character",
                        lambda cid, items, **kw: grants.append((cid, items, kw)) or [])
    return grants


def test_sustain_drop_dungeon_only(monkeypatch, tmp_path):
    """No dungeon_run → never grants (world combat must not get dungeon sustain)."""
    grants = _patch(monkeypatch, _sustain_db(tmp_path, None))
    monkeypatch.setattr(dts.random, "random", lambda: 0.0)  # would always pass the chance
    assert dts.grant_dungeon_victory_sustain(1, 7) is None
    assert grants == []


def test_sustain_drop_on_victory(monkeypatch, tmp_path):
    """Active tiles_v2 run, non-boss tile, chance hit → grants a healing consumable."""
    grants = _patch(monkeypatch, _sustain_db(tmp_path, _dungeon_run(is_boss=False, tier=1)))
    monkeypatch.setattr(dts.random, "random", lambda: 0.0)
    drop = dts.grant_dungeon_victory_sustain(1, 7)
    assert drop is not None
    assert drop["key"] in {"potion_healing_minor", "bandage", "healing_herb"}
    assert drop["quantity"] == 1
    # granted as a CONSUMABLE (not item_key) to the right character
    assert len(grants) == 1
    cid, items, kw = grants[0]
    assert cid == 7 and items[0]["consumable_key"] == drop["key"]


def test_sustain_drop_skips_boss_tile(monkeypatch, tmp_path):
    """Boss tiles already grant boss loot → no sustain drop there."""
    grants = _patch(monkeypatch, _sustain_db(tmp_path, _dungeon_run(is_boss=True, tier=1)))
    monkeypatch.setattr(dts.random, "random", lambda: 0.0)
    assert dts.grant_dungeon_victory_sustain(1, 7) is None
    assert grants == []


def test_sustain_drop_respects_chance(monkeypatch, tmp_path):
    """Chance miss → None, no grant (drop is probabilistic, not guaranteed)."""
    grants = _patch(monkeypatch, _sustain_db(tmp_path, _dungeon_run(is_boss=False, tier=1)))
    monkeypatch.setattr(dts.random, "random", lambda: 0.99)  # above any tier chance
    assert dts.grant_dungeon_victory_sustain(1, 7) is None
    assert grants == []
