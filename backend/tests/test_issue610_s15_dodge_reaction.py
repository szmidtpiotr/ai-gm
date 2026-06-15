"""TDD: Issue #610 — S15: system reakcji (pre-deklaracja) + skill `dodge`.

Pierwsza mechanika REAKCJI w grze. Gdy wróg TRAFIA, gracz z wykupionym unikiem
(`dodge` rank ≥ 1) i aktywną pre-deklaracją (`reaction_declared == 'dodge'`) wykonuje
test DEX (d20 + DEX_mod + skill_rank + proficiency) przeciwko WYNIKOWI ATAKU wroga
(attack_roll jako DC). Stopień liczony silnikiem S1 (_derive_outcome):
  • sukces (margines ≥ 0)        → atak mija, 0 obrażeń
  • porażka (margines < 0)        → normalne obrażenia
  • krytyczna porażka (≤ −5)      → normalne obrażenia + utrata reakcji w następnej rundzie

Pre-deklaracja konsumowana przy PIERWSZYM trafieniu w rundzie (raz/rundę). Skill-gated:
bez `dodge` rank ≥ 1 reakcja niedostępna. Wrogowie NIE dostają reakcji (symetria → backlog).

RZUT ATAKU WROGA (nat 20/nat 1, podwójne obrażenia) NIETKNIĘTY — reakcja działa wyłącznie
na aplikację obrażeń po trafieniu; margines dotyczy testu uniku (sam jest testem umiejętności).
"""
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import combat_service


def _player(*, declared="dodge", skill_rank=2, dex=10, locked_round=0, conditions=None):
    """Combatant gracza (kondycje na combatancie) + zwraca też sheet (skille na sheet)."""
    p = {
        "id": "player", "type": "player", "name": "Bohater",
        "hp_current": 20, "hp_max": 20, "defense": 10, "zone": "engaged",
        "stats": {"STR": 10, "DEX": dex, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
        "conditions": conditions or [],
    }
    if declared:
        p["reaction_declared"] = declared
    if locked_round:
        p["reaction_locked_round"] = locked_round
    sheet = {"stats": p["stats"], "skills": {"dodge": skill_rank}}
    return p, sheet


# ─── Helper _try_dodge_reaction ───────────────────────────────────────────────

def test_dodge_success_negates_attack(monkeypatch):
    """Wysoki rzut → margines ≥ 0: dodged=True (atak mija)."""
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 18)
    p, sheet = _player(skill_rank=2)          # DEX mod 0 + rank 2 → mod_total 2
    res = combat_service._try_dodge_reaction(p, sheet, attack_roll=15, round_n=1)
    assert res is not None
    assert res["available"] is True
    assert res["dodged"] is True              # 18+2=20 vs 15 → margines +5
    assert res["dodge_total"] == 20
    assert res["attack_roll"] == 15
    # pre-deklaracja skonsumowana
    assert "reaction_declared" not in p


def test_dodge_failure_keeps_damage(monkeypatch):
    """Słaby rzut → margines < 0: dodged=False, bez lockoutu."""
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 12)
    p, sheet = _player(skill_rank=2)
    res = combat_service._try_dodge_reaction(p, sheet, attack_roll=15, round_n=1)
    assert res["dodged"] is False             # 12+2=14 vs 15 → margines -1
    assert res["locked_next_round"] is False
    assert "reaction_locked_round" not in p


def test_dodge_critfail_locks_next_round(monkeypatch):
    """Krytyczna porażka (margines ≤ −5) → reaction_locked_round = round_n + 1."""
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 5)
    p, sheet = _player(skill_rank=2)
    res = combat_service._try_dodge_reaction(p, sheet, attack_roll=15, round_n=3)
    assert res["dodged"] is False             # 5+2=7 vs 15 → margines -8
    assert res["locked_next_round"] is True
    assert p["reaction_locked_round"] == 4


def test_no_declaration_returns_none():
    """Brak pre-deklaracji → None (silnik idzie normalną ścieżką obrażeń)."""
    p, sheet = _player(declared=None)
    assert combat_service._try_dodge_reaction(p, sheet, attack_roll=15, round_n=1) is None


def test_no_skill_returns_none_and_clears():
    """Pre-deklaracja bez skilla dodge (rank 0) → None + flaga wyczyszczona (skill-gated)."""
    p, sheet = _player(skill_rank=0)
    assert combat_service._try_dodge_reaction(p, sheet, attack_roll=15, round_n=1) is None
    assert "reaction_declared" not in p


def test_locked_round_blocks_reaction():
    """Reakcja zablokowana w bieżącej rundzie (po wcześniejszej krytycznej porażce)."""
    p, sheet = _player(skill_rank=2, locked_round=2)
    res = combat_service._try_dodge_reaction(p, sheet, attack_roll=15, round_n=2)
    assert res is not None
    assert res["available"] is False
    assert res["locked"] is True
    assert res["dodged"] is False
    assert "reaction_declared" not in p       # deklaracja skonsumowana mimo blokady


def test_proficiency_bonus_at_rank3(monkeypatch):
    """Rank ≥ 3 daje +2 proficiency (spójne z zablokowaną mechaniką testów)."""
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 10)
    p, sheet = _player(skill_rank=3)          # DEX 0 + rank 3 + prof 2 → mod_total 5
    res = combat_service._try_dodge_reaction(p, sheet, attack_roll=15, round_n=1)
    assert res["dodge_total"] == 15           # 10 + 5
    assert res["dodged"] is True              # margines 0 → obrońca wygrywa remis


# ─── Integracja z prawdziwym silnikiem walki (resolve_attack enemy branch) ────

def _combat_db(tmp_path, *, declared, skill_rank, locked_round=0, attack_bonus=10):
    db = tmp_path / "dodge.db"
    player = {
        "id": "player", "type": "player", "name": "Aldric",
        "hp_current": 20, "hp_max": 20, "defense": 10, "zone": "engaged",
        "stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
        "conditions": [],
    }
    if declared:
        player["reaction_declared"] = declared
    if locked_round:
        player["reaction_locked_round"] = locked_round
    enemy = {
        "id": "bandit", "type": "enemy", "enemy_key": "bandit", "name": "Bandit",
        "hp_current": 40, "hp_max": 40, "attack_bonus": attack_bonus, "damage_dice": "1d8", "zone": "engaged",
    }
    sheet = {"stats": player["stats"], "current_hp": 20, "max_hp": 20,
             "defense": {"base": 10}, "conditions": [], "skills": {"dodge": skill_rank}}
    combatants = json.dumps([player, enemy], ensure_ascii=False).replace("'", "''")
    sj = json.dumps(sheet, ensure_ascii=False).replace("'", "''")
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(f"""
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active');
        INSERT INTO campaigns (id,title) VALUES (1,'S15');
        CREATE TABLE characters (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER,
          name TEXT, system_id TEXT, sheet_json TEXT);
        INSERT INTO characters (id,campaign_id,user_id,name,system_id,sheet_json)
          VALUES (1,1,1,'Aldric','fantasy','{sj}');
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
        conn.commit()
    finally:
        conn.close()
    return db


# ⚠️ SF10 (#633): model PRE-DEKLARACJI zastąpiony REAKTYWNYM. Trafienie z dostępnym
# skillem otwiera OKNO reakcji (resolve_attack → reaction_window); rozliczenie w
# resolve_reaction(choice). Poniższe testy integracyjne zaktualizowane do dwukrokowego flow.

def test_resolve_attack_dodge_negates_damage(tmp_path, monkeypatch):
    """SF10: trafienie → okno reakcji → resolve_reaction('dodge') udany → 0 obrażeń."""
    # słaby atak (attack_bonus 0 → attack_roll = 18); unik 18+rank2 = 20 ≥ 18 → atak mija
    db = _combat_db(tmp_path, declared=None, skill_rank=2, attack_bonus=0)
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 18)   # wróg trafia (raw 18) + unik zdany
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 7)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        win = combat_service.resolve_attack(1, 0, attacker="enemy")
        assert win["hit"] is True and win.get("reaction_window") is True
        out = combat_service.resolve_reaction(1, "dodge")
    assert out.get("reaction", {}).get("dodged") is True
    assert out["damage"] == 0
    assert out["player_hp_remaining"] == 20          # bez obrażeń


def test_resolve_attack_take_normal_damage(tmp_path, monkeypatch):
    """SF10: okno reakcji → resolve_reaction('take') → pełne obrażenia."""
    db = _combat_db(tmp_path, declared=None, skill_rank=2)
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 18)
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 7)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        win = combat_service.resolve_attack(1, 0, attacker="enemy")
        assert win.get("reaction_window") is True
        out = combat_service.resolve_reaction(1, "take")
    assert out["damage"] == 7
    assert out["player_hp_remaining"] == 13


def test_resolve_attack_no_skill_no_reaction(tmp_path, monkeypatch):
    """Skill-gated: pre-deklaracja bez skilla dodge → reakcja niedostępna, normalne obrażenia."""
    db = _combat_db(tmp_path, declared="dodge", skill_rank=0)
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 18)
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 7)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, 0, attacker="enemy")
    assert out.get("reaction") is None or out.get("reaction", {}).get("available") is not True
    assert out["damage"] == 7


def test_resolve_attack_enemy_roll_untouched(tmp_path, monkeypatch):
    """Rzut ataku wroga raportowany bez zmian — reakcja nie dotyka mechaniki ataku."""
    db = _combat_db(tmp_path, declared="dodge", skill_rank=2)
    monkeypatch.setattr(combat_service, "roll_d20", lambda: 18)
    monkeypatch.setattr(combat_service, "roll_damage_dice", lambda *a, **k: 7)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        out = combat_service.resolve_attack(1, 0, attacker="enemy")
    # raw d20 wroga = 18, attack_roll = 18 + attack_bonus 10 = 28 (nietknięte mimo uniku)
    assert out["raw_d20"] == 18
    assert out["attack_roll"] == 28


# ─── declare_player_reaction (toggle, skill-gate, tura gracza) ────────────────

def test_declare_reaction_toggles_and_persists(tmp_path):
    """Pre-deklaracja ustawia flagę; ponowne wywołanie tego samego typu ją zdejmuje."""
    db = _combat_db(tmp_path, declared=None, skill_rank=1)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        # tura gracza wymagana — przestaw current_turn
        conn = sqlite3.connect(str(db))
        conn.execute("UPDATE active_combat SET current_turn='player' WHERE campaign_id=1")
        conn.commit(); conn.close()
        r1 = combat_service.declare_player_reaction(1, "dodge")
        assert r1["reaction_declared"] == "dodge"
        r2 = combat_service.declare_player_reaction(1, "dodge")
        assert r2["reaction_declared"] is None       # toggle off


def test_declare_reaction_requires_skill(tmp_path):
    """Bez skilla dodge rank ≥ 1 deklaracja odrzucona (ValueError → 400 w API)."""
    db = _combat_db(tmp_path, declared=None, skill_rank=0)
    with patch.object(combat_service, "COMBAT_DB_PATH", str(db)):
        conn = sqlite3.connect(str(db))
        conn.execute("UPDATE active_combat SET current_turn='player' WHERE campaign_id=1")
        conn.commit(); conn.close()
        with pytest.raises(ValueError):
            combat_service.declare_player_reaction(1, "dodge")
