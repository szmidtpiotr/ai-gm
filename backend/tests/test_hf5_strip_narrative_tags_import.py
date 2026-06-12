"""Regression: Issue #536 — HF-5: strip_narrative_tags was imported from xp_sources (wrong),
must come from narrative_state_service. Cichy fail blokował XP hooks w każdej turze."""
import importlib
import sys

sys.path.insert(0, "/app")


def test_strip_narrative_tags_in_narrative_state_service():
    """strip_narrative_tags must be importable from narrative_state_service."""
    from app.services.narrative_state_service import strip_narrative_tags
    assert callable(strip_narrative_tags)


def test_strip_narrative_tags_not_in_xp_sources():
    """strip_narrative_tags must NOT be in xp_sources — that was the bug."""
    import importlib
    mod = importlib.import_module("app.services.xp_sources")
    assert not hasattr(mod, "strip_narrative_tags"), (
        "strip_narrative_tags should not be exported from xp_sources; "
        "it lives in narrative_state_service"
    )


def test_strip_narrative_tags_removes_tags():
    """Smoke: function strips [NARRATIVE_EVENT:...] and [NARRATIVE_SEED:...] tags."""
    from app.services.narrative_state_service import strip_narrative_tags
    text = "Dotarłeś do wioski. [NARRATIVE_EVENT: key=village_found, note=gracz dotarł] Ludzie są przerażeni."
    result = strip_narrative_tags(text)
    assert "[NARRATIVE_EVENT:" not in result
    assert "Dotarłeś do wioski" in result
    assert "Ludzie są przerażeni" in result


def test_xp_sources_imports_work():
    """All names that turns.py imports from xp_sources must exist there."""
    from app.services.xp_sources import (
        process_narrative_xp_tags,
        grant_first_location_visit,
        grant_first_npc_talk,
        grant_session_start,
        grant_beat_complete,
    )
    for fn in (process_narrative_xp_tags, grant_first_location_visit,
               grant_first_npc_talk, grant_session_start, grant_beat_complete):
        assert callable(fn)
