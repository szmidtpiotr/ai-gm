"""BL-A6 (#1332) — rangi wariantów wroga (normal/weteran/elitarny).

Deterministyczne mnożniki nakładane W MOMENCIE SPAWNU na combatant JSON — rekord
w game_config_enemies NIETKNIĘTY. Testy sprawdzają: mnożniki HP/atk/dmg/XP/drop,
prefiks nazwy, flagę `rank` (save/load), flat damage_bonus w silniku ataku wroga,
oraz wybór rangi w composerze gdy budżet przewyższa najmocniejszego wroga puli.
"""
import sqlite3

import pytest

from app.services import combat_service as cs
from app.services import encounter_service as es


def _base_enemy_combatant():
    return {
        "id": "bandit_01",
        "type": "enemy",
        "enemy_key": "bandit",
        "name": "Bandyta",
        "hp_current": 100,
        "hp_max": 100,
        "defense": 12,
        "attack_bonus": 3,
        "xp_award": 100,
        "drop_chance": 0.5,
        "tier": "standard",
    }


# ── apply_enemy_rank: mnożniki ────────────────────────────────────────────────

def test_weteran_multipliers():
    c = _base_enemy_combatant()
    cs.apply_enemy_rank(c, "weteran")
    assert c["hp_max"] == 130 and c["hp_current"] == 130      # ×1.3
    assert c["attack_bonus"] == 3 + 1                          # +1
    assert "damage_bonus" not in c or c["damage_bonus"] == 0   # weteran bez +dmg
    assert c["xp_award"] == 130                                # ×1.3
    assert c["drop_chance"] == 0.5                             # ×1.0
    assert c["rank"] == "weteran"
    assert c["name"] == "Weteran: Bandyta"


def test_elitarny_multipliers():
    c = _base_enemy_combatant()
    cs.apply_enemy_rank(c, "elitarny")
    assert c["hp_max"] == 160 and c["hp_current"] == 160       # ×1.6
    assert c["attack_bonus"] == 3 + 2                          # +2
    assert c["damage_bonus"] == 1                              # elita +1 dmg
    assert c["xp_award"] == 160                                # ×1.6
    assert c["drop_chance"] == 0.75                            # 0.5 ×1.5
    assert c["rank"] == "elitarny"
    assert c["name"] == "Elitarny: Bandyta"


def test_drop_chance_capped_at_one():
    c = _base_enemy_combatant()
    c["drop_chance"] = 0.8
    cs.apply_enemy_rank(c, "elitarny")
    assert c["drop_chance"] == 1.0    # 0.8 ×1.5 = 1.2 → cap 1.0


def test_normal_and_none_untouched():
    for rank in (None, "", "normal", "boss"):
        c = _base_enemy_combatant()
        cs.apply_enemy_rank(c, rank)
        assert c["hp_max"] == 100
        assert c["attack_bonus"] == 3
        assert "rank" not in c
        assert c["name"] == "Bandyta"


def test_idempotent_no_double_multiply():
    c = _base_enemy_combatant()
    cs.apply_enemy_rank(c, "elitarny")
    snap = dict(c)
    cs.apply_enemy_rank(c, "elitarny")   # ponowne wywołanie — bez zmian
    assert c == snap


def test_base_record_untouched():
    """apply_enemy_rank działa na kopii combatanta, nie na rekordzie bazowym."""
    base = _base_enemy_combatant()
    c = dict(base)
    cs.apply_enemy_rank(c, "elitarny")
    assert base["hp_max"] == 100 and base["attack_bonus"] == 3 and base["xp_award"] == 100


# ── flat damage_bonus czytany przez silnik ataku wroga ────────────────────────

def test_flat_damage_bonus_read_for_enemy():
    c = _base_enemy_combatant()
    cs.apply_enemy_rank(c, "elitarny")   # ustawia damage_bonus = 1
    mod = cs._combatant_stat_modifier(c, sheet=None, stat="damage_bonus")
    assert mod == 1


def test_flat_damage_bonus_absent_for_normal():
    c = _base_enemy_combatant()
    assert cs._combatant_stat_modifier(c, sheet=None, stat="damage_bonus") == 0


# ── mnożniki z game_config_meta (override) ────────────────────────────────────

def _meta_conn(value_json=None):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE game_config_meta (key TEXT PRIMARY KEY, value TEXT)")
    if value_json is not None:
        conn.execute(
            "INSERT INTO game_config_meta (key, value) VALUES ('enemy_rank_multipliers', ?)",
            (value_json,),
        )
    conn.commit()
    return conn


def test_multipliers_default_when_no_meta():
    conn = _meta_conn()
    m = cs.get_enemy_rank_multipliers(conn)
    assert m["weteran"]["hp"] == 1.3
    assert m["elitarny"]["hp"] == 1.6


def test_multipliers_override_from_meta():
    conn = _meta_conn('{"elitarny": {"hp": 2.0}}')
    m = cs.get_enemy_rank_multipliers(conn)
    assert m["elitarny"]["hp"] == 2.0          # nadpisane
    assert m["elitarny"]["attack_bonus"] == 2  # reszta z domyślnych


def test_apply_with_meta_override():
    conn = _meta_conn('{"elitarny": {"hp": 2.0}}')
    c = _base_enemy_combatant()
    cs.apply_enemy_rank(c, "elitarny", cs.get_enemy_rank_multipliers(conn))
    assert c["hp_max"] == 200   # 100 × 2.0


# ── composer: ranga gdy budżet przewyższa najmocniejszego wroga puli ──────────

def test_rank_for_budget_thresholds():
    conn = _meta_conn()
    # threat najmocniejszego = 20
    assert es._rank_for_budget(conn, 20, 20, is_pool_top=True) is None    # 1.0×
    assert es._rank_for_budget(conn, 30, 20, is_pool_top=True) == "weteran"   # 1.5×
    assert es._rank_for_budget(conn, 45, 20, is_pool_top=True) == "elitarny"  # 2.25×
    # nie najmocniejszy → brak rangi (composer wziąłby silniejszego wroga)
    assert es._rank_for_budget(conn, 45, 20, is_pool_top=False) is None


def test_compose_solo_assigns_rank_when_overbudget():
    conn = _meta_conn()
    pool = [{"key": "bandit", "label": "Bandyta", "tier": "standard", "threat": 20.0}]
    # budżet 50 >> 20 → elitarny (2.5×)
    # #1369: sygnatura _compose_enemies zmieniona na penalty_map (dict key→mnożnik).
    pattern, enemies = es._compose_enemies(conn, pool, 50.0, __import__("random"), {})
    assert pattern in ("solo", "wataha", "herszt")
    if pattern == "solo":
        assert enemies[0].get("rank") == "elitarny"


def test_enc_enemy_carries_rank():
    d = {"key": "bandit", "label": "Bandyta", "tier": "standard"}
    e = es._enc_enemy(d, 1, "weteran")
    assert e["rank"] == "weteran"
    e2 = es._enc_enemy(d, 1)
    assert "rank" not in e2
