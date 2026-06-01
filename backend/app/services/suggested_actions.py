"""
Suggested Actions — T33 Hybrid Input UI

Builds a context-aware list of quick-action buttons returned with each turn response.
These buttons allow the player to act without typing free text.

Rule-based actions are generated from DB state (locations, NPCs, inventory, combat).
LLM-suggested actions (from GM JSON `suggested_actions` field) are merged in after.
"""

from __future__ import annotations

import json
import sqlite3
import structlog
from dataclasses import dataclass, field
from typing import Optional

logger = structlog.get_logger()

MAX_ACTIONS = 5


@dataclass
class SuggestedAction:
    label: str            # Polish display text
    action: str           # structured action string sent on click
    enabled: bool = True
    reason: Optional[str] = None   # tooltip when disabled
    icon: Optional[str] = None
    highlight: bool = False        # pulse/glow animation on the pill

    def to_dict(self) -> dict:
        d: dict = {"label": self.label, "action": self.action, "enabled": self.enabled}
        if self.reason:
            d["reason"] = self.reason
        if self.icon:
            d["icon"] = self.icon
        if self.highlight:
            d["highlight"] = True
        return d


def build_suggested_actions(
    conn: sqlite3.Connection,
    campaign_id: int,
    character_id: int,
    game_state: str | None,
    session_flags: dict,
    llm_suggested: list[dict] | None = None,
    travel_hint: str | None = None,
) -> list[dict]:
    """
    Build up to MAX_ACTIONS quick-action buttons for the player UI.

    Returns a list of dicts (JSON-serialisable).
    Never raises — returns [] on any error.
    """
    try:
        state = (game_state or "").upper()
        if state in ("COMBAT",):
            actions = _build_combat_actions(conn, character_id)
        elif state in ("NARRATIVE", "DIALOGUE", "", "SKILL_TEST_PENDING"):
            actions = _build_narrative_actions(conn, campaign_id, session_flags)
        else:
            actions = []

        # Merge LLM-suggested actions (appended after rule-based, dedup by action string)
        if llm_suggested:
            seen = {a.action for a in actions}
            for item in llm_suggested:
                if not isinstance(item, dict):
                    continue
                action_str = str(item.get("action") or "").strip()
                label_str = str(item.get("label") or "").strip()
                if not action_str or not label_str:
                    continue
                if action_str in seen:
                    continue
                seen.add(action_str)
                actions.append(SuggestedAction(
                    label=label_str,
                    action=action_str,
                    enabled=bool(item.get("enabled", True)),
                    reason=item.get("reason"),
                    icon=item.get("icon"),
                ))

        # Travel hint pill — shown when GM signals travel is appropriate
        if travel_hint:
            travel_pill = SuggestedAction(
                label=f"Podróżuj → {travel_hint}",
                action="OPEN_MAP",
                enabled=True,
                icon="🗺",
                highlight=True,
            )
            # Insert at start so it's the most prominent
            actions.insert(0, travel_pill)

        # Cap at MAX_ACTIONS
        actions = actions[:MAX_ACTIONS]
        return [a.to_dict() for a in actions]

    except Exception as exc:
        logger.warning("suggested_actions_error", error=str(exc))
        return []


# ── NARRATIVE / DIALOGUE state ────────────────────────────────────────────────

def _build_narrative_actions(
    conn: sqlite3.Connection,
    campaign_id: int,
    session_flags: dict,
) -> list[SuggestedAction]:
    """Priority: NPCs first, exits, SEARCH, REST — capped at MAX_ACTIONS."""
    actions: list[SuggestedAction] = []

    current_loc_key = session_flags.get("current_location_key") or ""
    if not current_loc_key:
        try:
            row = conn.execute(
                "SELECT gl.key FROM game_sessions gs "
                "JOIN game_locations gl ON gs.current_location_id = gl.id "
                "WHERE gs.campaign_id = ? LIMIT 1",
                (campaign_id,),
            ).fetchone()
            if row:
                current_loc_key = row["key"] or ""
        except Exception:
            pass

    # 1) NPCs present at current location
    if current_loc_key:
        npc_actions = _get_npc_actions(conn, current_loc_key)
        actions.extend(npc_actions[:2])

    # 2) Movement exits (max 2)
    if current_loc_key:
        exit_actions = _get_exit_actions(conn, current_loc_key)
        remaining = MAX_ACTIONS - len(actions)
        actions.extend(exit_actions[:min(2, remaining)])

    # 3) SEARCH — always available
    if len(actions) < MAX_ACTIONS:
        actions.append(SuggestedAction(
            label="Przeszukaj okolicę",
            action="SEARCH",
            enabled=True,
        ))

    # 4) REST — depends on location safe_for_rest flag
    if len(actions) < MAX_ACTIONS:
        safe = _is_safe_for_rest(conn, current_loc_key)
        actions.append(SuggestedAction(
            label="Odpocznij",
            action="REST:long",
            enabled=safe,
            reason="Nie możesz tu bezpiecznie odpocząć" if not safe else None,
        ))

    # 5) BUILD_CAMP — Stage 2B R4: only when hex is KNOWN and unsafe (skip if location unknown)
    if len(actions) < MAX_ACTIONS and current_loc_key and not _is_safe_for_rest(conn, current_loc_key):
        actions.append(SuggestedAction(
            label="Rozbij obóz",
            action="BUILD_CAMP",
            enabled=True,
            icon="🔥",
            reason="Tymczasowy obóz pozwoli odpocząć, ale ściągnie więcej spotkań.",
        ))

    return actions


def _get_npc_actions(conn: sqlite3.Connection, location_key: str) -> list[SuggestedAction]:
    actions: list[SuggestedAction] = []
    try:
        # Try location_npc_assignments join table first
        rows = conn.execute(
            """
            SELECT n.key, n.name
            FROM location_npc_assignments lna
            JOIN game_npcs n ON n.key = lna.npc_key
            WHERE lna.location_key = ? AND lna.is_active = 1
            LIMIT 2
            """,
            (location_key,),
        ).fetchall()
        for row in rows:
            npc_key = str(row["key"] or "")
            npc_name = str(row["name"] or npc_key)
            actions.append(SuggestedAction(
                label=f"Porozmawiaj z {npc_name}",
                action=f"DIALOGUE:{npc_key}",
                enabled=True,
            ))
        if actions:
            return actions

        # Fallback: parse npc_keys JSON from game_locations
        loc_row = conn.execute(
            "SELECT npc_keys FROM game_locations WHERE key = ? LIMIT 1",
            (location_key,),
        ).fetchone()
        if loc_row:
            npc_keys_raw = loc_row["npc_keys"] if "npc_keys" in loc_row.keys() else None
            if npc_keys_raw:
                npc_keys = json.loads(npc_keys_raw) if isinstance(npc_keys_raw, str) else npc_keys_raw
                if isinstance(npc_keys, list):
                    for npc_key in npc_keys[:2]:
                        npc_key = str(npc_key).strip()
                        if not npc_key:
                            continue
                        # Try to get name
                        nr = conn.execute(
                            "SELECT name FROM game_npcs WHERE key = ? LIMIT 1",
                            (npc_key,),
                        ).fetchone()
                        npc_name = str(nr["name"]) if nr else npc_key
                        actions.append(SuggestedAction(
                            label=f"Porozmawiaj z {npc_name}",
                            action=f"DIALOGUE:{npc_key}",
                            enabled=True,
                        ))
    except Exception as exc:
        logger.warning("npc_actions_error", error=str(exc))
    return actions


def _get_exit_actions(conn: sqlite3.Connection, location_key: str) -> list[SuggestedAction]:
    actions: list[SuggestedAction] = []
    try:
        rows = conn.execute(
            """
            SELECT lc.to_key, gl.label
            FROM location_connections lc
            LEFT JOIN game_locations gl ON gl.key = lc.to_key
            WHERE lc.from_key = ?
            LIMIT 2
            """,
            (location_key,),
        ).fetchall()
        for row in rows:
            dest_key = str(row["to_key"] or "")
            dest_name = str(row["label"] or dest_key)
            if not dest_key:
                continue
            actions.append(SuggestedAction(
                label=f"Idź do {dest_name}",
                action=f"MOVEMENT:{dest_key}",
                enabled=True,
            ))
    except Exception as exc:
        logger.warning("exit_actions_error", error=str(exc))
    return actions


def _is_safe_for_rest(conn: sqlite3.Connection, location_key: str) -> bool:
    if not location_key:
        return False
    try:
        row = conn.execute(
            "SELECT safe_for_rest FROM game_locations WHERE key = ? LIMIT 1",
            (location_key,),
        ).fetchone()
        if row and "safe_for_rest" in row.keys():
            return bool(row["safe_for_rest"])
    except Exception as exc:
        logger.warning("safe_for_rest_error", error=str(exc))
    return False


# ── COMBAT state ──────────────────────────────────────────────────────────────

def _build_combat_actions(
    conn: sqlite3.Connection,
    character_id: int,
) -> list[SuggestedAction]:
    actions: list[SuggestedAction] = []

    # 1) Attack — always enabled
    actions.append(SuggestedAction(
        label="Atakuj",
        action="ATTACK",
        enabled=True,
        icon="⚔",
    ))

    # 2) Flee — depends on location enclosed flag
    not_enclosed = _can_flee(conn, character_id)
    actions.append(SuggestedAction(
        label="Uciekaj",
        action="FLEE",
        enabled=not_enclosed,
        reason="Brak drogi ucieczki" if not not_enclosed else None,
        icon="🏃",
    ))

    # 3) Use item — depends on inventory
    has_items = _has_usable_items(conn, character_id)
    actions.append(SuggestedAction(
        label="Użyj przedmiotu",
        action="ITEM_USE",
        enabled=has_items,
        reason="Brak przedmiotów" if not has_items else None,
        icon="🧪",
    ))

    return actions


def _can_flee(conn: sqlite3.Connection, character_id: int) -> bool:
    """Return True if character can flee (location is not enclosed)."""
    try:
        # Get character's current location via campaign
        row = conn.execute(
            """
            SELECT gl.enclosed
            FROM characters c
            JOIN campaigns camp ON camp.id = c.campaign_id
            JOIN game_sessions gs ON gs.campaign_id = camp.id
            LEFT JOIN game_locations gl ON gl.key = JSON_EXTRACT(gs.session_flags, '$.current_location_key')
            WHERE c.id = ?
            LIMIT 1
            """,
            (character_id,),
        ).fetchone()
        if row and "enclosed" in row.keys() and row["enclosed"] is not None:
            return not bool(row["enclosed"])
    except Exception as exc:
        logger.warning("can_flee_error", error=str(exc))
    # Safe default: can flee
    return True


def _has_usable_items(conn: sqlite3.Connection, character_id: int) -> bool:
    """Return True if character has any inventory items (excluding narrative-only)."""
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) as cnt
            FROM character_inventory
            WHERE character_id = ?
              AND item_key NOT IN ('__narrative__')
            """,
            (character_id,),
        ).fetchone()
        if row:
            return int(row["cnt"] or 0) > 0
    except Exception as exc:
        logger.warning("has_usable_items_error", error=str(exc))
    return False
