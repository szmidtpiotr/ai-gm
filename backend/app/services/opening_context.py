"""Build opening-scene plan context string from a campaign's gm_plan_json.

Extracted from characters.py and turns.py (issue #372) so both code paths
share identical logic and it can be unit-tested in isolation.
"""
import json


def build_opening_plan_context(gm_plan_json: str | None) -> str:
    """Return a '\n\nKontekst kampanii:...' string when the plan has an active arc with a title
    or hook locations.  Returns '' on missing/empty/invalid input — never raises.
    """
    if not gm_plan_json:
        return ""
    try:
        plan = json.loads(gm_plan_json)
        arcs = plan.get("arcs") or {}
        active_id = plan.get("active_arc_id") or "default"
        arc = arcs.get(active_id) or next(iter(arcs.values()), {})
        title = arc.get("title", "")
        road = arc.get("roadmap", "")
        locs = ((arc.get("hooks") or {}).get("locations") or [])
        if not (title or locs):
            return ""
        return (
            "\n\nKontekst kampanii:"
            + (f"\n- Tytuł wątku: {title}" if title else "")
            + (f"\n- Zarys: {road[:200]}" if road else "")
            + (f"\n- Sugerowane lokacje: {', '.join(locs[:3])}" if locs else "")
            + "\n\nOtwarcie MUSI być spójne z tym kontekstem — wybierz odpowiednie miejsce startowe, NIE las jeśli fabuła tego nie wymaga."
        )
    except Exception:
        return ""
