"""Issue #1519 — balans czarów bojowych między rasami (gra jest głównie solo).

Przed: człowiek 32 czary bojowe (komplet ról na każdym tierze), krasnolud 6
(same obrażenia, zero leczenia/kontroli/reakcji), elf 6 (nic powyżej T3).
Po: każda rasa ma dostęp do ról obrona / leczenie / kontrola / reakcja i pełną
ścieżkę T1-T5, przy zachowanych różnych profilach mocy.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.migrations_admin import _seed_race_combat_balance
from app.services.spell_service import defense_absorb_amount

COMBAT_TYPES = ("attack", "attack_aoe", "defense", "heal", "effect", "effect_aoe", "reaction")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE game_config_spells (
          key TEXT PRIMARY KEY, label TEXT, tier INTEGER DEFAULT 1,
          mana_cost INTEGER DEFAULT 1, spell_type TEXT DEFAULT 'attack',
          damage_die TEXT, heal_die TEXT, target_zone TEXT DEFAULT 'any',
          aoe INTEGER DEFAULT 0, effect_json TEXT, description TEXT,
          is_active INTEGER DEFAULT 1, race_lock TEXT
        );
        CREATE TABLE character_spells (
          character_id INTEGER, spell_key TEXT, rank INTEGER DEFAULT 1
        );
    """)
    # stan „przed" — istotne dla testów przycinania duplikatów
    conn.executemany(
        "INSERT INTO game_config_spells (key, label, tier, mana_cost, spell_type, "
        "damage_die, heal_die, race_lock) VALUES (?,?,?,?,?,?,?,'human')",
        [
            ("fire_bolt", "Ognisty Pocisk", 1, 1, "attack", "1d8", None),
            ("frost_bolt", "Mroźna Strzała", 1, 2, "attack", "1d8", None),
            ("magic_bolt", "Błysk Magiczny", 1, 2, "attack", "2d6", None),
            ("acid_splash", "Plusk Kwasu", 1, 1, "attack", "1d6", None),
            ("lightning_arrow", "Piorunowy Grot", 2, 3, "attack", "2d6", None),
            ("ice_lance", "Lodowa Lanca", 2, 3, "attack", "2d8", None),
        ],
    )
    conn.execute(
        "INSERT INTO game_config_spells (key, label, tier, mana_cost, spell_type, "
        "damage_die, race_lock) VALUES ('mend_bark','Kora Zrasta',2,2,'heal','2d4','elf')"
    )
    conn.commit()
    return conn


def _by_race(conn, race: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM game_config_spells WHERE race_lock = ? AND is_active = 1 "
        "AND spell_type IN {} ORDER BY tier".format(COMBAT_TYPES), (race,)
    ).fetchall()


# ─── Nowe czary bojowe ───────────────────────────────────────────────────────

def test_adds_five_combat_spells_per_race():
    conn = _conn()
    try:
        _seed_race_combat_balance(conn)
        for race in ("elf", "dwarf"):
            new = conn.execute(
                "SELECT COUNT(*) FROM game_config_spells WHERE race_lock = ? "
                "AND key IN ('shadow_step','elder_bark','thorn_rain','green_rebirth',"
                "'song_of_the_crack','stone_stance','ember_mend','rockbind','clan_runes',"
                "'ancestral_bulwark')", (race,)
            ).fetchone()[0]
            assert new == 5, race
    finally:
        conn.close()


def test_every_race_gets_defense_heal_and_control():
    """Solo = brak drużyny, która załata brakującą rolę."""
    conn = _conn()
    try:
        _seed_race_combat_balance(conn)
        for race in ("elf", "dwarf"):
            types = {r["spell_type"] for r in _by_race(conn, race)}
            assert "defense" in types, race
            assert "heal" in types, race
            assert "reaction" in types, race
    finally:
        conn.close()


def test_dwarf_defense_available_from_level_one():
    """Krasnolud miał pierwszą tarczę dopiero na T2 = poziom 3."""
    conn = _conn()
    try:
        _seed_race_combat_balance(conn)
        row = conn.execute(
            "SELECT * FROM game_config_spells WHERE key = 'stone_stance'").fetchone()
        assert row["tier"] == 1 and row["spell_type"] == "defense"
        assert defense_absorb_amount(dict(row)) == 6
    finally:
        conn.close()


def test_elf_has_options_on_tier_four_and_five():
    conn = _conn()
    try:
        _seed_race_combat_balance(conn)
        tiers = {r["tier"] for r in _by_race(conn, "elf")}
        assert {4, 5} <= tiers
    finally:
        conn.close()


def test_elf_damage_stays_below_dwarf_at_top_tier():
    """Profile zostają różne: elf kontroluje, krasnolud bije."""
    conn = _conn()
    try:
        _seed_race_combat_balance(conn)
        elf_top = conn.execute(
            "SELECT damage_die FROM game_config_spells WHERE key = 'song_of_the_crack'"
        ).fetchone()[0]
        assert elf_top == "3d8"  # krasnoludzki black_vein to 4d8
    finally:
        conn.close()


def test_reaction_payloads_use_engine_supported_mechanics():
    """Silnik zna tylko mirror_image / blink / globe — inne dają unsupported_reaction."""
    conn = _conn()
    try:
        _seed_race_combat_balance(conn)
        for key in ("shadow_step", "ancestral_bulwark"):
            ej = json.loads(conn.execute(
                "SELECT effect_json FROM game_config_spells WHERE key = ?", (key,)
            ).fetchone()[0])
            assert ej["reaction"] in ("mirror_image", "blink", "globe", "globe_invulnerability")
    finally:
        conn.close()


# ─── Przycinanie ludzkich duplikatów ─────────────────────────────────────────

def test_dominated_duplicates_disabled_when_nobody_knows_them():
    conn = _conn()
    try:
        _seed_race_combat_balance(conn)
        for key in ("frost_bolt", "lightning_arrow"):
            active = conn.execute(
                "SELECT is_active FROM game_config_spells WHERE key = ?", (key,)
            ).fetchone()[0]
            assert active == 0, key
    finally:
        conn.close()


def test_duplicate_kept_active_when_a_character_knows_it():
    """Wyłączony czar znika z `get_spell` — gracz zostałby z martwym wpisem na karcie."""
    conn = _conn()
    try:
        conn.execute("INSERT INTO character_spells VALUES (7, 'frost_bolt', 1)")
        conn.commit()
        _seed_race_combat_balance(conn)
        active = conn.execute(
            "SELECT is_active FROM game_config_spells WHERE key = 'frost_bolt'").fetchone()[0]
        assert active == 1
    finally:
        conn.close()


def test_acid_splash_gets_a_role_instead_of_deletion():
    conn = _conn()
    try:
        _seed_race_combat_balance(conn)
        ej = conn.execute(
            "SELECT effect_json FROM game_config_spells WHERE key = 'acid_splash'").fetchone()[0]
        assert json.loads(ej)["ignore_armor"] is True
        assert conn.execute(
            "SELECT is_active FROM game_config_spells WHERE key = 'acid_splash'"
        ).fetchone()[0] == 1
    finally:
        conn.close()


def test_magic_bolt_moved_off_tier_one():
    conn = _conn()
    try:
        _seed_race_combat_balance(conn)
        assert conn.execute(
            "SELECT tier FROM game_config_spells WHERE key = 'magic_bolt'").fetchone()[0] == 2
    finally:
        conn.close()


def test_mend_bark_heal_die_repaired():
    """#1474 wpisał leczenie w kolumnę obrażeń → silnik leczył fallbackiem 2d6."""
    conn = _conn()
    try:
        _seed_race_combat_balance(conn)
        row = conn.execute(
            "SELECT damage_die, heal_die FROM game_config_spells WHERE key = 'mend_bark'"
        ).fetchone()
        assert row["heal_die"] == "2d4" and row["damage_die"] is None
    finally:
        conn.close()


def test_seed_is_idempotent():
    conn = _conn()
    try:
        _seed_race_combat_balance(conn)
        before = conn.execute("SELECT COUNT(*) FROM game_config_spells").fetchone()[0]
        _seed_race_combat_balance(conn)
        assert conn.execute("SELECT COUNT(*) FROM game_config_spells").fetchone()[0] == before
    finally:
        conn.close()
