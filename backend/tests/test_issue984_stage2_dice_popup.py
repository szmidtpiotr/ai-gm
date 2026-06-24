"""TDD: Issue #984 — Stage 2 damage dice popup brak po trafieniu.

Backend contract: resolve_attack na trafienie MUSI zwrócić damage_die i damage>=1
żeby buildDamageStage(data) w combat_ui.js NIE zwróciło null → Stage 2 się wyświetla.

Na zabójczym ciosie (enemy_dead=True) odpowiedź NADAL niesie damage_die.
To serce rasy #984: combat.status='ended' pojawia się w tej samej odpowiedzi
co damage_die — frontend musi pokazać Stage 2 ZANIM wykryje koniec walki z polla.
"""
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _fixtures_schema as fx
import pytest

if "httpx" not in sys.modules:
    sys.modules["httpx"] = MagicMock()

from app.services import combat_service as cs


# ── Minimal test DB ──────────────────────────────────────────────────────────

def _build_db(db_path: str) -> None:
    sheet = json.dumps({
        "archetype": "warrior",
        "level": 1,
        "stats": {"STR": 14, "DEX": 10, "CON": 12, "INT": 8, "WIS": 8, "CHA": 8, "LCK": 8},
        "current_hp": 10, "max_hp": 10,
        "skills": {},
        "equipped_weapon": "shortsword",
        "conditions": [],
    }, ensure_ascii=False).replace("'", "''")

    conn = sqlite3.connect(db_path)
    conn.executescript(f"""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, display_name TEXT
        );
        INSERT INTO users (id, username, password_hash, display_name) VALUES (1,'test','x','Test');

        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY, title TEXT, system_id TEXT, model_id TEXT,
            owner_user_id INTEGER, language TEXT DEFAULT 'pl', mode TEXT DEFAULT 'solo',
            status TEXT DEFAULT 'active'
        );
        INSERT INTO campaigns (id,title,system_id,model_id,owner_user_id) VALUES (1,'Test #984','fantasy','m',1);

        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER, name TEXT,
            system_id TEXT, sheet_json TEXT
        );
        INSERT INTO characters (id,campaign_id,user_id,name,system_id,sheet_json)
            VALUES (1,1,1,'[TEST] Wojownik984','fantasy','{sheet}');

        {fx.table_sql("game_config_weapons")}
        INSERT INTO game_config_weapons (key,label,damage_die,linked_stat,allowed_classes,weapon_type)
            VALUES ('shortsword','Krótki miecz','1d6','STR','warrior','melee');

        {fx.table_sql("game_config_enemies")}
        INSERT INTO game_config_enemies (key,label,hp_base,ac_base,attack_bonus,dex_modifier,damage_die,drop_chance)
            VALUES ('slime_984','Szlam',1,10,0,0,'1d3',0.0);

        CREATE TABLE IF NOT EXISTS active_combat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL UNIQUE,
            character_id INTEGER NOT NULL,
            round INTEGER NOT NULL DEFAULT 1,
            turn_order TEXT NOT NULL,
            current_turn TEXT NOT NULL,
            combatants TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            ended_reason TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            location_tag TEXT DEFAULT NULL,
            loot_pool TEXT DEFAULT NULL,
            boss_defeated INTEGER NOT NULL DEFAULT 0,
            ammo_spent_json TEXT DEFAULT NULL,
            combat_turn_deadline TEXT DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS combat_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            combat_id INTEGER, campaign_id INTEGER,
            turn_number REAL, actor TEXT, event_type TEXT,
            roll_value INTEGER, damage INTEGER, hp_after INTEGER,
            target_id TEXT, target_name TEXT, hit INTEGER, narrative TEXT,
            created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
        );

        CREATE TABLE IF NOT EXISTS game_sessions (
            id INTEGER PRIMARY KEY, campaign_id INTEGER UNIQUE, session_flags TEXT DEFAULT '{{}}'
        );
        INSERT OR IGNORE INTO game_sessions (campaign_id, session_flags) VALUES (1,'{{}}');

        CREATE TABLE IF NOT EXISTS character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER, item_key TEXT, item_type TEXT DEFAULT 'weapon',
            qty INTEGER DEFAULT 1, equipped INTEGER DEFAULT 0, slot TEXT, affix_json TEXT
        );
        INSERT INTO character_inventory (character_id, item_key, item_type, qty, equipped, slot)
            VALUES (1,'shortsword','weapon',1,1,'main_hand');
    """)
    conn.commit()
    conn.close()


@pytest.fixture()
def _db984(tmp_path):
    db = str(tmp_path / "test_984.db")
    _build_db(db)
    with patch.object(cs, "COMBAT_DB_PATH", db):
        yield db


# ─── Testy główne ─────────────────────────────────────────────────────────────

def test_resolve_attack_hit_returns_damage_die_for_stage2(_db984):
    """resolve_attack na trafienie MUSI zwrócić damage_die i damage>=1.

    Stage 2 popup (buildDamageStage) zwraca null gdy brakuje damage_die lub damage<=0.
    Blokujemy tę regresję — hit musi zawsze nieść damage_die + obrażenia >= 1.
    """
    state = cs.initiate_combat(1, 1, ["slime_984"])
    assert state["status"] == "active"

    # nat20 = auto-sukces, ignoruje pancerz → pewne obrażenia >= 1
    result = cs.resolve_attack(1, roll_result=20, attacker="player", raw_d20=20)

    assert result.get("hit") is True, f"nat20 musi trafić; got: {result}"
    assert result.get("damage_die"), (
        "resolve_attack na trafienie musi zwrócić damage_die "
        "(buildDamageStage w combat_ui.js zwraca null gdy brakuje) — "
        f"got: {result}"
    )
    assert result.get("damage", 0) >= 1, (
        "Trafienie musi zadać min 1 obrażeń (apply_defense_model gwarantuje min=1). "
        f"got: damage={result.get('damage')}"
    )


def test_resolve_attack_killing_blow_still_has_damage_die(_db984):
    """Na zabójczym ciosie (enemy_dead=True) damage_die NADAL musi być w odpowiedzi.

    Serce rasy #984: po nat20 na wrogu z 1HP, combat_state.status='ended'
    pojawia się w tej samej odpowiedzi co damage_die.
    Frontend (combat_ui.js) musi pokazać Stage 2 (kości obrażeń) ZANIM
    pollCombatState wykryje status='ended' i wywoła handleCombatEnded.
    Jeśli damage_die zniknie na enemy_dead=True — Stage 2 nigdy się nie pojawi.
    """
    state = cs.initiate_combat(1, 1, ["slime_984"])
    assert state["status"] == "active"

    result = cs.resolve_attack(1, roll_result=20, attacker="player", raw_d20=20)

    # Szlam ma 1HP — nat20 musi go zabić
    assert result.get("enemy_dead") is True, (
        "slime_984 ma hp_base=1 — nat20 musi zabić; "
        f"enemy_dead={result.get('enemy_dead')}, damage={result.get('damage')}"
    )

    # Na zabójczym ciosie damage_die musi być dostępne dla Stage 2
    assert result.get("damage_die"), (
        "Na zabójczym ciosie (enemy_dead=True) damage_die musi być w odpowiedzi — "
        "frontend potrzebuje go do Stage 2 popup ZANIM zobaczy status='ended'. "
        f"got: {result}"
    )
    assert result.get("damage", 0) >= 1, (
        f"Zabójczy cios musi zadać >= 1 obrażeń. got: {result.get('damage')}"
    )

    # Walka zakończona po zabiciu ostatniego wroga
    cs_snap = result.get("combat_state", {})
    if cs_snap:
        assert cs_snap.get("status") == "ended", (
            f"Po zabiciu ostatniego wroga combat_state.status='ended'. "
            f"got: {cs_snap.get('status')}"
        )


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_resolve_attack_miss_no_damage_on_nat1(_db984):
    """Na pudłach (nat1) Stage 2 słusznie się nie pokazuje — hit=False."""
    state = cs.initiate_combat(1, 1, ["slime_984"])
    assert state["status"] == "active"

    result = cs.resolve_attack(1, roll_result=1, attacker="player", raw_d20=1)

    # nat1 = auto-porażka
    assert result.get("hit") is not True, (
        f"nat1 = auto-porażka; got hit={result.get('hit')}"
    )
