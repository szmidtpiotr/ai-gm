"""TDD: Issue #1376 — spójny power-curve wrogów (bez inwersji tierów) + loot.

Follow-up balansowy do #1346. BRAMKA DANYCH kodująca kryteria akceptacji:

  1. Brak inwersji elite/standard: max(threat standardów) < min(threat elit).
  2. Brak inwersji boss/elite: max(threat elit) < min(threat bossów).
  3. loot_tier nie zaśmiecony: każdy ∈ {NULL, '', weak, standard, elite, boss}.
  4. Żaden wróg nie dropi 0 zł: per-enemy gold_max > 0 (złoto leci TYLKO z tabeli
     per-wróg, nie z tierowej — patrz loot_service._roll_gold).
  5. Każdy wróg rezolwuje aktywną tabelę tierową (feed komponentów craftingu #1333/4).

Jedzie na współdzielonej `/data/ai_gm.db` (read-only), używa prawdziwych funkcji
z encounter_service/loot_service. Failuje dopóki balans nie jest dostrojony."""
import os
import sqlite3

import pytest

from app.services.encounter_service import enemy_threat_value
from app.services.loot_service import _resolve_tier_table_key

DB_PATH = os.environ.get("AI_GM_DB_PATH", "/data/ai_gm.db")
VALID_LOOT_TIER = {None, "", "weak", "standard", "elite", "boss"}


@pytest.fixture()
def conn():
    c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    try:
        yield c
    finally:
        c.close()


def _enemies(conn):
    return conn.execute(
        """SELECT * FROM game_config_enemies
           WHERE world_scope='global' AND review_status='permanent' AND is_active=1"""
    ).fetchall()


def _threats_by_tier(conn):
    out = {"weak": [], "standard": [], "elite": [], "boss": []}
    for r in _enemies(conn):
        t = r["tier"]
        if t in out:
            out[t].append((r["key"], enemy_threat_value(dict(r))))
    return out


# ─── Test 1 — brak inwersji elite/standard ───────────────────────────────────

def test_no_elite_below_standard(conn):
    bt = _threats_by_tier(conn)
    max_std = max(bt["standard"], key=lambda x: x[1])
    min_elite = min(bt["elite"], key=lambda x: x[1])
    assert min_elite[1] > max_std[1], (
        f"INWERSJA: elita {min_elite[0]}={min_elite[1]} <= standard "
        f"{max_std[0]}={max_std[1]} — 'elita' słabsza od 'zwykłego'"
    )


# ─── Test 2 — brak inwersji boss/elite ───────────────────────────────────────

def test_no_boss_below_elite(conn):
    bt = _threats_by_tier(conn)
    max_elite = max(bt["elite"], key=lambda x: x[1])
    min_boss = min(bt["boss"], key=lambda x: x[1])
    assert min_boss[1] > max_elite[1], (
        f"INWERSJA: boss {min_boss[0]}={min_boss[1]} <= elita "
        f"{max_elite[0]}={max_elite[1]}"
    )


# ─── Test 3 — loot_tier bez zaśmiecenia ──────────────────────────────────────

def test_loot_tier_not_polluted(conn):
    bad = [
        (r["key"], r["loot_tier"]) for r in _enemies(conn)
        if r["loot_tier"] not in VALID_LOOT_TIER
    ]
    assert not bad, f"loot_tier zaśmiecony (słowa lochowe) na {len(bad)}: {bad[:8]}"


# ─── Test 4 — żaden wróg nie dropi 0 zł ───────────────────────────────────────

def test_no_zero_gold_enemy(conn):
    zero = []
    for r in _enemies(conn):
        row = conn.execute(
            "SELECT gold_max FROM game_config_loot_tables WHERE key=?",
            (r["loot_table_key"],),
        ).fetchone()
        if not row or int(row["gold_max"] or 0) <= 0:
            zero.append(r["key"])
    assert not zero, f"wrogowie dropiący 0 zł (per-enemy gold_max=0): {zero}"


# ─── Backward compat — feed komponentów craftingu nietknięty ─────────────────

def test_every_enemy_resolves_tier_table(conn):
    """Każdy wróg mapuje się na aktywną tabelę tierową (union loot / komponenty)."""
    missing = [r["key"] for r in _enemies(conn) if not _resolve_tier_table_key(conn, r)]
    assert not missing, f"wrogowie bez tabeli tierowej (brak feedu komponentów): {missing}"
