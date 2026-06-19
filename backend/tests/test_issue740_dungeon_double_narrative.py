"""TDD: Issue #740 — dungeon entry shows double narrative (LLM_OPEN + room_narrative).

Backend guard: _inject_dungeon_loch_context must inject room description into LLM
messages so the __AI_GM_OPEN turn produces a complete room narrative. This makes
the separate room_narrative append in frontend redundant and removable.

The primary RED test is the Playwright spec (counts UI message blocks).
"""
import sys, json

sys.path.insert(0, "/app")

from app.services.game_engine import _inject_dungeon_loch_context


def _make_run(room_description="Zimna komnata o wilgotnych ścianach.", doors=None, enemies=None, cleared=False):
    return {
        "system": "tiles_v2",
        "completed": False,
        "failed": False,
        "graph": {
            "entry_node": "n0",
            "nodes": {
                "n0": {
                    "content": {
                        "room_description": room_description,
                        "label": "Krypta Próbna",
                        "enemies": enemies or [],
                    },
                    "doors_open": doors or {"N": True},
                    "door_hints": {"N": "stare drzwi"},
                    "cleared": cleared,
                }
            },
        },
        "positions": {"player": "n0"},
    }


# ─── Główne testy ────────────────────────────────────────────────────────────


def test_inject_dungeon_context_adds_loch_block():
    """_inject_dungeon_loch_context wstawia blok [LOCH] do messages."""
    messages = [
        {"role": "system", "content": "Główny prompt."},
        {"role": "user", "content": "Opisz komnatę."},
    ]
    _inject_dungeon_loch_context(_make_run(), {"name": "Test"}, messages)
    loch = [m for m in messages if "[LOCH" in m.get("content", "")]
    assert len(loch) == 1, "Musi być dokładnie jeden blok [LOCH]"


def test_inject_dungeon_context_includes_room_description():
    """Opis komnaty z DB trafia do bloku [LOCH] — LLM ma dane bez room_narrative."""
    messages = [{"role": "system", "content": "prompt"}, {"role": "user", "content": "q"}]
    _inject_dungeon_loch_context(_make_run("Wilgotny skarbiec z mchem na kamieniach."), {"name": "X"}, messages)
    loch_content = next(m["content"] for m in messages if "[LOCH" in m.get("content", ""))
    assert "Wilgotny skarbiec z mchem na kamieniach." in loch_content, "room_description musi być w bloku LOCH"


def test_inject_dungeon_context_includes_doors():
    """Otwarte drzwi trafiają do bloku [LOCH]."""
    messages = [{"role": "system", "content": "p"}, {"role": "user", "content": "q"}]
    _inject_dungeon_loch_context(_make_run(doors={"N": True, "S": True}), {"name": "X"}, messages)
    loch_content = next(m["content"] for m in messages if "[LOCH" in m.get("content", ""))
    assert "północ" in loch_content
    assert "południe" in loch_content


def test_inject_dungeon_context_enemy_present():
    """Wrogowie w pomieszczeniu powodują linię ostrzegawczą w bloku."""
    messages = [{"role": "system", "content": "p"}, {"role": "user", "content": "q"}]
    _inject_dungeon_loch_context(
        _make_run(enemies=["goblin"], cleared=False), {"name": "X"}, messages
    )
    loch_content = next(m["content"] for m in messages if "[LOCH" in m.get("content", ""))
    assert "wrogowie" in loch_content.lower()


def test_inject_dungeon_context_empty_room_desc_no_crash():
    """Pusty room_description nie powoduje wyjątku — blok LOCH nadal powstaje."""
    messages = [{"role": "user", "content": "q"}]
    _inject_dungeon_loch_context(_make_run(room_description=""), {"name": "X"}, messages)
    loch = [m for m in messages if "[LOCH" in m.get("content", "")]
    assert len(loch) == 1


# ─── Backward compat ─────────────────────────────────────────────────────────


def test_inject_does_not_remove_existing_messages():
    """Oryginalne messages (system + user) są zachowane po injekcji."""
    messages = [
        {"role": "system", "content": "Główny prompt."},
        {"role": "user", "content": "Opisz komnatę."},
    ]
    original_len = len(messages)
    _inject_dungeon_loch_context(_make_run(), {"name": "Test"}, messages)
    assert len(messages) == original_len + 1, "Inject dodaje dokładnie 1 message"
    assert messages[0]["content"] == "Główny prompt.", "Pierwszy message niezmieniony"
    assert messages[-1]["role"] == "user", "User message ostatni (przed blokiem)"
