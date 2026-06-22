"""TDD: Issue #611 — S16: reakcja `shield_block` (druga reakcja w grze).

Reużywa frameworku reakcji z S15 (#610). Gracz z założoną TARCZĄ i skillem
`shield_block` rank ≥ 1 może zadeklarować BLOK (`reaction_declared == 'shield_block'`).
Gdy wróg TRAFIA, MECHANIKA wykonuje test STR (d20 + STR_mod + skill_rank + proficiency)
przeciw wynikowi ataku wroga (DC = max(attack_roll, 12)). Stopień liczony silnikiem S1
(_derive_outcome):
  • sukces (margines ≥ 0)              → obrażenia − (1d6 + STR_mod, min 0)
  • sukces o ≥ +5 / CRITICAL_SUCCESS   → pełne odparcie (0 obrażeń)
  • porażka (margines < 0)             → pełne obrażenia
  • CRITICAL_FAILURE (margines ≤ −5)   → pełne obrażenia + tarcza traci durability ×3 (F7)

XOR z dodge (jedna reakcja/rundę — `reaction_declared` trzyma jedną wartość). Skill-gated
+ gate tarczy (założona broń z game_config_weapons, key zawiera 'shield' lub label 'tarcz').

RZUT ATAKU WROGA (nat 20/nat 1, podwójne obrażenia) NIETKNIĘTY — reakcja działa wyłącznie
na obrażenia po trafieniu; margines dotyczy testu bloku (sam jest testem umiejętności).
"""
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import combat_service


def _player(*, declared="shield_block", skill_rank=2, str_stat=10, conditions=None):
    p = {
        "id": "player", "type": "player", "name": "Bohater",
        "hp_current": 20, "hp_max": 20, "defense": 10, "zone": "engaged",
        "stats": {"STR": str_stat, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
        "conditions": conditions or [],
    }
    if declared:
        p["reaction_declared"] = declared
    sheet = {"stats": p["stats"], "skills": {"shield_block": skill_rank}}
    return p, sheet


# ─── Helper _try_shield_block_reaction (unit) ─────────────────────────────────

def test_block_success_reduces_damage(monkeypatch):
    """Sukces (margines ≥ 0, < +5) → obrażenia − (1d6 + STR_mod)."""
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 14)
    monkeypatch.setattr(combat_service, "_player_has_shield_equipped", lambda *a, **k: (True, 1))
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 4)  # 1d6 → 4
    p, sheet = _player(skill_rank=2, str_stat=14)   # STR mod +2 + rank 2 → mod_total 4
    res = combat_service._try_shield_block_reaction(
        None, None, p, sheet, attack_roll=15, round_n=1, dmg=10)
    assert res is not None
    assert res["available"] is True
    # 14+4=18 vs DC 15 → margines +3 (sukces, nie pełne odparcie)
    assert res["full_block"] is False
    assert res["reduction"] == 6                     # 1d6(4) + STR_mod(2)
    assert res["damage_after"] == 4                  # 10 - 6
    assert "reaction_declared" not in p              # deklaracja skonsumowana


def test_block_full_at_margin_5(monkeypatch):
    """Margines ≥ +5 → pełne odparcie (0 obrażeń)."""
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 19)
    monkeypatch.setattr(combat_service, "_player_has_shield_equipped", lambda *a, **k: (True, 1))
    p, sheet = _player(skill_rank=2, str_stat=10)   # mod_total 2
    res = combat_service._try_shield_block_reaction(
        None, None, p, sheet, attack_roll=15, round_n=1, dmg=10)
    # 19+2=21 vs DC 15 → margines +6 ≥ +5
    assert res["full_block"] is True
    assert res["damage_after"] == 0


def test_block_failure_keeps_damage(monkeypatch):
    """Porażka (margines < 0) → pełne obrażenia, brak utraty durability."""
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 8)
    monkeypatch.setattr(combat_service, "_player_has_shield_equipped", lambda *a, **k: (True, 1))
    p, sheet = _player(skill_rank=2, str_stat=10)
    res = combat_service._try_shield_block_reaction(
        None, None, p, sheet, attack_roll=15, round_n=1, dmg=10)
    assert res["full_block"] is False
    assert res["damage_after"] == 10
    assert res["durability_hit"] is False


def test_block_min_dc_12(monkeypatch):
    """DC bloku nie schodzi poniżej 12 nawet przy słabym ataku wroga."""
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 9)
    monkeypatch.setattr(combat_service, "_player_has_shield_equipped", lambda *a, **k: (True, 1))
    p, sheet = _player(skill_rank=2, str_stat=10)   # mod_total 2 → total 11
    res = combat_service._try_shield_block_reaction(
        None, None, p, sheet, attack_roll=5, round_n=1, dmg=10)
    assert res["dc"] == 12                            # max(5, 12)
    assert res["full_block"] is False
    assert res["damage_after"] == 10                  # 11 < 12 → porażka


def test_no_declaration_returns_none():
    """Brak pre-deklaracji bloku → None (silnik idzie normalną ścieżką)."""
    p, sheet = _player(declared=None)
    assert combat_service._try_shield_block_reaction(
        None, None, p, sheet, attack_roll=15, round_n=1, dmg=10) is None


def test_no_skill_returns_none_and_clears():
    """Bez skilla shield_block (rank 0) → None + flaga wyczyszczona (skill-gated)."""
    p, sheet = _player(skill_rank=0)
    assert combat_service._try_shield_block_reaction(
        None, None, p, sheet, attack_roll=15, round_n=1, dmg=10) is None
    assert "reaction_declared" not in p


def test_proficiency_bonus_at_rank3(monkeypatch):
    """Rank ≥ 3 daje +2 proficiency (spójne z mechaniką testów)."""
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 10)
    monkeypatch.setattr(combat_service, "_player_has_shield_equipped", lambda *a, **k: (True, 1))
    p, sheet = _player(skill_rank=3, str_stat=10)   # STR 0 + rank 3 + prof 2 → mod_total 5
    res = combat_service._try_shield_block_reaction(
        None, None, p, sheet, attack_roll=15, round_n=1, dmg=10)
    assert res["block_total"] == 15                  # 10 + 5
    assert res["full_block"] is False                # margines 0 → sukces, nie pełne


# ─── _player_has_shield_equipped (gate) ───────────────────────────────────────

def _inv_db(tmp_path, *, weapon_key, equipped=1, label="Tarcza", w_key=None, durability=60):
    """Mini DB z character_inventory + game_config_weapons do testu gate'u tarczy."""
    db = tmp_path / "inv.db"
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript("""
        CREATE TABLE game_config_weapons (key TEXT PRIMARY KEY, label TEXT);
        CREATE TABLE character_inventory (id INTEGER PRIMARY KEY AUTOINCREMENT,
          character_id INTEGER, weapon_key TEXT, item_key TEXT, equipped INTEGER DEFAULT 0,
          durability_current INTEGER, durability_max INTEGER);
        """)
        conn.execute("INSERT INTO game_config_weapons (key,label) VALUES (?,?)",
                     (w_key or weapon_key, label))
        conn.execute(
            "INSERT INTO character_inventory (character_id,weapon_key,equipped,durability_current,durability_max) "
            "VALUES (1,?,?,?,?)", (weapon_key, equipped, durability, durability))
        conn.commit()
        return db, conn
    finally:
        conn.close()


def test_shield_detected_by_key(tmp_path):
    """Broń z key zawierającym 'shield' i equipped=1 → tarcza wykryta."""
    db, _ = _inv_db(tmp_path, weapon_key="wooden_shield", label="Drewniana Tarcza")
    conn = sqlite3.connect(str(db))
    try:
        has, inv_id = combat_service._player_has_shield_equipped(conn, 1)
    finally:
        conn.close()
    assert has is True
    assert inv_id is not None


def test_shield_detected_by_label(tmp_path):
    """Broń z label zawierającym 'tarcz' (key bez 'shield') → tarcza wykryta."""
    db, _ = _inv_db(tmp_path, weapon_key="puklerz", label="Stalowa Tarcza")
    conn = sqlite3.connect(str(db))
    try:
        has, inv_id = combat_service._player_has_shield_equipped(conn, 1)
    finally:
        conn.close()
    assert has is True


def test_no_shield_when_unequipped(tmp_path):
    """Tarcza w plecaku ale NIE założona (equipped=0) → brak tarczy."""
    db, _ = _inv_db(tmp_path, weapon_key="wooden_shield", equipped=0)
    conn = sqlite3.connect(str(db))
    try:
        has, inv_id = combat_service._player_has_shield_equipped(conn, 1)
    finally:
        conn.close()
    assert has is False


def test_non_shield_weapon_not_detected(tmp_path):
    """Założony miecz (nie tarcza) → brak tarczy."""
    db, _ = _inv_db(tmp_path, weapon_key="shortsword", label="Krótki Miecz")
    conn = sqlite3.connect(str(db))
    try:
        has, inv_id = combat_service._player_has_shield_equipped(conn, 1)
    finally:
        conn.close()
    assert has is False


# ─── Integracja z prawdziwym silnikiem walki (resolve_attack enemy branch) ────

def _combat_db(tmp_path, *, declared, skill_rank, shield=True, shield_durability=60, attack_bonus=10):
    db = tmp_path / "block.db"
    player = {
        "id": "player", "type": "player", "name": "Aldric",
        "hp_current": 20, "hp_max": 20, "defense": 10, "zone": "engaged",
        "stats": {"STR": 14, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
        "conditions": [],
    }
    if declared:
        player["reaction_declared"] = declared
    enemy = {
        "id": "bandit", "type": "enemy", "enemy_key": "bandit", "name": "Bandit",
        "hp_current": 40, "hp_max": 40, "attack_bonus": attack_bonus,
        "damage_dice": "1d8", "zone": "engaged",
    }
    sheet = {"stats": player["stats"], "current_hp": 20, "max_hp": 20,
             "defense": {"base": 10}, "conditions": [], "skills": {"shield_block": skill_rank}}
    combatants = json.dumps([player, enemy], ensure_ascii=False).replace("'", "''")
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(f"""
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active', mode TEXT);
        INSERT INTO campaigns (id,title) VALUES (1,'S16');
        CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
          name TEXT, system_id TEXT, sheet_json TEXT);
        INSERT INTO characters (id,campaign_id,user_id,name,system_id,sheet_json)
          VALUES (1,1,1,'Aldric','fantasy','{sj}');
        CREATE TABLE game_config_weapons (key TEXT PRIMARY KEY, label TEXT);
        INSERT INTO game_config_weapons (key,label) VALUES ('wooden_shield','Drewniana Tarcza'),('shortsword','Krótki Miecz');
        CREATE TABLE character_inventory (id INTEGER PRIMARY KEY AUTOINCREMENT,
          character_id INTEGER, weapon_key TEXT, item_key TEXT, equipped INTEGER DEFAULT 0,
          durability_current INTEGER, durability_max INTEGER, affixes_json TEXT);
        CREATE TABLE active_combat (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER UNIQUE,
          character_id INTEGER, round INTEGER DEFAULT 1, turn_order TEXT, current_turn TEXT,
          combatants TEXT, status TEXT DEFAULT 'active', ended_reason TEXT, location_tag TEXT,
          loot_pool TEXT, created_at TEXT, updated_at TEXT);
        INSERT INTO active_combat (campaign_id,character_id,round,turn_order,current_turn,combatants,status)
          VALUES (1,1,1,'["bandit","player"]','bandit','{combatants}','active');
        CREATE TABLE combat_turns (id INTEGER PRIMARY KEY AUTOINCREMENT, combat_id INTEGER, campaign_id INTEGER,
          turn_number REAL, actor TEXT, event_type TEXT, roll_value INTEGER, damage INTEGER, hp_after INTEGER,
          target_id TEXT, target_name TEXT, hit INTEGER, narrative TEXT,
          created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
        """)
        if shield:
            conn.execute(
                "INSERT INTO character_inventory (character_id,weapon_key,equipped,durability_current,durability_max) "
                "VALUES (1,'wooden_shield',1,?,?)", (shield_durability, 60))
        conn.commit()
    finally:
        conn.close()
    return db


# ⚠️ SF10 (#633): pre-deklaracja → model reaktywny. Trafienie z dostępną reakcją otwiera
# okno (resolve_attack → reaction_window); blok rozliczany w resolve_reaction('shield_block').

def test_resolve_attack_block_reduces_damage(tmp_path, monkeypatch):
    """SF10: okno reakcji → resolve_reaction('block') udany → obrażenia zredukowane o 1d6+STR."""
    db = _combat_db(tmp_path, declared=None, skill_rank=2, attack_bonus=0)
    # raw 14 → wróg trafia (attack_roll 14 ≥ AC 10). Test bloku: 14 + STR2 + rank2 = 18 vs DC 14 → +4
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 14)
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 6)  # dmg 6 ; 1d6 redukcja 6
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        win = combat_service.resolve_attack(1, 0, attacker="enemy")
        assert win["hit"] is True and win.get("reaction_window") is True
        out = combat_service.resolve_reaction(1, "block")
    assert out.get("reaction", {}).get("reaction") == "shield_block"
    assert out["reaction"]["full_block"] is False
    # dmg 6 − (1d6=6 + STR2=2 = 8, min 0) → 0
    assert out["damage"] == 0
    assert out["player_hp_remaining"] == 20


def test_resolve_attack_block_critfail_hits_durability(tmp_path, monkeypatch):
    """SF10: blok przez resolve_reaction — krytyczna porażka → tarcza traci 3 durability, pełne obrażenia."""
    db = _combat_db(tmp_path, declared=None, skill_rank=2, shield_durability=60, attack_bonus=10)
    # raw 3 → attack_roll 13 (trafia AC 10). Blok: 3 + STR2 + rank2 = 7 vs DC 13 → margines -6 ≤ -5
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 3)
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 5)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        combat_service.resolve_attack(1, 0, attacker="enemy")
        out = combat_service.resolve_reaction(1, "block")
    assert out["reaction"]["durability_hit"] is True
    assert out["damage"] == 5
    conn = sqlite3.connect(str(db))
    try:
        dur = conn.execute(
            "SELECT durability_current FROM character_inventory WHERE weapon_key='wooden_shield'").fetchone()[0]
    finally:
        conn.close()
    assert dur == 57                                  # 60 − 3


def test_resolve_attack_no_shield_no_reaction(tmp_path, monkeypatch):
    """Gate tarczy: deklaracja bloku bez założonej tarczy → reakcja niedostępna, normalne obrażenia.

    #826 margin-damage model: roll=14, attack_bonus=10 → attack_roll=24, defense=10,
    margin=14, +2 extra dmg (floor(14/5)). Base roll=6 + margin 2 = 8 total.
    """
    db = _combat_db(tmp_path, declared="shield_block", skill_rank=2, shield=False)
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 14)
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 6)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, 0, attacker="enemy")
    assert out.get("reaction") is None or out["reaction"].get("available") is not True
    assert out["damage"] == 8  # 6 base + 2 margin (#826)


def test_resolve_attack_enemy_roll_untouched(tmp_path, monkeypatch):
    """Rzut ataku wroga raportowany bez zmian — reakcja nie dotyka mechaniki ataku."""
    db = _combat_db(tmp_path, declared="shield_block", skill_rank=2, attack_bonus=10)
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 18)
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 6)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, 0, attacker="enemy")
    assert out["raw_d20"] == 18
    assert out["attack_roll"] == 28                   # 18 + attack_bonus 10, nietknięte


# ─── SF10: okno reakcji → take = pełne obrażenia ──────────────────────────────

def test_resolve_attack_take_normal_damage(tmp_path, monkeypatch):
    """SF10: okno reakcji (skill+tarcza) → resolve_reaction('take') → pełne obrażenia.

    #826 margin-damage model: roll=18, attack_bonus=10 → attack_roll=28, defense=10,
    margin=18, +3 extra dmg (floor(18/5)). Base roll=6 + margin 3 = 9 total.
    """
    db = _combat_db(tmp_path, declared=None, skill_rank=2)
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 18)
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 6)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        win = combat_service.resolve_attack(1, 0, attacker="enemy")
        assert win.get("reaction_window") is True
        out = combat_service.resolve_reaction(1, "take")
    assert out["damage"] == 9  # 6 base + 3 margin (#826)
