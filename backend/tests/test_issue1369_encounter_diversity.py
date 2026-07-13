"""TDD: Issue #1369 — Monotonia spotkań w podróży (pula poz. 1-2, śmieci testowe,
dziura terenów, słaby anti-repeat).

Cztery mechanizmy naprawcze (diagnoza w #1369):
  #2 guard puli — wrogowie testowi/placeholdery nigdy nie wchodzą do puli spotkań.
  #3 słownik terenów — hex_type (bridge/snow/lake/town…) → tag wroga, zamiast pustki.
  #4 anti-repeat po enemy_key — twardy blok klucza z ostatniego spotkania przy puli ≥3
     + mocniejsza kara przy 2 kolejnych powtórkach.

Testy budują własną bazę in-memory (game_config_enemies) — deterministyczne, bez DEV DB.
"""
from _fixtures_schema import table_sql
import random
import sqlite3

import pytest

from app.services import encounter_service as es


# ─── Fixtures / helpers ──────────────────────────────────────────────────────

_ENEMY_COLS = (
    "key", "label", "hp_base", "ac_base", "attack_bonus", "damage_die",
    "damage_bonus", "attacks_per_turn", "tier", "min_level", "max_level",
    "terrain_tags", "world_scope", "review_status", "is_active",
)


def _mk_conn(enemies: list[dict]) -> sqlite3.Connection:
    """In-memory DB z samą tabelą game_config_enemies (bez game_config_meta →
    _meta_float spada na wartości domyślne, co jest pożądane w teście)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        """ + table_sql("game_config_enemies") + """
        """
    )
    for e in enemies:
        row = {**{c: None for c in _ENEMY_COLS}, **e}
        row.setdefault("world_scope", "global")
        row["world_scope"] = e.get("world_scope", "global")
        row["review_status"] = e.get("review_status", "permanent")
        row["is_active"] = e.get("is_active", 1)
        conn.execute(
            f"INSERT INTO game_config_enemies ({','.join(_ENEMY_COLS)}) "
            f"VALUES ({','.join('?' for _ in _ENEMY_COLS)})",
            tuple(row[c] for c in _ENEMY_COLS),
        )
    conn.commit()
    return conn


def _enemy(key, *, tier="standard", tags="road", hp=10, ac=12, atk=2,
           die="d6", lvl=(1, 2), scope="global", review="permanent", active=1):
    return {
        "key": key, "label": key.title(), "hp_base": hp, "ac_base": ac,
        "attack_bonus": atk, "damage_die": die, "damage_bonus": 0,
        "attacks_per_turn": 1, "tier": tier, "min_level": lvl[0],
        "max_level": lvl[1], "terrain_tags": tags, "world_scope": scope,
        "review_status": review, "is_active": active,
    }


# ─── #3 — słownik terenów hex_type → tag wroga ───────────────────────────────

@pytest.mark.parametrize("hex_type,expected", [
    ("bridge", "road"),
    ("Bridge", "road"),        # case-insensitive
    ("snow", "plains"),
    ("tundra", "plains"),
    ("heath", "plains"),
    ("lake", "river"),
    ("sea", "river"),
    ("coast", "river"),
    ("town", "city"),
    ("village", "city"),
    ("przelecz", "mountain"),
    ("grania", "mountain"),
    ("forest", "forest"),      # znany tag — passthrough
    ("road", "road"),          # passthrough
    (None, None),
    ("", None),
])
def test_normalize_hex_terrain(hex_type, expected):
    assert es._normalize_hex_terrain(hex_type) == expected


def test_bridge_hex_matches_road_enemies_not_empty():
    """Most (bridge) — pierwsza walka Piotra. Bez mapowania filtr dawał pustkę i
    relax-to-all. Teraz bridge≈road → w puli wrogowie drogowi, brak zejścia do relax."""
    conn = _mk_conn([
        _enemy("bandit", tags="road,forest,plains"),
        _enemy("guard", tags="city,castle,road"),
        _enemy("wilk_stepowy", tags="road,plains,wilderness"),
        _enemy("zombie", tags="swamp,ruins,dungeon"),  # NIE na road → poza pulą
    ])
    pool = es.eligible_enemy_pool(conn, level=1, hex_type="bridge")
    keys = {d["key"] for d in pool}
    assert "bandit" in keys and "guard" in keys and "wilk_stepowy" in keys
    assert "zombie" not in keys, "bridge≈road nie może wciągać wrogów bagiennych"


# ─── #2 — guard puli: śmieci testowe nigdy nie wchodzą ───────────────────────

@pytest.mark.parametrize("key,is_test", [
    ("enemy", True),
    ("unknown_attacker", True),
    ("old_man", True),
    ("s2_pw_bandyta_lucznik", True),
    ("s2_pw_custom_stats", True),
    ("s4_pw_kaplan", True),
    ("s4_pw_osilek", True),
    ("goblin_u31", True),
    ("bandit", False),
    ("wolf", False),
    ("guard", False),
    ("dark_mage", False),
    (None, False),
    ("", False),
])
def test_is_test_enemy_key(key, is_test):
    assert es._is_test_enemy_key(key) is is_test


def test_junk_excluded_from_pool():
    """Rekordy testowe permanent+global nigdy nie trafiają do puli (wzór #941)."""
    conn = _mk_conn([
        _enemy("bandit", tags="road"),
        _enemy("wolf", tags="road,plains"),
        _enemy("enemy", tags="road,wilderness"),            # śmieć
        _enemy("old_man", tags="city,road"),                # śmieć (Starzec)
        _enemy("s2_pw_bandyta_lucznik", tags="road,forest"),  # śmieć
        _enemy("goblin_u31", tags="road"),                  # śmieć
    ])
    pool = es.eligible_enemy_pool(conn, level=1, hex_type="road")
    keys = {d["key"] for d in pool}
    assert keys == {"bandit", "wolf"}, f"śmieci w puli: {keys}"


# ─── #4 — anti-repeat po enemy_key ───────────────────────────────────────────

def test_build_penalty_map_escalates_on_consecutive():
    """Klucz w 2 kolejnych spotkaniach → kara podniesiona do potęgi (penalty**2)."""
    pm = es._build_penalty_map(["bandit+wolf", "bandit"], 0.25)
    assert pm["bandit"] == pytest.approx(0.25 ** 2)
    assert pm["wolf"] == pytest.approx(0.25)
    assert es._build_penalty_map([], 0.25) == {}


def test_composer_avoids_last_enemy_key_when_pool_ge3():
    """Przy puli ≥3 różnych kluczy: skomponowane spotkanie NIE powtarza klucza
    z ostatniego spotkania (twardy blok #1369)."""
    conn = _mk_conn([
        _enemy("bandit", tier="standard", tags="road", hp=12, atk=3),
        _enemy("guard", tier="standard", tags="road", hp=10, atk=2),
        _enemy("wilk_stepowy", tier="standard", tags="road", hp=11, atk=3),
    ])
    for seed in range(30):
        enc = es.encounter_composer(
            conn, level=1, hex_type="road",
            rng=random.Random(seed), recent_sigs=["bandit"],
        )
        assert enc is not None
        keys = {e["enemy_key"] for e in enc["enemies"]}
        assert "bandit" not in keys, f"seed={seed}: powtórzył bandit mimo puli ≥3"


def test_composer_repeat_allowed_when_pool_lt3():
    """Pula < 3 kluczy — twardy blok po kluczu NIE obowiązuje (brak alternatyw);
    composer nadal zwraca poprawne spotkanie (backward compat)."""
    conn = _mk_conn([
        _enemy("bandit", tags="road", hp=12),
        _enemy("guard", tags="road", hp=10),
    ])
    enc = es.encounter_composer(
        conn, level=1, hex_type="road",
        rng=random.Random(0), recent_sigs=["bandit"],
    )
    assert enc is not None
    assert enc["enemies"], "composer musi zwrócić wrogów nawet przy małej puli"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_composer_no_history_unchanged():
    """Bez historii spotkań composer działa jak wcześniej (dowolny wróg z puli)."""
    conn = _mk_conn([
        _enemy("bandit", tags="forest"),
        _enemy("wolf", tags="forest"),
        _enemy("goblin", tier="weak", tags="forest", hp=8),
    ])
    enc = es.encounter_composer(
        conn, level=1, hex_type="forest",
        rng=random.Random(1), recent_sigs=[],
    )
    assert enc is not None
    keys = {e["enemy_key"] for e in enc["enemies"]}
    assert keys <= {"bandit", "wolf", "goblin"}


def test_known_terrain_still_filters():
    """Znany hex_type (forest) nadal filtruje po tagach — bez regresji #3."""
    conn = _mk_conn([
        _enemy("wolf", tags="forest,hills"),
        _enemy("bandit", tags="road,plains"),  # NIE forest
    ])
    pool = es.eligible_enemy_pool(conn, level=1, hex_type="forest")
    keys = {d["key"] for d in pool}
    assert keys == {"wolf"}
