"""TDD: Issue #372 — Opening scene always in forest: build_opening_plan_context helper.

Tests verify:
- Arc with title + roadmap + locations → correct _plan_ctx built
- Roadmap truncated at 200 chars
- Locations capped at max 3
- No title AND no locations → empty context (condition: if arc_title or arc_locs)
- None / empty gm_plan_json → empty string, no crash
- Invalid JSON → empty string, no crash
- "NIE las" instruction present in non-empty context
- Identical logic used in both characters.py and turns.py code paths
"""
import sys
import json
sys.path.insert(0, "/app")


# ─── Helper import ───────────────────────────────────────────────────────────

def _build(gm_plan_json):
    """Import the helper — will fail (RED) until we create it."""
    from app.services.opening_context import build_opening_plan_context
    return build_opening_plan_context(gm_plan_json)


def _make_plan(arc_title="", roadmap="", locations=None, arc_id="arc1"):
    """Build a gm_plan_json string for testing."""
    arc = {"title": arc_title, "roadmap": roadmap, "hooks": {"locations": locations or []}}
    plan = {"active_arc_id": arc_id, "arcs": {arc_id: arc}}
    return json.dumps(plan)


# ─── Core: context building ───────────────────────────────────────────────────

def test_build_context_includes_arc_title():
    """Arc title must appear in the built context string."""
    plan = _make_plan(arc_title="Tajemnica Czarnego Zamku", roadmap="Bohater odkrywa tajemnicę.")
    ctx = _build(plan)
    assert "Tajemnica Czarnego Zamku" in ctx, (
        f"Tytuł wątku 'Tajemnica Czarnego Zamku' musi być w kontekście.\nGot: {ctx!r}"
    )


def test_build_context_includes_roadmap():
    """Arc roadmap must appear (up to 200 chars) in the built context string."""
    plan = _make_plan(arc_title="Wątek", roadmap="Bohater szuka zaginionego króla w mrocznych katakumbach.")
    ctx = _build(plan)
    assert "Bohater szuka zaginionego króla" in ctx, (
        f"Zarys fabuły (roadmap) musi być w kontekście.\nGot: {ctx!r}"
    )


def test_build_context_includes_locations():
    """Arc hook locations must appear in the built context string."""
    plan = _make_plan(arc_title="Wątek", locations=["Karczma Pod Złotą Beczkę", "Rynek Miejski"])
    ctx = _build(plan)
    assert "Karczma Pod Złotą Beczkę" in ctx, (
        f"Sugerowane lokacje muszą być w kontekście.\nGot: {ctx!r}"
    )
    assert "Rynek Miejski" in ctx, (
        f"Druga lokacja też musi być w kontekście.\nGot: {ctx!r}"
    )


def test_build_context_roadmap_truncated_at_200():
    """Roadmap longer than 200 chars must be truncated to 200 chars."""
    long_roadmap = "X" * 300
    plan = _make_plan(arc_title="Wątek", roadmap=long_roadmap)
    ctx = _build(plan)
    # The 200-char slice means we see 200 X's but not 300
    assert "X" * 200 in ctx, "Pierwsze 200 znaków roadmap musi być w kontekście"
    assert "X" * 201 not in ctx, (
        "Roadmap dłuższy niż 200 znaków musi być przycięty. "
        f"Znaleziono więcej niż 200 znaków 'X' w kontekście."
    )


def test_build_context_locations_capped_at_3():
    """More than 3 locations must be capped at 3 in the context."""
    locs = ["Loc1", "Loc2", "Loc3", "Loc4", "Loc5"]
    plan = _make_plan(arc_title="Wątek", locations=locs)
    ctx = _build(plan)
    assert "Loc1" in ctx
    assert "Loc2" in ctx
    assert "Loc3" in ctx
    assert "Loc4" not in ctx, (
        f"Czwarta lokacja (Loc4) NIE powinna być w kontekście — cap to 3.\nGot: {ctx!r}"
    )
    assert "Loc5" not in ctx, "Piąta lokacja też nie może być w kontekście"


def test_build_context_nie_las_instruction_included():
    """Non-empty context must include the 'NIE las' instruction."""
    plan = _make_plan(arc_title="Miejska Intryga", locations=["Karczma"])
    ctx = _build(plan)
    assert "NIE las" in ctx, (
        f"Kontekst musi zawierać instrukcję 'NIE las jeśli fabuła tego nie wymaga'.\nGot: {ctx!r}"
    )


def test_build_context_includes_kampanii_header():
    """Non-empty context must start with 'Kontekst kampanii:' header."""
    plan = _make_plan(arc_title="Jakiś Wątek")
    ctx = _build(plan)
    assert "Kontekst kampanii:" in ctx, (
        f"Kontekst musi zawierać nagłówek 'Kontekst kampanii:'.\nGot: {ctx!r}"
    )


# ─── Edge cases: empty / no context ──────────────────────────────────────────

def test_build_context_no_title_no_locations_returns_empty():
    """Arc with only roadmap (no title, no locations) must return empty string."""
    plan = _make_plan(arc_title="", roadmap="Jakiś zarys.", locations=[])
    ctx = _build(plan)
    assert ctx == "", (
        f"Brak tytułu i brak lokacji → kontekst musi być pusty (condition: if arc_title or arc_locs).\n"
        f"Got: {ctx!r}"
    )


def test_build_context_none_returns_empty():
    """None gm_plan_json must return empty string without raising."""
    ctx = _build(None)
    assert ctx == "", f"None → pusty string. Got: {ctx!r}"


def test_build_context_empty_string_returns_empty():
    """Empty string gm_plan_json must return empty string without raising."""
    ctx = _build("")
    assert ctx == "", f"Pusty string → pusty string. Got: {ctx!r}"


def test_build_context_invalid_json_returns_empty():
    """Invalid JSON must return empty string without raising (same as try/except pass)."""
    ctx = _build("not valid json{{{")
    assert ctx == "", f"Zepsuty JSON → pusty string. Got: {ctx!r}"


def test_build_context_plan_with_no_arcs_returns_empty():
    """Plan JSON with empty arcs dict must return empty string."""
    plan = json.dumps({"active_arc_id": "arc1", "arcs": {}})
    ctx = _build(plan)
    assert ctx == "", f"Pusty arcs dict → pusty string. Got: {ctx!r}"


def test_build_context_returns_string_always():
    """Return type must always be str, never None or other type."""
    for gm_plan in [None, "", "bad json", _make_plan()]:
        result = _build(gm_plan)
        assert isinstance(result, str), (
            f"build_opening_plan_context musi zawsze zwracać str, nie {type(result)}"
        )


# ─── Backward compat: no crash with partial arcs ─────────────────────────────

def test_build_context_arc_without_hooks_key():
    """Arc without 'hooks' key must not crash."""
    plan = json.dumps({
        "active_arc_id": "arc1",
        "arcs": {"arc1": {"title": "Test Wątek", "roadmap": "Opis."}}
    })
    ctx = _build(plan)
    assert "Test Wątek" in ctx, f"Brak klucza 'hooks' nie może zepsuć kontekstu.\nGot: {ctx!r}"


def test_build_context_arc_with_none_hooks():
    """Arc with hooks=None must not crash."""
    plan = json.dumps({
        "active_arc_id": "arc1",
        "arcs": {"arc1": {"title": "Wątek", "hooks": None}}
    })
    ctx = _build(plan)
    assert "Wątek" in ctx, f"hooks=None nie może zepsuć kontekstu.\nGot: {ctx!r}"


def test_build_context_uses_first_arc_when_active_arc_id_missing():
    """When active_arc_id is missing, must fall back to first arc in dict."""
    plan = json.dumps({
        "arcs": {"arc_first": {"title": "Pierwszy Wątek", "roadmap": "Opis."}}
    })
    ctx = _build(plan)
    assert "Pierwszy Wątek" in ctx, (
        f"Bez active_arc_id powinno użyć pierwszego arca.\nGot: {ctx!r}"
    )
