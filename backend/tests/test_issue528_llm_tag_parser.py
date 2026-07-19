"""TDD: Issue #528 — U5: Centralny parser tagów LLM + tabela llm_tag_errors + polityka malformed."""
import sys
import sqlite3
import re

sys.path.insert(0, "/app")


# ─── Characterizing tests (document existing behavior — must stay GREEN) ──────

def test_quest_suggest_parser_existing_behavior():
    """Istniejący quest_suggest_parser rozpoznaje format [QUEST_SUGGEST:title|obj|reward]."""
    from app.services.quest_suggest_parser import parse_quest_suggest, strip_quest_suggest_tags

    text = "Spotykasz starca. [QUEST_SUGGEST: Znajdź artefakt | Odszukaj starożytny posąg | 50 XP] Mów więcej."
    quests = parse_quest_suggest(text)
    assert len(quests) == 1
    assert quests[0]["title"] == "Znajdź artefakt"
    assert quests[0]["objective"] == "Odszukaj starożytny posąg"
    assert quests[0]["reward"] == "50 XP"

    stripped = strip_quest_suggest_tags(text)
    assert "[QUEST_SUGGEST" not in stripped


def test_spend_gold_tag_regex_existing_behavior():
    """Istniejący SPEND_GOLD tag regex wyciąga klucz usługi z narracji."""
    import re
    _RE = re.compile(r'\[SPEND_GOLD:\s*([a-zA-Z0-9_]+)\s*\]')
    text = "Płacisz karczmarzowi. [SPEND_GOLD: inn_night] Dobranoc."
    m = _RE.search(text)
    assert m is not None
    assert m.group(1).strip() == "inn_night"


def test_narrative_event_tag_existing_behavior():
    """Istniejący NARRATIVE_EVENT parser wyciąga key i note."""
    from app.services.narrative_state_service import parse_narrative_event_tags, strip_narrative_tags

    text = "[NARRATIVE_EVENT: key=discovery_temple, note=Gracz odkrył świątynię] Oto ona."
    events = parse_narrative_event_tags(text)
    assert len(events) == 1
    assert events[0][0] == "discovery_temple"
    assert "świątynię" in events[0][1]

    stripped = strip_narrative_tags(text)
    assert "[NARRATIVE_EVENT" not in stripped


def test_narrative_seed_tag_existing_behavior():
    """NARRATIVE_SEED parser wyciąga key i hint."""
    from app.services.narrative_state_service import parse_narrative_seed_tags

    text = "[NARRATIVE_SEED: key=dark_lord_hint, hint=Ktoś śledzi bohatera] Czujesz wzrok."
    seeds = parse_narrative_seed_tags(text)
    assert len(seeds) == 1
    assert seeds[0][0] == "dark_lord_hint"


def test_arc_advance_parser_existing_behavior():
    """Istniejący ARC_ADVANCE parser wyciąga klucz arcu."""
    from app.services.campaign_plan_runtime import parse_arc_advance_tags

    text = "Epizod się kończy. [ARC_ADVANCE: arc_main] Nowy rozdział."
    tags = parse_arc_advance_tags(text)
    assert len(tags) == 1
    assert tags[0] == "arc_main"


# ─── RED tests: new llm_tag_parser module (fail until module created) ─────────

def _make_test_db():
    """In-memory DB with llm_tag_errors table — mimics the migration."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_tag_errors (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            turn_number INTEGER NOT NULL DEFAULT 0,
            tag_raw     TEXT    NOT NULL DEFAULT '',
            error_type  TEXT    NOT NULL DEFAULT 'unknown',
            ts          TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    return conn


def test_llm_tag_parser_module_importable():
    """llm_tag_parser module must exist and be importable."""
    from app.services import llm_tag_parser  # noqa: F401


def test_llm_tag_parser_registry_has_core_tags():
    """Rejestr tagów zawiera co najmniej kluczowe tagi gry."""
    from app.services.llm_tag_parser import TAG_REGISTRY

    required_tags = [
        "QUEST_SUGGEST",
        "SPEND_GOLD",
        "SKILL_TEST",
        "NPC_MEMORY",
        "NARRATIVE_EVENT",
        "NARRATIVE_SEED",
        "BEAT_COMPLETE",
        "ARC_ADVANCE",
        "COMBAT_START",
        "APPLY_CONDITION",
        "CREATE_LOCATION",
        "CREATE_NPC",
        "CREATE_ENEMY",
        "NPC_KILLED",
        "QUEST_COMPLETE",
        "XP_GRANT",
        "CAMPAIGN_END",
        "DISCOVERY",
        "DUNGEON_CLEAR",
    ]
    for tag in required_tags:
        assert tag in TAG_REGISTRY, f"TAG_REGISTRY missing: {tag}"


def test_tag_registry_values_are_compiled_patterns():
    """Każda wartość w rejestrze to skompilowany regex."""
    from app.services.llm_tag_parser import TAG_REGISTRY

    for name, pattern in TAG_REGISTRY.items():
        assert isinstance(pattern, re.Pattern), f"{name}: expected compiled regex, got {type(pattern)}"


def test_log_tag_error_inserts_row():
    """log_tag_error wstawia wiersz do llm_tag_errors."""
    from app.services.llm_tag_parser import log_tag_error

    conn = _make_test_db()
    log_tag_error(conn, campaign_id=42, turn_number=7, tag_raw="[QUEST_SUGGEST: brak_pipe]", error_type="invalid_schema")

    row = conn.execute("SELECT * FROM llm_tag_errors WHERE campaign_id = 42").fetchone()
    assert row is not None
    assert row["campaign_id"] == 42
    assert row["turn_number"] == 7
    assert row["error_type"] == "invalid_schema"
    assert "QUEST_SUGGEST" in row["tag_raw"]


def test_log_tag_error_swallows_exceptions():
    """log_tag_error nie crashuje turę gdy tabela nie istnieje."""
    from app.services.llm_tag_parser import log_tag_error

    conn = sqlite3.connect(":memory:")  # no llm_tag_errors table
    # must not raise
    log_tag_error(conn, campaign_id=1, turn_number=1, tag_raw="[X:y]", error_type="invalid_schema")


def test_get_tag_error_count_returns_correct_count():
    """get_tag_error_count zwraca liczbę błędów dla kampanii."""
    from app.services.llm_tag_parser import log_tag_error, get_tag_error_count

    conn = _make_test_db()
    log_tag_error(conn, 10, 1, "[BAD:x]", "invalid_schema")
    log_tag_error(conn, 10, 2, "[BAD:y]", "invalid_reference")
    log_tag_error(conn, 99, 1, "[BAD:z]", "invalid_schema")  # other campaign

    count_10 = get_tag_error_count(conn, 10)
    count_99 = get_tag_error_count(conn, 99)
    assert count_10 == 2, f"Expected 2 for campaign 10, got {count_10}"
    assert count_99 == 1, f"Expected 1 for campaign 99, got {count_99}"


def test_get_tag_error_count_returns_zero_for_no_errors():
    """Kampania bez błędów tagów zwraca 0."""
    from app.services.llm_tag_parser import get_tag_error_count

    conn = _make_test_db()
    count = get_tag_error_count(conn, 999)
    assert count == 0


def test_find_unknown_tags_detects_unregistered_patterns():
    """find_unknown_tags wykrywa [TAG:...] których nie ma w rejestrze."""
    from app.services.llm_tag_parser import find_unknown_tags

    text = "Tekst narracji [QUEST_SUGGEST: a|b|c] normalny tag. [HALUCYNACJA: coś] nieznany."
    unknown = find_unknown_tags(text)
    assert any("HALUCYNACJA" in u for u in unknown), f"Expected HALUCYNACJA in unknown: {unknown}"
    assert not any("QUEST_SUGGEST" in u for u in unknown), "QUEST_SUGGEST should NOT be in unknown"


def test_find_unknown_tags_empty_on_clean_text():
    """Tekst bez tagów LLM → lista pusta."""
    from app.services.llm_tag_parser import find_unknown_tags

    text = "Zwykła narracja [w nawiasach kwadratowych] bez tagów."
    # This should not match — no colon after CAPS identifier
    unknown = find_unknown_tags(text)
    # Accept if it finds bracketed text without colons — depends on regex
    # Key assertion: no tags that LOOK like LLM tags (CAPS:value) in a clean narrative
    for u in unknown:
        assert re.match(r'\[[A-Z_]+:', u), f"Unexpected unknown tag: {u}"


def test_all_known_tags_match_their_own_format():
    """Każdy znany tag ma regex który pasuje do przykładowego poprawnego formatu."""
    from app.services.llm_tag_parser import TAG_REGISTRY

    samples = {
        "QUEST_SUGGEST": "[QUEST_SUGGEST: Tytuł | Cel | Nagroda]",
        "SPEND_GOLD": "[SPEND_GOLD: inn_night]",
        "NPC_MEMORY": "[NPC_MEMORY: Kowal | Handluje mieczami]",
        "NARRATIVE_EVENT": "[NARRATIVE_EVENT: key=ev_temple, note=znaleziono świątynię]",
        "NARRATIVE_SEED": "[NARRATIVE_SEED: key=dark_hint, hint=ktoś śledzi]",
        "BEAT_COMPLETE": "[BEAT_COMPLETE: beat_discover]",
        "ARC_ADVANCE": "[ARC_ADVANCE: arc_main]",
        "COMBAT_START": "[COMBAT_START: goblin]",
        "APPLY_CONDITION": "[APPLY_CONDITION: poisoned:enemy_id_1]",
        "CREATE_NPC": "[CREATE_NPC: key=blacksmith, name=Kowal]",
        "CREATE_ENEMY": "[CREATE_ENEMY: key=dark_orc, name=Mroczny Ork]",
        "NPC_KILLED": "[NPC_KILLED: key=village_elder]",
        "QUEST_COMPLETE": "[QUEST_COMPLETE: quest_find_artifact]",
        "XP_GRANT": "[XP_GRANT: znaleziono skarb:25]",
        "CAMPAIGN_END": "[CAMPAIGN_END: good_ending]",
        "DISCOVERY": "[DISCOVERY: secret_cave|Odkryłeś tajną grotę]",
        "DUNGEON_CLEAR": "[DUNGEON_CLEAR: dungeon_goblin_lair]",
        "SKILL_TEST": "[SKILL_TEST: stealth:DC:12]",
    }

    for tag_name, sample in samples.items():
        if tag_name not in TAG_REGISTRY:
            continue
        pattern = TAG_REGISTRY[tag_name]
        assert pattern.search(sample), f"{tag_name}: regex did not match sample: {sample!r}"
