"""TDD: Issue #1134 (PT-D5) — reputacja frakcji w encounterze straży (guard_check).

Encounter `guard_check` (targ) różnicuje wynik wg reputacji frakcji straży (#1103):
  - wroga frakcja (rep ≤ -20)  → rewizja + grzywna przy PORAŻCE (strata złota),
  - neutralna (-20..+20)       → standardowy wynik testu (bez dodatkowej kary),
  - przyjazna (rep ≥ +20)      → auto-pass: straż macha ręką (hook, zero kosztu).

Rdzeń jest CZYSTY: `faction_guard_outcome(reputation_value, gold, skill_check)`
przyjmuje wartość reputacji + złoto + wynik testu i zwraca konsekwencję. Progi
attitude reużywają `reputation_service.npc_attitude_from_reputation` (spójność z #1103).

Brak danych frakcji → wołający podaje reputation_value=0 → 'neutral' fallback,
nic się nie psuje. Konsekwencje MIĘKKIE (złoto) — walka to wyjątek (Nat 1).

Testy in-memory / czyste funkcje — nie dotykają /data/ai_gm.db.
"""
import random
import sqlite3

import pytest

from app.services import social_encounter_service as ses
from app.services import encounter_catalog_service as cat


# ─── Główne: 3 progi reputacji → 3 różne konsekwencje ─────────────────────────

def test_guard_check_three_reputation_tiers_three_consequences():
    """Acceptance: 3 progi reputacji frakcji → 3 różne konsekwencje guard_check."""
    fail = {"success": False, "escalate_combat": False}
    gold = 200

    hostile = ses.faction_guard_outcome(-30, gold, fail)   # wroga
    neutral = ses.faction_guard_outcome(0, gold, fail)     # neutralna
    friendly = ses.faction_guard_outcome(30, gold, fail)   # przyjazna

    # trzy różne postawy
    assert hostile["attitude"] == "hostile"
    assert neutral["attitude"] == "neutral"
    assert friendly["attitude"] == "friendly"

    # trzy różne konsekwencje na TYM SAMYM (nieudanym) teście:
    #  wroga  → grzywna (strata złota), brak auto-pass
    assert hostile["gold_loss"] > 0
    assert hostile["auto_pass"] is False
    #  neutralna → standard: porażka, ale bez grzywny
    assert neutral["gold_loss"] == 0
    assert neutral["auto_pass"] is False
    #  przyjazna → auto-pass mimo nieudanego testu, zero kosztu
    assert friendly["gold_loss"] == 0
    assert friendly["auto_pass"] is True
    assert friendly["success"] is True

    # rozstrzygnięcia są rozróżnialne
    assert len({hostile["resolution"], neutral["resolution"], friendly["resolution"]}) == 3


def test_guard_check_hostile_success_no_fine():
    """Wroga frakcja + UDANY test → przepuszczenie (burkliwie), bez grzywny."""
    ok = {"success": True, "escalate_combat": False}
    out = ses.faction_guard_outcome(-40, 200, ok)
    assert out["attitude"] == "hostile"
    assert out["gold_loss"] == 0
    assert out["success"] is True


def test_guard_fine_pct_and_cap():
    """Grzywna = 10% złota w dół, cap, nieujemna."""
    assert ses.guard_fine(200) == min(20, ses.GUARD_FINE_CAP)
    assert ses.guard_fine(0) == 0
    assert ses.guard_fine(-5) == 0
    # cap
    assert ses.guard_fine(100000) == ses.GUARD_FINE_CAP


def test_catalog_row_exposes_faction_tag():
    """PT-D5: rekord social z katalogu przenosi faction_tag do struktury silnika."""
    row = {
        "key": "guard_check",
        "faction_tag": "straz_miejska",
        "payload": {"stat": "CHA", "skill": "persuasion", "dc": 12, "resolution_kind": "soft"},
    }
    ev = ses._event_from_catalog_row(row)
    assert ev["faction_tag"] == "straz_miejska"
    assert ev["key"] == "guard_check"


# ─── Backward compatibility ───────────────────────────────────────────────────

def test_no_faction_data_neutral_fallback():
    """Brak danych frakcji (rep=0) → neutralny fallback: standardowy wynik testu."""
    fail = {"success": False, "escalate_combat": False}
    out = ses.faction_guard_outcome(0, 200, fail)
    assert out["attitude"] == "neutral"
    assert out["gold_loss"] == 0
    assert out["auto_pass"] is False
    # sukces bez zmian przy neutralnej
    ok = {"success": True, "escalate_combat": False}
    assert ses.faction_guard_outcome(0, 200, ok)["success"] is True


def test_existing_social_pool_unaffected():
    """Inne zdarzenia społeczne (pickpocket) działają bez zmian — brak regresji."""
    ev = ses.pick_social_event("alley", roll=0.0)
    assert ev["key"] in ("pickpocket", "drunk_harassment")
    # hardcode event nie ma faction_tag (None) — nie psuje starego kształtu
    assert ev.get("faction_tag") is None


def test_hardcode_guard_check_still_soft():
    """guard_check z hardcode nadal kind='soft' (definicja bez zmian)."""
    ev = dict(ses._EVENT_DEFS["guard_check"])
    assert ev["kind"] == "soft"
    assert ev["skill"] == "persuasion"


# ── PT-F6 #1140: guard_check carries faction_tag (PT-D5 no longer dormant) ──────

def test_ptf6_guard_check_has_faction_tag():
    from app.services import social_encounter_service as ses
    assert ses._EVENT_DEFS["guard_check"].get("faction_tag") == "zakon_straznikow"
    # hardcode fallback path surfaces it
    ev = dict(ses._EVENT_DEFS["guard_check"]); ev["key"] = "guard_check"
    assert ev.get("faction_tag") == "zakon_straznikow"


# ── PT-F6 #1140: validate_fk rejects hallucinated stat / npc_key ────────────────

def _fk_db():
    import sqlite3, json
    c = sqlite3.connect(":memory:"); c.row_factory = sqlite3.Row
    c.executescript(
        "CREATE TABLE game_config_skills (key TEXT);"
        "CREATE TABLE game_config_enemies (key TEXT);"
        "CREATE TABLE npcs (key TEXT);"
    )
    c.execute("INSERT INTO game_config_skills (key) VALUES ('persuasion')")
    c.execute("INSERT INTO npcs (key) VALUES ('kowal_bartek')")
    c.commit()
    return c


def test_ptf6_validate_fk_rejects_bad_stat():
    import pytest
    from app.services.encounter_catalog_service import validate_fk
    c = _fk_db()
    with pytest.raises(ValueError):
        validate_fk(c, kind="social", payload={"skill": "persuasion", "stat": "ZZZ"})


def test_ptf6_validate_fk_accepts_good_stat_and_npc():
    from app.services.encounter_catalog_service import validate_fk
    c = _fk_db()
    # should not raise
    validate_fk(c, kind="social", payload={"skill": "persuasion", "stat": "CHA", "npc_key": "kowal_bartek"})


def test_ptf6_validate_fk_rejects_bad_npc():
    import pytest
    from app.services.encounter_catalog_service import validate_fk
    c = _fk_db()
    with pytest.raises(ValueError):
        validate_fk(c, kind="social", payload={"skill": "persuasion", "npc_key": "nieistniejacy_npc"})
