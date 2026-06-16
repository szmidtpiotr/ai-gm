"""TDD: Issue #698 (L-doors2) — endless extend musi domykać drzwi na styku segmentów.

Po #697 boss krypty ma WSZYSTKIE drzwi zaślepione (0 wolnych). `extend_dungeon_for_endless`
musi:
  - dobrać kierunek doczepienia z REALNYCH drzwi bossa (zdejmując zaślepkę),
  - upewnić się, że kafel-wejście nowego segmentu MA drzwi `opp_dir` (brak drzwi-widm),
  - domknąć cały scalony graf (`_fill_open_doors`),
  - zachować: ZERO doors_open==null, ZERO drzwi-widm, ZERO sierot, symetria na styku.

Testujemy czystą funkcję sklejającą `_attach_endless_segment`, żeby uniknąć całego setupu DB.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.dungeon_tile_service import (  # noqa: E402
    OPPOSITE,
    _attach_endless_segment,
    _count_open_doors,
)


# ─── helpery budowania syntetycznych grafów ──────────────────────────────────


def _node(tile_id, pos, doors, doors_open, is_boss=False):
    """Węzeł grafu z content.doors = realne drzwi kafla."""
    return {
        "tile_id": tile_id,
        "position": list(pos),
        "doors_open": dict(doors_open),
        "door_hints": {},
        "content": {"tile_id": tile_id, "doors": list(doors), "enemies": [], "items": []},
        "visited": False,
        "cleared": False,
        "is_boss": is_boss,
    }


def _cap_tile(tile_id, door):
    """Kafel-zaślepka (1 drzwi) dla puli `non_boss` używanej przez _fill_open_doors."""
    import json

    return {
        "id": tile_id,
        "label": f"cap_{door}",
        "doors_json": json.dumps([door]),
        "enemies_json": "[]",
        "items_json": "[]",
        "active_states_json": "[]",
        "exit_conditions_json": "[]",
    }


def _old_graph_post_697():
    """Stary graf po #697: boss ma WSZYSTKIE drzwi zaślepione (0 wolnych).

    node_0 (entry, drzwi E) → node_1 (boss, drzwi W+S).
    Boss W = ścieżka do entry; boss S = zaślepka cap_s (osierocalny węzeł).
    """
    nodes = {
        "node_0": _node(10, (0, 0), ["E"], {"E": "node_1"}),
        "node_1": _node(20, (1, 0), ["W", "S"], {"W": "node_0", "S": "cap_s"}, is_boss=True),
        "cap_s": _node(99, (1, -1), ["N"], {"N": "node_1"}),
    }
    return nodes, "node_1"


def _new_segment_graph():
    """Nowy odcinek (cycle 2): entry drzwi N+E, wewnątrz zaślepka na N.

    node_0 (entry, drzwi N+E) → node_1 (boss, drzwi W). N entry = zaślepka fill_0.
    Kierunek styku: boss S (opp N) ⇒ entry MUSI mieć drzwi N. Ma. Brak drzwi-widm.
    """
    nodes = {
        "node_0": _node(30, (0, 0), ["N", "E"], {"N": "fill_0", "E": "node_1"}),
        "node_1": _node(40, (1, 0), ["W"], {"W": "node_0"}, is_boss=True),
        "fill_0": _node(99, (0, 1), ["S"], {"S": "node_0"}),
    }
    return {"nodes": nodes, "entry_node": "node_0", "boss_node": "node_1"}


def _all_dirs_reachable(nodes, entry):
    seen = set()
    stack = [entry]
    while stack:
        nid = stack.pop()
        if nid in seen:
            continue
        seen.add(nid)
        for tgt in (nodes.get(nid, {}).get("doors_open") or {}).values():
            if tgt is not None and tgt not in seen:
                stack.append(tgt)
    return seen


# ─── Test główny — regresja #698 ──────────────────────────────────────────────


def test_extend_welds_seam_no_null_no_ghost_no_orphan():
    old_nodes, old_boss = _old_graph_post_697()
    new_graph = _new_segment_graph()
    caps = [_cap_tile(99, d) for d in ("N", "S", "E", "W")]

    result = _attach_endless_segment(old_nodes, old_boss, new_graph, new_cycle=2, non_boss_caps=caps)
    nodes = result["nodes"]
    entry = "node_0"

    # 1. ZERO doors_open == null
    assert _count_open_doors(nodes) == 0, "po extend zostały otwarte (null) drzwi"

    # 2. Brak drzwi-widm: każdy kierunek w doors_open istnieje w content.doors kafla
    for nid, n in nodes.items():
        real = set(n["content"]["doors"])
        for d in n["doors_open"]:
            assert d in real, f"drzwi-widmo {nid}.{d} — brak w content.doors {real}"

    # 3. Symetria: każde połączenie obustronne
    for nid, n in nodes.items():
        for d, tgt in n["doors_open"].items():
            assert tgt is not None
            back = nodes[tgt]["doors_open"].get(OPPOSITE[d])
            assert back == nid, f"asymetria {nid}.{d}->{tgt}, powrót={back}"

    # 4. Brak sierot — wszystko osiągalne z entry
    reachable = _all_dirs_reachable(nodes, entry)
    assert set(nodes.keys()) == reachable, (
        f"węzły-sieroty: {set(nodes.keys()) - reachable}"
    )

    # 5. Styk boss↔nowy segment faktycznie istnieje (boss łączy się z węzłem cyklu 2)
    boss_targets = set((nodes[old_boss]["doors_open"]).values())
    assert any(t.startswith("c2_") for t in boss_targets), "boss nie doczepił segmentu c2_"

    # 6. Osierocona zaślepka usunięta (cap_s nie wisi już w grafie jako sierota)
    assert "cap_s" not in nodes or nodes["cap_s"]["doors_open"].get("N") == old_boss


# ─── Regresja z /playwright-test-report L13c (2026-06-16) ─────────────────────
# Pierwsza wersja fixu sklejała segment na DOWOLNYCH drzwiach bossa, których
# przeciwległy kierunek istniał w kaflu-wejściu — także na drzwiach prowadzących
# do REALNEJ ścieżki. Skutek na żywym grafie: kradła krawędź ścieżki bossa
# (asymetria) i nadpisywała drzwi-onward kafla-wejścia (cały nowy segment osierocony).
# Reguła: styk MUSI użyć drzwi „zapasowych" (None lub zaślepka) po OBU stronach;
# gdy takiej pary nie ma → przegeneruj segment (helper rzuca ValueError).


def _old_graph_two_path_two_cap_boss():
    """Boss z 2 drzwiami ŚCIEŻKI (W→node_4, S→node_2) i 2 zaślepkami (N, E).

    Odwzorowuje realny graf z kampanii 99762: boss node_5 miał W→node_4 (wejście
    ścieżki) i S→node_2, a N/E były zaślepione.
    """
    nodes = {
        "node_0": _node(10, (-2, 0), ["E"], {"E": "node_4"}),
        "node_4": _node(11, (-1, 0), ["E", "W"], {"W": "node_0", "E": "node_5"}),
        "node_2": _node(12, (0, -1), ["N"], {"N": "node_5"}),
        "cap_n": _node(99, (0, 1), ["S"], {"S": "node_5"}),
        "cap_e": _node(99, (1, 0), ["W"], {"W": "node_5"}),
        "node_5": _node(20, (0, 0), ["N", "S", "E", "W"],
                        {"N": "cap_n", "S": "node_2", "E": "cap_e", "W": "node_4"}, is_boss=True),
    }
    return nodes, "node_5"


def test_seam_uses_spare_doors_never_steals_boss_path():
    """Boss z 2 ścieżkami + 2 zaślepkami: styk dobiera zaślepkę↔zaślepkę,
    NIE odpina ścieżki bossa ani drzwi-onward wejścia → zero sierot/asymetrii."""
    old_nodes, old_boss = _old_graph_two_path_two_cap_boss()
    # nowy segment: wejście ma drzwi S=zaślepka (pasuje do bossa N) + E=onward
    new_graph = {
        "nodes": {
            "node_0": _node(30, (0, 0), ["S", "E"], {"S": "fill_0", "E": "node_1"}),
            "node_1": _node(40, (1, 0), ["W"], {"W": "node_0"}, is_boss=True),
            "fill_0": _node(99, (0, -1), ["N"], {"N": "node_0"}),
        },
        "entry_node": "node_0",
        "boss_node": "node_1",
    }
    caps = [_cap_tile(99, d) for d in ("N", "S", "E", "W")]
    result = _attach_endless_segment(old_nodes, old_boss, new_graph, new_cycle=2, non_boss_caps=caps)
    nodes = result["nodes"]

    assert _count_open_doors(nodes) == 0, "zostały otwarte drzwi"
    # boss ścieżki nienaruszone: node_4↔boss (W) i node_2↔boss (S) dalej symetryczne
    assert nodes[old_boss]["doors_open"]["W"] == "node_4"
    assert nodes["node_4"]["doors_open"]["E"] == old_boss
    assert nodes[old_boss]["doors_open"]["S"] == "node_2"
    # drzwi-onward wejścia c2 zachowane (segment NIE osierocony)
    assert nodes["c2_node_0"]["doors_open"]["E"] == "c2_node_1"
    # symetria + brak sierot na całości
    for nid, n in nodes.items():
        for d, tgt in n["doors_open"].items():
            assert tgt is not None
            assert nodes[tgt]["doors_open"].get(OPPOSITE[d]) == nid, f"asym {nid}.{d}"
            assert d in set(n["content"]["doors"]), f"ghost {nid}.{d}"
    assert set(nodes.keys()) == _all_dirs_reachable(nodes, "node_0"), "sieroty"


def test_no_compatible_spare_pair_raises_for_redraw():
    """Gdy żadna para zapasowych drzwi nie pasuje (jedyne wolne drzwi bossa nie mają
    odpowiednika-zapasu w wejściu) → helper rzuca ValueError zamiast łączyć przez
    ścieżkę/onward (sygnał dla wołającego: przegeneruj segment)."""
    old_nodes, old_boss = _old_graph_two_path_two_cap_boss()
    # wejście: jedyne drzwi pasujące kierunkiem (S→boss N) to drzwi-ONWARD (nie zapas);
    # zapasowe drzwi wejścia W nie mają zapasowego odpowiednika u bossa (E to zaślepka,
    # ale opp(W)=E… ustawmy tak, by realnie nie było pary)
    new_graph = {
        "nodes": {
            # entry: S = onward (do node_1), brak innych drzwi → opp(N bossa)=S = onward
            "node_0": _node(30, (0, 0), ["S"], {"S": "node_1"}),
            "node_1": _node(40, (0, 1), ["N"], {"N": "node_0"}, is_boss=True),
        },
        "entry_node": "node_0",
        "boss_node": "node_1",
    }
    caps = [_cap_tile(99, d) for d in ("N", "S", "E", "W")]
    with pytest.raises(ValueError):
        _attach_endless_segment(old_nodes, old_boss, new_graph, new_cycle=2, non_boss_caps=caps)


# ─── Backward compat — entry-run graf (#697) pozostaje nienaruszony ───────────


def test_old_entry_run_graph_still_closed_after_697():
    """Graf entry-run (#697) sam w sobie ma 0 otwartych drzwi — nie regresujemy."""
    old_nodes, _ = _old_graph_post_697()
    assert _count_open_doors(old_nodes) == 0
