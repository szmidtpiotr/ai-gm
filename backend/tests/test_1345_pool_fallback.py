"""#1345 — eligible_enemy_pool band-widening fallback (SMOKE-A P1 gate fix).

Gdy pula wrogów jest za mała dla poziomu bohatera (dziura pasm — np. lvl 10 = same
bossy z terenem), composer dostawał pustą / jednotierową pulę → spotkania
niewygrywalne lub brak spotkania. Fallback poszerza pasmo poziomów (±delta) trzymając
scope='global'+permanent i teren; teren luzowany dopiero w ostateczności.
"""
import sqlite3

import pytest

from app.services.encounter_service import eligible_enemy_pool


def _mkconn(min_size=2, max_delta=4):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE game_config_enemies (
            key TEXT, label TEXT, hp_base INT, ac_base INT, attack_bonus INT,
            damage_die TEXT, damage_bonus INT, attacks_per_turn INT, tier TEXT,
            min_level INT, max_level INT, terrain_tags TEXT,
            world_scope TEXT, review_status TEXT, is_active INT)"""
    )
    conn.execute("CREATE TABLE game_config_meta (key TEXT, value TEXT)")
    conn.executemany(
        "INSERT INTO game_config_meta(key,value) VALUES (?,?)",
        [("encounter_pool_min_size", str(min_size)),
         ("encounter_pool_widen_max_delta", str(max_delta))],
    )

    def add(key, tier, mn, mx, terr, scope="global", status="permanent", active=1):
        conn.execute(
            "INSERT INTO game_config_enemies VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (key, key, 30, 13, 3, "1d6", 1, 1, tier, mn, mx, terr, scope, status, active),
        )

    add("std_forest", "standard", 1, 5, "forest")
    add("elite_forest", "elite", 6, 9, "forest")           # tylko po poszerzeniu pasma dla lvl10
    add("boss_forest", "boss", 10, None, "forest,ruins")
    add("boss_mountain", "boss", 10, None, "mountain")       # inny teren — nie w forest
    add("tmpl_forest", "boss", 10, None, "forest", scope="template")            # scope leak
    add("camp_forest", "boss", 10, None, "forest", scope="campaign", status="pending_review")  # scope leak
    conn.commit()
    return conn


def test_naive_band_is_empty_documents_the_bug():
    """Dowód pierwotnej wady: lvl10/forest ma w wąskim paśmie tylko bossa forest."""
    conn = _mkconn()
    # naiwne zapytanie [10,10] + forest byłoby ubogie — fallback ma to naprawić.
    pool = eligible_enemy_pool(conn, level=10, hex_type="forest")
    assert pool, "pool nie może być pusty na lvl10/forest po fallbacku"


def test_widen_pulls_elite_and_is_multitier():
    conn = _mkconn()
    pool = eligible_enemy_pool(conn, level=10, hex_type="forest")
    keys = {d["key"] for d in pool}
    tiers = {d["tier"] for d in pool}
    assert "elite_forest" in keys, "poszerzenie pasma powinno dociągnąć elitę lvl6-9"
    assert len(tiers) >= 2, f"pula powinna być wielotierowa, jest: {tiers}"


def test_terrain_respected_when_pool_sufficient():
    conn = _mkconn()
    pool = eligible_enemy_pool(conn, level=10, hex_type="forest")
    keys = {d["key"] for d in pool}
    assert "boss_mountain" not in keys, "wróg z innym terenem nie może wejść, gdy pula wystarcza"


def test_scope_purity_never_leaks_template_or_campaign():
    conn = _mkconn()
    for lvl in (1, 5, 10):
        pool = eligible_enemy_pool(conn, level=lvl, hex_type="forest")
        keys = {d["key"] for d in pool}
        assert "tmpl_forest" not in keys, "template nigdy nie może wejść do puli"
        assert "camp_forest" not in keys, "campaign/pending nigdy nie może wejść do puli"


def test_low_level_does_not_leak_bosses_upward():
    conn = _mkconn()
    pool = eligible_enemy_pool(conn, level=1, hex_type="forest")
    tiers = {d["tier"] for d in pool}
    assert "boss" not in tiers, f"lvl1 nie może dostać bossów, tiers={tiers}"


def test_threat_is_computed_on_every_row():
    conn = _mkconn()
    pool = eligible_enemy_pool(conn, level=10, hex_type="forest")
    assert all("threat" in d and d["threat"] > 0 for d in pool)


def test_terrain_relax_last_resort_when_no_terrain_match():
    """Gdy żaden wróg w paśmie nie pasuje do terenu — luzuj teren zamiast pustki."""
    conn = _mkconn(min_size=5)
    # 'swamp' nie występuje w żadnym terrain_tags → bez luzowania byłaby pustka.
    pool = eligible_enemy_pool(conn, level=10, hex_type="swamp")
    assert pool, "terrain-relax powinien zwrócić niepustą pulę zamiast pustki"


def test_healthy_pool_unchanged_no_widening():
    """Gdy pula już wystarczy przy delta=0, zachowanie bez zmian (brak poszerzenia)."""
    conn = _mkconn(min_size=1)
    pool = eligible_enemy_pool(conn, level=3, hex_type="forest")
    keys = {d["key"] for d in pool}
    assert keys == {"std_forest"}, f"lvl3/forest przy min_size=1 = tylko standard, jest {keys}"
