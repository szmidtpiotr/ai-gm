"""TDD: Issue #585 (S5) — Seed ~18 skilli kategorii A (czyste testy).

RED→GREEN: hurtowy zasiew skilli z design doc TABELA 1 (POZA dodge/shield_block/
wrestling → Blok 4, haggling → S6, gamble → S7) do `game_config_skills`, wiersze
`skill_counters` (opposed/dc) oraz rozszerzenie mapy ryzyka U7
(`game_config_skill_risk_categories`). Silnik już obsługuje czyste testy — S5
dokłada wyłącznie DANE (seedy idempotentne, brak migracji schematu).

Test sprawdza ŻYWĄ bazę DEV (`/data/ai_gm.db` wewnątrz kontenera backendu — to
samo źródło, na którym uruchamia się migracja przy starcie). Asercja braku
duplikatów (COUNT == DISTINCT) potwierdza idempotencję INSERT OR IGNORE.
"""
import os
import sqlite3

import pytest

DB_PATH = os.environ.get("AIGM_DB_PATH", "/data/ai_gm.db")

pytestmark = pytest.mark.skipif(
    not os.path.exists(DB_PATH),
    reason=f"żywa baza DEV niedostępna ({DB_PATH}) — uruchom w kontenerze backendu",
)


# 18 nowych skilli kategorii A: klucz → linked_stat primary
NEW_SKILLS = {
    "riding": "DEX",
    "endurance": "CON",
    "swim": "STR",
    "climb": "STR",
    "charm": "CHA",
    "gossip": "CHA",
    "bribe": "CHA",
    "trade_craft": "INT",
    "language": "INT",
    "theology": "WIS",
    "nature": "WIS",
    "alchemy": "INT",
    "magic_sense": "WIS",
    "tracking": "WIS",
    "sailing": "INT",
    "pickpocket": "DEX",
    "disguise": "CHA",
    "torture": "CHA",
}

VALID_STATS = {"STR", "DEX", "CON", "INT", "WIS", "CHA"}

# Skille z testem przeciwnym (counter_type='opposed') + stat obrony celu
OPPOSED_COUNTERS = {
    "charm": "WIS",
    "bribe": "WIS",
    "pickpocket": "WIS",
    "disguise": "WIS",
    "torture": "CON",
}

# Skille nakładające ryzyko fizyczne/społeczne — U7 safety net musi je rozpoznać
EXPECTED_RISK_SKILL_KEYS = {"swim", "riding", "pickpocket", "disguise", "tracking", "sailing", "bribe"}


def _rows(sql, params=()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


# ─── Seed game_config_skills ────────────────────────────────────────────────

def test_all_new_skills_seeded():
    """Wszystkie 18 skilli kategorii A są w game_config_skills."""
    keys = {r["key"] for r in _rows("SELECT key FROM game_config_skills")}
    missing = set(NEW_SKILLS) - keys
    assert not missing, f"Brakuje skilli w seedzie: {sorted(missing)}"


def test_new_skills_linked_stat_valid():
    """Każdy nowy skill ma linked_stat z dozwolonego zbioru i zgodny z designem."""
    rows = _rows(
        "SELECT key, linked_stat FROM game_config_skills WHERE key IN ({})".format(
            ",".join("?" * len(NEW_SKILLS))
        ),
        tuple(NEW_SKILLS),
    )
    by_key = {r["key"]: r["linked_stat"] for r in rows}
    for key, expected_stat in NEW_SKILLS.items():
        assert by_key.get(key) in VALID_STATS, f"{key}: linked_stat poza zbiorem"
        assert by_key[key] == expected_stat, f"{key}: linked_stat {by_key[key]} != {expected_stat}"


def test_new_skills_have_nonempty_description():
    """description niepusty — trafia do katalogu LLM (config_service SELECT description)."""
    rows = _rows(
        "SELECT key, description FROM game_config_skills WHERE key IN ({})".format(
            ",".join("?" * len(NEW_SKILLS))
        ),
        tuple(NEW_SKILLS),
    )
    assert rows, "brak nowych skilli w bazie"
    for r in rows:
        assert (r["description"] or "").strip(), f"{r['key']}: pusty description"


def test_craft_skills_marked_narrative():
    """trade_craft i alchemy oznaczone jako efekt narracyjny (crafting poza zakresem)."""
    rows = _rows(
        "SELECT key, description FROM game_config_skills WHERE key IN ('trade_craft','alchemy')"
    )
    assert len(rows) == 2, "trade_craft/alchemy niezaseedowane"
    for r in rows:
        desc = (r["description"] or "").lower()
        assert "poza zakresem" in desc or "narracyj" in desc, f"{r['key']}: brak adnotacji crafting"


def test_no_duplicate_skill_keys():
    """COUNT == DISTINCT — seed idempotentny (INSERT OR IGNORE, brak duplikatów)."""
    total = _rows("SELECT COUNT(*) c FROM game_config_skills")[0]["c"]
    distinct = _rows("SELECT COUNT(DISTINCT key) c FROM game_config_skills")[0]["c"]
    assert total == distinct, f"duplikaty kluczy skilli: {total} != {distinct}"


# ─── Seed skill_counters ────────────────────────────────────────────────────

def test_opposed_counters_seeded():
    """Skille z testem przeciwnym mają wiersz opposed z poprawnym counter_key."""
    rows = _rows(
        "SELECT player_skill_key, counter_type, counter_key FROM skill_counters "
        "WHERE player_skill_key IN ({})".format(",".join("?" * len(OPPOSED_COUNTERS))),
        tuple(OPPOSED_COUNTERS),
    )
    by_key = {r["player_skill_key"]: r for r in rows}
    for skill, stat in OPPOSED_COUNTERS.items():
        assert skill in by_key, f"brak countera dla {skill}"
        assert by_key[skill]["counter_type"] == "opposed", f"{skill}: nie opposed"
        assert by_key[skill]["counter_key"] == stat, f"{skill}: counter_key {by_key[skill]['counter_key']} != {stat}"


def test_dc_counters_clamped_to_dc_lock():
    """default_dc każdego nowego countera należy do zbioru DC lock {8,12,16,20,24}."""
    rows = _rows(
        "SELECT player_skill_key, default_dc FROM skill_counters "
        "WHERE player_skill_key IN ({})".format(",".join("?" * len(NEW_SKILLS))),
        tuple(NEW_SKILLS),
    )
    assert rows, "brak counterów dla nowych skilli"
    for r in rows:
        assert r["default_dc"] in {8, 12, 16, 20, 24}, f"{r['player_skill_key']}: DC {r['default_dc']} poza DC lock"


# ─── Seed U7 risk categories ────────────────────────────────────────────────

def test_risk_categories_extended_for_new_skills():
    """Mapa ryzyka U7 rozszerzona o nowe skille (kieszonkostwo, pływanie, przebranie...)."""
    skill_keys = {
        r["skill_key"]
        for r in _rows("SELECT skill_key FROM game_config_skill_risk_categories")
    }
    missing = EXPECTED_RISK_SKILL_KEYS - skill_keys
    assert not missing, f"Mapa ryzyka U7 nie pokrywa nowych skilli: {sorted(missing)}"


# ─── Backward compatibility ─────────────────────────────────────────────────

def test_existing_core_skills_untouched():
    """Istniejące skille rdzenne nadal obecne z niezmienionym linked_stat."""
    rows = _rows(
        "SELECT key, linked_stat FROM game_config_skills WHERE key IN ('stealth','attack','persuasion')"
    )
    by_key = {r["key"]: r["linked_stat"] for r in rows}
    assert by_key.get("stealth") == "DEX"
    assert by_key.get("attack") == "STR"
    assert by_key.get("persuasion") == "CHA"
