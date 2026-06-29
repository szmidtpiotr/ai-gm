"""
W1 canonical shape for `campaigns.gm_plan_json` (**[S11b]** / T06).

- Single JSON blob on the campaign row (no extra SQL table for beats in W1).
- `normalize_gm_plan` upgrades legacy rows and fills defaults.
- `merge_gm_plan_patch` applies PATCH payloads without wiping unrelated keys.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

GM_PLAN_SCHEMA_VERSION = 2

# Keys considered "legacy" flat content before W1 arcs; kept for backward compatibility.
_LEGACY_TOP_KEYS = frozenset(
    {
        "roadmap",
        "scene_goals",
        "hooks",
        "current_scene_ordinal",
        "scene_log",
    }
)


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _ensure_arc_shape(arc_id: str, node: Any) -> dict[str, Any]:
    if not isinstance(node, dict):
        node = {}
    out = dict(node)
    out.setdefault("id", arc_id)
    out.setdefault("title", "")
    out.setdefault("status", "draft")  # draft | active | closed
    goals = out.get("scene_goals")
    if not isinstance(goals, list):
        goals = []
    out["scene_goals"] = [str(g).strip() for g in goals if g is not None and str(g).strip()]
    hooks = out.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
    npcs = hooks.get("npcs")
    locs = hooks.get("locations")
    hooks_out: dict[str, Any] = {}
    if isinstance(npcs, list) and npcs:
        hooks_out["npcs"] = [str(x) for x in npcs if x is not None and str(x).strip()]
    if isinstance(locs, list) and locs:
        hooks_out["locations"] = [str(x) for x in locs if x is not None and str(x).strip()]
    out["hooks"] = hooks_out
    priv = out.get("private_notes")
    if priv is not None and not isinstance(priv, str):
        out["private_notes"] = str(priv)
    return out


def normalize_gm_plan(raw: str | None) -> dict[str, Any]:
    """
    Parse DB text → canonical dict. Invalid JSON becomes empty plan with schema marker.
    Migrates legacy flat keys into `arcs.default` when no arcs yet.
    """
    if not raw or not str(raw).strip():
        return {
            "schema_version": GM_PLAN_SCHEMA_VERSION,
            "arcs": {},
            "active_arc_id": None,
            "engine_private": {},
        }
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {
            "schema_version": GM_PLAN_SCHEMA_VERSION,
            "arcs": {},
            "active_arc_id": None,
            "engine_private": {},
        }
    if not isinstance(data, dict):
        return {
            "schema_version": GM_PLAN_SCHEMA_VERSION,
            "arcs": {},
            "active_arc_id": None,
            "engine_private": {},
        }

    out = deepcopy(data)
    ver = _coerce_int(out.get("schema_version"), 0)
    if ver < GM_PLAN_SCHEMA_VERSION:
        arcs = out.get("arcs")
        if not isinstance(arcs, dict) or not arcs:
            if isinstance(arcs, list) and arcs:
                # Template format: arcs is a list of {id, key_beats, status} dicts.
                # Convert to W1 dict keyed by arc.id; derive scene_goals from key_beats labels.
                arcs_dict: dict[str, Any] = {}
                active_id_from_list: str | None = None
                for i, arc in enumerate(arcs):
                    if not isinstance(arc, dict):
                        continue
                    arc_id = str(arc.get("id", f"arc_{i}"))
                    arc_copy = dict(arc)
                    if "key_beats" in arc_copy and "scene_goals" not in arc_copy:
                        arc_copy["scene_goals"] = [
                            b.get("label") or b.get("beat_key", "")
                            for b in arc_copy.get("key_beats", [])
                            if isinstance(b, dict) and (b.get("label") or b.get("beat_key"))
                        ]
                    arcs_dict[arc_id] = arc_copy
                    if arc.get("status") == "active" and active_id_from_list is None:
                        active_id_from_list = arc_id
                out["arcs"] = arcs_dict
                if not out.get("active_arc_id") and active_id_from_list:
                    out["active_arc_id"] = active_id_from_list
            else:
                legacy_slice = {k: out[k] for k in _LEGACY_TOP_KEYS if k in out}
                if legacy_slice:
                    out["arcs"] = {"default": _ensure_arc_shape("default", legacy_slice)}
                    out["active_arc_id"] = "default"
                else:
                    out["arcs"] = {}
                    out["active_arc_id"] = None
        else:
            fixed: dict[str, Any] = {}
            for aid, node in arcs.items():
                if aid is None:
                    continue
                fixed[str(aid)] = _ensure_arc_shape(str(aid), node)
            out["arcs"] = fixed
            if out.get("active_arc_id") is None and fixed:
                out["active_arc_id"] = next(iter(fixed.keys()))
        ep = out.get("engine_private")
        if not isinstance(ep, dict):
            out["engine_private"] = {}
        out["schema_version"] = GM_PLAN_SCHEMA_VERSION

    # Ensure shape even when schema_version already current
    arcs = out.get("arcs")
    if not isinstance(arcs, dict):
        arcs = {}
    fixed_arcs: dict[str, Any] = {}
    for aid, node in arcs.items():
        if aid is None:
            continue
        fixed_arcs[str(aid)] = _ensure_arc_shape(str(aid), node)
    out["arcs"] = fixed_arcs

    aa = out.get("active_arc_id")
    if aa is not None:
        aa = str(aa).strip() or None
    if aa and aa not in fixed_arcs:
        aa = next(iter(fixed_arcs.keys()), None) if fixed_arcs else None
    elif aa is None and fixed_arcs:
        aa = next(iter(fixed_arcs.keys()))
    out["active_arc_id"] = aa

    ep = out.get("engine_private")
    if not isinstance(ep, dict):
        out["engine_private"] = {}
    out["schema_version"] = GM_PLAN_SCHEMA_VERSION
    return out


def _deep_merge_dict(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge_dict(out[k], v)  # type: ignore[arg-type]
        else:
            out[k] = v
    return out


def merge_gm_plan_patch(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """
    Merge PATCH body into base plan.
    - Top-level keys: shallow overwrite except `arcs` and `engine_private` (deep merge).
    - `arcs[id]` merges per arc; use null/empty value strategies via replace whole arc by sending full object.
    """
    out = deepcopy(normalize_gm_plan(json.dumps(base, ensure_ascii=False)))

    # Legacy flat PATCH bodies (roadmap, scene_goals, …) route into the active arc when `arcs` is omitted.
    legacy_in_patch = {k: patch[k] for k in _LEGACY_TOP_KEYS if k in patch}
    patch_rest = {k: v for k, v in patch.items() if k not in _LEGACY_TOP_KEYS}
    if legacy_in_patch and "arcs" not in patch:
        aa = out.get("active_arc_id")
        aid = (
            str(aa).strip()
            if isinstance(aa, str) and str(aa).strip()
            else (next(iter(out.get("arcs") or {}), None) or "default")
        )
        arc_wrap = {"arcs": {aid: legacy_in_patch}}
        patch = {**patch_rest, **arc_wrap}
    else:
        patch = dict(patch)

    for key, val in patch.items():
        if key == "arcs" and isinstance(val, dict):
            arcs = out.get("arcs")
            if not isinstance(arcs, dict):
                arcs = {}
            for aid, arc_patch in val.items():
                if aid is None:
                    continue
                sid = str(aid)
                if isinstance(arc_patch, dict):
                    prev = arcs.get(sid, {})
                    merged_arc = _deep_merge_dict(
                        prev if isinstance(prev, dict) else {}, arc_patch
                    )
                    arcs[sid] = _ensure_arc_shape(sid, merged_arc)
                else:
                    arcs[sid] = _ensure_arc_shape(sid, arc_patch)
            out["arcs"] = arcs
        elif key == "engine_private" and isinstance(val, dict):
            ep = out.get("engine_private")
            if not isinstance(ep, dict):
                ep = {}
            out["engine_private"] = _deep_merge_dict(ep, val)
        else:
            out[key] = val
    return normalize_gm_plan(json.dumps(out, ensure_ascii=False))


def format_gm_plan_block(raw: str | None) -> str:
    """
    Human-readable block for prompts (narrative injection, GM summary).
    Uses active arc when set; otherwise falls back to legacy flat fields / first arc.
    """
    plan = normalize_gm_plan(raw)
    arcs: dict[str, Any] = plan.get("arcs") if isinstance(plan.get("arcs"), dict) else {}
    active_id = plan.get("active_arc_id")
    node: dict[str, Any] | None = None
    if isinstance(active_id, str) and active_id.strip() and active_id in arcs:
        node = arcs[active_id]
    elif arcs:
        first_key = next(iter(arcs.keys()))
        node = arcs.get(first_key)
    if not isinstance(node, dict):
        node = {}

    roadmap = node.get("roadmap")
    if roadmap is None and plan.get("roadmap"):
        roadmap = plan.get("roadmap")

    parts: list[str] = []
    if roadmap and str(roadmap).strip():
        parts.append("## Plan / roadmap MG\n" + str(roadmap).strip())

    goals = node.get("scene_goals")
    if goals is None and isinstance(plan.get("scene_goals"), list):
        goals = plan.get("scene_goals")
    if isinstance(goals, list) and goals:
        lines = "\n".join(f"- {g}" for g in goals if g is not None and str(g).strip())
        if lines:
            parts.append("## Cele bieżącego odcinka / sceny\n" + lines)

    hooks = node.get("hooks")
    if not isinstance(hooks, dict) and isinstance(plan.get("hooks"), dict):
        hooks = plan.get("hooks")
    if isinstance(hooks, dict):
        npcs = hooks.get("npcs")
        locs = hooks.get("locations")
        bits = []
        if isinstance(npcs, list) and npcs:
            bits.append("NPC: " + ", ".join(str(x) for x in npcs if x))
        if isinstance(locs, list) and locs:
            bits.append("Lokacje: " + ", ".join(str(x) for x in locs if x))
        if bits:
            parts.append("## Haki fabularne\n" + "\n".join(bits))

    ordn = node.get("current_scene_ordinal")
    if ordn is None:
        ordn = plan.get("current_scene_ordinal")
    if ordn is not None:
        try:
            parts.append(f"## Licznik odcinka (MG): {int(ordn)}")
        except (TypeError, ValueError):
            pass

    aa = plan.get("active_arc_id")
    if isinstance(aa, str) and aa.strip() and arcs:
        parts.append(f"## Aktywny łuk (MG): {aa.strip()}")

    return "\n\n".join(parts)


def gm_plan_is_ready(raw: str | None) -> bool:
    """
    Minimalna treść planu MG zanim pierwsza narracja może pójść do LLM (T05).
    Sprawdza aktywny łuk (lub pierwszy dostępny / legacy).
    """
    plan = normalize_gm_plan(raw)

    # #1018 — V2 plans carry the roadmap as `acts[].key_beats[]` (no `arcs`).
    # A plan with at least one act that has beats / a summary / a title is ready;
    # without this a freshly generated V2 plan would look "empty" and trigger a
    # spurious regeneration.
    acts = plan.get("acts")
    if isinstance(acts, list) and any(
        isinstance(a, dict)
        and (
            a.get("key_beats")
            or str(a.get("summary") or "").strip()
            or str(a.get("title") or "").strip()
        )
        for a in acts
    ):
        return True

    arcs: dict[str, Any] = plan.get("arcs") if isinstance(plan.get("arcs"), dict) else {}
    active_id = plan.get("active_arc_id")
    node: dict[str, Any] | None = None
    if isinstance(active_id, str) and active_id.strip() and active_id in arcs:
        node = arcs[active_id]
    elif arcs:
        node = next(iter(arcs.values()))
    if not isinstance(node, dict):
        node = {}

    roadmap = node.get("roadmap")
    if roadmap is None and plan.get("roadmap"):
        roadmap = plan.get("roadmap")
    if roadmap is not None and str(roadmap).strip():
        return True

    goals = node.get("scene_goals")
    if goals is None and isinstance(plan.get("scene_goals"), list):
        goals = plan.get("scene_goals")
    if isinstance(goals, list) and any(str(g).strip() for g in goals if g is not None):
        return True

    hooks = node.get("hooks")
    if not isinstance(hooks, dict) and isinstance(plan.get("hooks"), dict):
        hooks = plan.get("hooks")
    if isinstance(hooks, dict):
        npcs = hooks.get("npcs")
        locs = hooks.get("locations")
        if isinstance(npcs, list) and any(str(x).strip() for x in npcs if x is not None):
            return True
        if isinstance(locs, list) and any(str(x).strip() for x in locs if x is not None):
            return True

    return False


# ── #991: Arc auto-advance ───────────────────────────────────────────────────

_TUTORIAL_ARC_MARKERS = ("tutorial", "intro", "prolog", "wstep", "wstęp", "samouczek")


def advance_gm_plan_arc(raw: str | None) -> tuple[dict[str, Any], bool]:
    """After tutorial/intro quest completes, advance active_arc_id to the next arc.

    Only auto-advances when the current arc id or title contains a tutorial/intro marker.
    Returns (updated_plan_dict, did_advance).
    """
    plan = normalize_gm_plan(raw)
    arcs: dict[str, Any] = plan.get("arcs", {})
    active_id = plan.get("active_arc_id")

    if not active_id or not arcs or len(arcs) < 2:
        return plan, False

    # Check if current arc is a tutorial/intro arc by id or title
    active_arc = arcs.get(str(active_id), {})
    active_label = (str(active_id) + " " + str(active_arc.get("title", ""))).lower()
    if not any(marker in active_label for marker in _TUTORIAL_ARC_MARKERS):
        return plan, False

    arc_keys = list(arcs.keys())
    try:
        idx = arc_keys.index(str(active_id))
    except ValueError:
        return plan, False

    if idx + 1 >= len(arc_keys):
        return plan, False

    next_arc_id = arc_keys[idx + 1]
    plan = deepcopy(plan)
    plan["arcs"][str(active_id)]["status"] = "closed"
    plan["arcs"][next_arc_id]["status"] = "active"
    plan["active_arc_id"] = next_arc_id
    return plan, True
