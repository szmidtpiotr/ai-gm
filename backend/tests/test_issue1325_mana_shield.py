"""TDD: Issue #1325 — Tarcza Many (mana_shield): reakcja instant maga w oknie SF10.

Odpowiednik Bloku wojownika, ale DETERMINISTYCZNY (bez rzutu). Mag „przyjmuje cios w manę
zamiast w ciało". Model CAP:
  • twardy limit wydatku many na cios = 2 × rank (`MANA_SHIELD_LIMIT_PER_RANK`, start 2),
  • przelicznik R = 2 obr./1 mana (`MANA_SHIELD_ABSORB_PER_MANA`, start 2),
  • tarcza pochłania `min(dmg_finalne, limit × rank × R)`,
  • mag płaci `ceil(pochłonięte / R)` — TYLKO za faktycznie wykorzystaną absorpcję.
Punkt w potoku: OSTATNI — PO modelu #826 (margines + pancerz) i po absorpcji B10, tuż przed HP.
Gate: skill `mana_shield` rank ≥ 1 ORAZ current_mana > 0. Limit: 1/rundę ZAWSZE (także 1 wróg).
Brak rzutu → brak crit-fail → brak lockoutu.
"""
import importlib

import pytest

cs = importlib.import_module("app.services.combat_service")


# ─── Helper _try_mana_shield_reaction ────────────────────────────────────────

def _mk(mana=10, rank=1, declared="mana_shield"):
    """Combatant gracza + sheet ze skillem mana_shield i pulą many."""
    p = {"id": "player", "hp_current": 20, "stats": {"INT": 14}}
    if declared:
        p["reaction_declared"] = declared
    sheet = {"stats": {"INT": 14}, "skills": {"mana_shield": rank}, "current_mana": mana}
    return p, sheet


def test_mana_shield_partial_absorb_caps_at_limit():
    """Cios 10 obr. finalnych, rank 1 (limit 2 many → 4 obr.): pochłania 4, płaci 2 many.

    HP: dmg_after = 10 − 4 = 6. Mana: 10 − 2 = 8.
    """
    p, sheet = _mk(mana=10, rank=1)
    res = cs._try_mana_shield_reaction(p, sheet, dmg=10, round_n=1)
    assert res is not None and res.get("available") is True
    assert int(res.get("absorbed")) == 4
    assert int(res.get("damage_after")) == 6
    assert int(res.get("mana_spent")) == 2
    assert int(sheet["current_mana"]) == 8


def test_mana_shield_full_absorb_pays_only_used():
    """Cios 3 obr. finalnych, rank 1: pochłania 3 (poniżej capu 4), płaci ceil(3/2)=2 many, HP −0."""
    p, sheet = _mk(mana=10, rank=1)
    res = cs._try_mana_shield_reaction(p, sheet, dmg=3, round_n=1)
    assert res is not None and res.get("available") is True
    assert int(res.get("absorbed")) == 3
    assert int(res.get("damage_after")) == 0
    assert int(res.get("mana_spent")) == 2  # ceil(3/2)
    assert int(sheet["current_mana"]) == 8


def test_mana_shield_one_damage_pays_one_mana():
    """Cios 1 obr.: pochłania 1, płaci ceil(1/2)=1 manę, HP −0."""
    p, sheet = _mk(mana=10, rank=1)
    res = cs._try_mana_shield_reaction(p, sheet, dmg=1, round_n=1)
    assert res is not None and res.get("available") is True
    assert int(res.get("absorbed")) == 1
    assert int(res.get("damage_after")) == 0
    assert int(res.get("mana_spent")) == 1
    assert int(sheet["current_mana"]) == 9


def test_mana_shield_crit_capped_pool_not_drained():
    """Nat 20 wroga (duże finalne obrażenia) — cap chroni pulę: rank 1 wydaje max 2 many."""
    p, sheet = _mk(mana=10, rank=1)
    res = cs._try_mana_shield_reaction(p, sheet, dmg=40, round_n=1)
    assert res is not None and res.get("available") is True
    assert int(res.get("absorbed")) == 4        # limit 2 many × R2
    assert int(res.get("mana_spent")) == 2       # nie więcej niż cap
    assert int(res.get("damage_after")) == 36
    assert int(sheet["current_mana"]) == 8       # pula NIE zjechana poniżej limitu


def test_mana_shield_rank2_higher_limit():
    """Rank 2 → limit 4 many → 8 obr. pochłonięte przy cios 10: HP −2, mana −4."""
    p, sheet = _mk(mana=10, rank=2)
    res = cs._try_mana_shield_reaction(p, sheet, dmg=10, round_n=1)
    assert int(res.get("absorbed")) == 8
    assert int(res.get("damage_after")) == 2
    assert int(res.get("mana_spent")) == 4
    assert int(sheet["current_mana"]) == 6


def test_mana_shield_low_mana_limited_by_pool():
    """Mag ma tylko 1 manę — pochłania max R×1 = 2 obr., płaci 1 manę (pula < cap)."""
    p, sheet = _mk(mana=1, rank=1)
    res = cs._try_mana_shield_reaction(p, sheet, dmg=10, round_n=1)
    assert int(res.get("absorbed")) == 2
    assert int(res.get("mana_spent")) == 1
    assert int(res.get("damage_after")) == 8
    assert int(sheet["current_mana"]) == 0


def test_mana_shield_no_mana_unavailable():
    """0 many → reakcja niedostępna (available=False), obrażenia bez zmian."""
    p, sheet = _mk(mana=0, rank=1)
    res = cs._try_mana_shield_reaction(p, sheet, dmg=10, round_n=1)
    assert res is None or res.get("available") is False
    assert int(sheet["current_mana"]) == 0


def test_mana_shield_no_skill_returns_none():
    """Brak skilla mana_shield → helper zwraca None, mana nietknięta."""
    p, sheet = _mk(mana=10, rank=0)
    res = cs._try_mana_shield_reaction(p, sheet, dmg=10, round_n=1)
    assert res is None
    assert int(sheet["current_mana"]) == 10


def test_mana_shield_zero_damage_no_cost():
    """Obrażenia już zjedzone (dmg=0, np. przez pancerz/absorpcję) → mana nie schodzi."""
    p, sheet = _mk(mana=10, rank=1)
    res = cs._try_mana_shield_reaction(p, sheet, dmg=0, round_n=1)
    assert res is None or int(res.get("mana_spent") or 0) == 0
    assert int(sheet["current_mana"]) == 10


# ─── _reaction_options gate + 1/rundę ZAWSZE ─────────────────────────────────

def test_reaction_options_includes_mana_shield_when_skill_and_mana():
    """Okno reakcji pokazuje 'mana_shield' gdy skill ≥ 1 i mana > 0."""
    p = {"id": "player"}
    sheet = {"skills": {"mana_shield": 1}, "current_mana": 5}
    opts = cs._reaction_options(None, 1, p, sheet, round_n=1, enemy_count=1)
    assert "mana_shield" in opts


def test_reaction_options_excludes_mana_shield_without_mana():
    """0 many → 'mana_shield' nie pojawia się w oknie."""
    p = {"id": "player"}
    sheet = {"skills": {"mana_shield": 1}, "current_mana": 0}
    opts = cs._reaction_options(None, 1, p, sheet, round_n=1, enemy_count=1)
    assert "mana_shield" not in opts


def test_mana_shield_one_per_round_even_single_enemy():
    """1/rundę ZAWSZE (także 1 wróg): po zużyciu reakcji w tej rundzie tarcza znika z opcji.

    Odstępstwo od #1322 — przy jednym wrogu Unik/Bariera pozostają co atak, ale Tarcza NIE.
    """
    p = {"id": "player", "reaction_used_round": 1}
    sheet = {"skills": {"mana_shield": 1, "dodge": 1}, "current_mana": 5}
    opts = cs._reaction_options(None, 1, p, sheet, round_n=1, enemy_count=1)
    assert "mana_shield" not in opts    # 1/rundę egzekwowane mimo single-enemy
    assert "dodge" in opts               # Unik wg #1322 nadal dostępny co atak


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_arcane_ward_still_works(monkeypatch):
    """Bariera INT (#1324) działa bez zmian — nie zepsuliśmy siostrzanej reakcji."""
    monkeypatch.setattr(cs, "roll_d20", lambda: 20)
    p = {"id": "player", "reaction_declared": "arcane_ward", "stats": {"INT": 14}}
    sheet = {"stats": {"INT": 14}, "skills": {"arcane_ward": 1}, "current_mana": 10}
    res = cs._try_arcane_ward_reaction(p, sheet, attack_roll=12, round_n=1)
    assert res is not None and res.get("warded") is True


def test_reaction_options_warrior_no_mana_shield():
    """Wojownik bez skilla mana_shield nie widzi tarczy w oknie; Unik zostaje."""
    p = {"id": "player"}
    sheet = {"skills": {"dodge": 1}, "current_mana": 0}
    opts = cs._reaction_options(None, 1, p, sheet, round_n=1, enemy_count=1)
    assert "mana_shield" not in opts
    assert "dodge" in opts
