"""TDD: Issue #824 — LB5 Scale enemy count by party size (not strength)."""
import sqlite3
import sys

import pytest

sys.path.insert(0, "/app")


# ─── _scale_enemy_counts ─────────────────────────────────────────────────────

def test_scale_solo_no_change():
    """solo (party_size=1) = identical count — backward compat."""
    from app.services.encounter_service import _scale_enemy_counts

    enemies = [{"enemy_key": "goblin", "count": 2}]
    result = _scale_enemy_counts(enemies, 1)
    assert result[0]["count"] == 2


def test_scale_duo():
    """duo: count doubles (1*2=2), within cap (1+4=5)."""
    from app.services.encounter_service import _scale_enemy_counts

    enemies = [{"enemy_key": "goblin", "count": 1}]
    result = _scale_enemy_counts(enemies, 2)
    assert result[0]["count"] == 2


def test_scale_cap_enforced():
    """party_size=20 capped at base + MP_ENEMY_COUNT_CAP (=4)."""
    from app.services.encounter_service import _scale_enemy_counts

    enemies = [{"enemy_key": "goblin", "count": 1}]
    result = _scale_enemy_counts(enemies, 20)
    assert result[0]["count"] == 5  # 1 + 4 cap


def test_scale_tier_key_unchanged():
    """enemy_key/tier/extra fields must not change — only count scaled."""
    from app.services.encounter_service import _scale_enemy_counts

    enemies = [{"enemy_key": "elite_wolf", "count": 1, "notes": "boss"}]
    result = _scale_enemy_counts(enemies, 3)
    r = result[0]
    assert r["enemy_key"] == "elite_wolf"
    assert r.get("notes") == "boss"
    # count should have scaled (3×1=3, within cap 1+4=5)
    assert r["count"] == 3


def test_scale_empty_list():
    from app.services.encounter_service import _scale_enemy_counts

    assert _scale_enemy_counts([], 3) == []


def test_scale_multiple_types_all_scaled():
    """Each enemy type scaled independently."""
    from app.services.encounter_service import _scale_enemy_counts

    enemies = [
        {"enemy_key": "goblin", "count": 1},
        {"enemy_key": "orc", "count": 2},
    ]
    result = _scale_enemy_counts(enemies, 2)
    assert result[0]["count"] == 2  # 1*2=2
    assert result[1]["count"] == 4  # 2*2=4


def test_scale_quad_with_cap():
    """party_size=4: count=2, 2*4=8 → capped at 2+4=6."""
    from app.services.encounter_service import _scale_enemy_counts

    enemies = [{"enemy_key": "goblin", "count": 2}]
    result = _scale_enemy_counts(enemies, 4)
    assert result[0]["count"] == 6


# ─── _party_size_for_campaign ─────────────────────────────────────────────────

def _mem_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE campaign_members (
            id INTEGER PRIMARY KEY, campaign_id INTEGER,
            user_id INTEGER, status TEXT, character_id INTEGER
        )
    """)
    conn.commit()
    return conn


def test_party_size_empty_returns_1():
    """No members → solo fallback (1)."""
    from app.services.encounter_service import _party_size_for_campaign

    conn = _mem_conn()
    assert _party_size_for_campaign(conn, 999) == 1
    conn.close()


def test_party_size_duo():
    """Two accepted members with assigned heroes = 2."""
    from app.services.encounter_service import _party_size_for_campaign

    conn = _mem_conn()
    conn.execute("INSERT INTO campaign_members VALUES (1,1,10,'accepted',42)")
    conn.execute("INSERT INTO campaign_members VALUES (2,1,11,'accepted',43)")
    conn.commit()
    assert _party_size_for_campaign(conn, 1) == 2
    conn.close()


def test_party_size_invited_not_counted():
    """invited member (no character) not counted in party."""
    from app.services.encounter_service import _party_size_for_campaign

    conn = _mem_conn()
    conn.execute("INSERT INTO campaign_members VALUES (1,1,10,'accepted',42)")
    conn.execute("INSERT INTO campaign_members VALUES (2,1,11,'invited',NULL)")
    conn.commit()
    assert _party_size_for_campaign(conn, 1) == 1
    conn.close()


def test_party_size_accepted_no_hero_not_counted():
    """Accepted but character_id IS NULL → not counted (hero not chosen yet)."""
    from app.services.encounter_service import _party_size_for_campaign

    conn = _mem_conn()
    conn.execute("INSERT INTO campaign_members VALUES (1,1,10,'accepted',42)")
    conn.execute("INSERT INTO campaign_members VALUES (2,1,11,'accepted',NULL)")
    conn.commit()
    assert _party_size_for_campaign(conn, 1) == 1
    conn.close()


def test_party_size_quad():
    """Four accepted members = 4."""
    from app.services.encounter_service import _party_size_for_campaign

    conn = _mem_conn()
    for i in range(4):
        conn.execute(f"INSERT INTO campaign_members VALUES ({i},1,{10+i},'accepted',{40+i})")
    conn.commit()
    assert _party_size_for_campaign(conn, 1) == 4
    conn.close()
