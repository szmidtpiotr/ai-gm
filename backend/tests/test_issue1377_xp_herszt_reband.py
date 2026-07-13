"""TDD: Issue #1377 — residua #1376: normalizacja XP + cap budżetu herszt + reband.

BRAMKA kodująca kryteria akceptacji:
  1. XP monotoniczny per tier: sortując wrogów tieru po threat, xp_award nie maleje
     (xp = round(threat × mult) → wyższy threat ⇒ >= xp). Łapie goblin xp=3 i
     niemonotoniczne bossy (demon_lord 1800 > dragon 1500 mimo niższego threat).
  2. Herszt nie przekracza budżetu: leader_threat + Σ poplecznicy <= budget; gdy
     lider ~budget → herszt degeneruje do samotnego lidera (residuum #1346).
  3. vampire_master rebandowany na L8-10 (threat 102.5 — sufit elit, nie lvl 6-7)."""
import os
import random
import sqlite3

import pytest

from app.services.encounter_service import _compose_enemies, enemy_threat_value

DB_PATH = os.environ.get("AI_GM_DB_PATH", "/data/ai_gm.db")


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


# ─── Test 1 — XP monotoniczny per tier (threat ↑ ⇒ xp ↑) ─────────────────────

@pytest.mark.parametrize("tier", ["weak", "standard", "elite", "boss"])
def test_xp_monotonic_within_tier(conn, tier):
    rows = [dict(r) for r in _enemies(conn) if r["tier"] == tier]
    seq = sorted(((enemy_threat_value(r), r["xp_award"], r["key"]) for r in rows))
    prev_xp, prev_key = -1, None
    for thr, xp, key in seq:
        assert xp >= prev_xp, (
            f"XP niemonotoniczny w {tier}: {key} threat={thr:.1f} xp={xp} "
            f"< poprzedni {prev_key} xp={prev_xp}"
        )
        prev_xp, prev_key = xp, key


def test_no_zero_or_trivial_xp(conn):
    """Żaden wróg nie ma xp poniżej realnej wartości (goblin xp=3 bug)."""
    bad = [(r["key"], r["xp_award"], round(enemy_threat_value(dict(r)), 1))
           for r in _enemies(conn)
           if r["xp_award"] < enemy_threat_value(dict(r)) * 0.7]
    assert not bad, f"wrogowie z rażąco zaniżonym xp (<0.7×threat): {bad}"


# ─── Test 2 — herszt nie przekracza budżetu ──────────────────────────────────

def test_herszt_respects_budget(conn):
    """Lider ~budget → composer NIE dokłada poplecznikow ponad budżet."""
    pool = [
        {"key": "lead_boss", "label": "Lider", "tier": "elite", "threat": 100.0},
        {"key": "minion_std", "label": "Popl", "tier": "standard", "threat": 20.0},
    ]
    budget = 100.0  # lider sam zżera cały budżet
    seen_herszt = False
    for seed in range(80):
        rng = random.Random(seed)
        p, e = _compose_enemies(conn, [dict(d) for d in pool], budget, rng, {})
        if p != "herszt":
            continue
        seen_herszt = True
        spent = sum(
            x["count"] * next(d["threat"] for d in pool if d["key"] == x["enemy_key"])
            for x in e
        )
        assert spent <= budget * 1.05, (
            f"herszt overspend seed={seed}: spent={spent} > budget={budget} "
            f"({[(x['enemy_key'], x['count']) for x in e]})"
        )
    assert seen_herszt, "test nie trafił wzorca herszt w 80 seedach — popraw fixture"


# ─── Test 3 — vampire_master reband L8-10 ─────────────────────────────────────

def test_vampire_master_rebanded(conn):
    r = conn.execute(
        "SELECT min_level, max_level FROM game_config_enemies WHERE key='vampire_master'"
    ).fetchone()
    assert r and r["min_level"] == 8 and r["max_level"] == 10, (
        f"vampire_master pasmo = {dict(r) if r else None}, oczekiwane 8-10"
    )
