"""NPC memory (BUG-03).

Per-campaign roster of NPCs the party has met. Lightweight layer over the
global `npcs` catalog. The MG context-injector calls `get_recent_known_npcs`
every turn to remind itself of who the player already knows; the turn loop
calls `record_npc_met` / `update_npc_relation` when it parses the matching
optional fields from the LLM response.

Schema migration: `_ensure_campaign_known_npcs` in `migrations_admin.py`.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable

DB_PATH = Path("/data/ai_gm.db")

# Cap exposed to MG. More history → bigger prompt → no real upside since the
# user explicitly chose "last 10 met" during BUG-03 discovery.
DEFAULT_CONTEXT_LIMIT = 10

VALID_RELATIONS = ("friendly", "neutral", "hostile")

_PURCHASE_COUNT_COL = "purchase_count"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _lookup_catalog_npc_id(conn: sqlite3.Connection, name: str) -> int | None:
    """Best-effort catalog match by exact label, falling back to key prefix."""
    row = conn.execute(
        "SELECT id FROM npcs WHERE LOWER(label) = LOWER(?) LIMIT 1", (name,)
    ).fetchone()
    if row:
        return int(row["id"])
    # Soft fallback: a key like "marta_karczmarka" should match "Marta".
    row = conn.execute(
        "SELECT id FROM npcs WHERE key = LOWER(REPLACE(?, ' ', '_')) LIMIT 1", (name,)
    ).fetchone()
    return int(row["id"]) if row else None


def record_npc_met(
    *,
    campaign_id: int,
    name: str,
    role: str | None = None,
    first_met_location: str | None = None,
    first_met_turn: int | None = None,
    notes: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Insert-or-touch a known-NPC row.

    Idempotent on (campaign_id, npc_name): a repeat call updates the
    updated_at timestamp and merges in any newly-provided fields without
    clobbering existing values with None.
    """
    name = (name or "").strip()
    if not name:
        return {"ok": False, "reason": "empty name"}

    managed = conn is None
    if managed:
        conn = _conn()
    try:
        npc_id = _lookup_catalog_npc_id(conn, name)
        existing = conn.execute(
            "SELECT * FROM campaign_known_npcs WHERE campaign_id = ? AND npc_name = ?",
            (campaign_id, name),
        ).fetchone()

        if existing:
            # Only overwrite fields the caller actually supplied. Leave None alone.
            fields: list[tuple[str, Any]] = []
            if role is not None:
                fields.append(("role", role))
            if first_met_location is not None and not existing["first_met_location"]:
                # first_met_location is sticky — set once.
                fields.append(("first_met_location", first_met_location))
            if notes is not None:
                fields.append(("notes", notes))
            if npc_id and not existing["npc_id"]:
                fields.append(("npc_id", npc_id))

            set_clauses = ", ".join(f"{col} = ?" for col, _ in fields)
            if set_clauses:
                set_clauses += ", updated_at = datetime('now')"
            else:
                set_clauses = "updated_at = datetime('now')"
            params: list[Any] = [v for _, v in fields] + [existing["id"]]
            conn.execute(
                f"UPDATE campaign_known_npcs SET {set_clauses} WHERE id = ?",
                params,
            )
            row_id = existing["id"]
        else:
            cur = conn.execute(
                """
                INSERT INTO campaign_known_npcs
                    (campaign_id, npc_id, npc_name, role, first_met_location, first_met_turn, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (campaign_id, npc_id, name, role, first_met_location, first_met_turn, notes),
            )
            row_id = cur.lastrowid

        if managed:
            conn.commit()
        return {"ok": True, "id": row_id, "new": existing is None, "catalog_npc_id": npc_id}
    finally:
        if managed:
            conn.close()


def update_npc_relation(
    *,
    campaign_id: int,
    name: str,
    relation_status: str | None = None,
    notes: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Update an existing known-NPC's disposition and/or notes.

    No-op if the NPC isn't already in the roster (we don't auto-create here —
    use `record_npc_met` for that). Returns {ok: False} if not found so the
    caller can decide to insert.
    """
    name = (name or "").strip()
    if not name:
        return {"ok": False, "reason": "empty name"}
    if relation_status is not None and relation_status not in VALID_RELATIONS:
        return {"ok": False, "reason": f"invalid relation_status: {relation_status}"}

    managed = conn is None
    if managed:
        conn = _conn()
    try:
        row = conn.execute(
            "SELECT id FROM campaign_known_npcs WHERE campaign_id = ? AND npc_name = ?",
            (campaign_id, name),
        ).fetchone()
        if not row:
            return {"ok": False, "reason": "not_found"}

        fields: list[tuple[str, Any]] = []
        if relation_status is not None:
            fields.append(("relation_status", relation_status))
        if notes is not None:
            fields.append(("notes", notes))
        if not fields:
            return {"ok": True, "id": row["id"], "noop": True}

        set_clauses = ", ".join(f"{col} = ?" for col, _ in fields)
        set_clauses += ", updated_at = datetime('now')"
        params: list[Any] = [v for _, v in fields] + [row["id"]]
        conn.execute(
            f"UPDATE campaign_known_npcs SET {set_clauses} WHERE id = ?",
            params,
        )
        if managed:
            conn.commit()
        return {"ok": True, "id": row["id"]}
    finally:
        if managed:
            conn.close()


def increment_npc_purchase_count(
    *,
    campaign_id: int,
    npc_id: int,
    npc_name: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> None:
    """Bump purchase_count for this shop NPC.

    If npc_name is provided, UPSERTs a minimal roster entry so purchases
    are tracked even before the player has a dialogue encounter with the NPC.
    Without npc_name, falls back to UPDATE-only (no-op if not in roster yet).
    """
    managed = conn is None
    if managed:
        conn = _conn()
    try:
        try:
            if npc_name:
                conn.execute(
                    """
                    INSERT INTO campaign_known_npcs
                        (campaign_id, npc_id, npc_name, relation_status, purchase_count)
                    VALUES (?, ?, ?, 'neutral', 1)
                    ON CONFLICT(campaign_id, npc_name) DO UPDATE SET
                        npc_id = excluded.npc_id,
                        purchase_count = COALESCE(campaign_known_npcs.purchase_count, 0) + 1,
                        updated_at = datetime('now')
                    """,
                    (int(campaign_id), int(npc_id), str(npc_name)),
                )
            else:
                conn.execute(
                    """
                    UPDATE campaign_known_npcs
                    SET purchase_count = COALESCE(purchase_count, 0) + 1,
                        updated_at = datetime('now')
                    WHERE campaign_id = ? AND npc_id = ?
                    """,
                    (int(campaign_id), int(npc_id)),
                )
            if managed:
                conn.commit()
        except Exception:
            pass  # silently skip on schema mismatch
    finally:
        if managed:
            conn.close()


def get_recent_known_npcs(
    campaign_id: int,
    limit: int = DEFAULT_CONTEXT_LIMIT,
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    """Return the most-recently-active NPCs the party has met in this campaign.

    Joined with `npcs` for catalog data (description, personality) so callers
    can format a rich block without N+1 queries.
    """
    managed = conn is None
    if managed:
        conn = _conn()
    try:
        rows = conn.execute(
            """
            SELECT
                k.id, k.npc_name, k.role, k.first_met_location, k.first_met_turn,
                k.notes, k.relation_status, k.updated_at, k.npc_id,
                COALESCE(k.purchase_count, 0) AS purchase_count,
                n.description AS catalog_description,
                n.personality_json AS catalog_personality_json,
                COALESCE(n.is_shop, 0) AS is_shop
            FROM campaign_known_npcs k
            LEFT JOIN npcs n ON n.id = k.npc_id
            WHERE k.campaign_id = ?
            ORDER BY k.updated_at DESC, k.id DESC
            LIMIT ?
            """,
            (campaign_id, int(limit)),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        if managed:
            conn.close()


def format_known_npcs_block(
    rows: Iterable[dict[str, Any]],
) -> str:
    """Render a Polish prompt block listing known NPCs for context injection.

    Returns an empty string when there are no rows so the caller can skip
    appending an empty section.
    """
    rows = list(rows)
    if not rows:
        return ""

    lines: list[str] = ["### ZNANI NPC (ostatnich " + str(len(rows)) + ", pamiętaj o nich)"]
    relation_pl = {"friendly": "przyjazny", "neutral": "neutralny", "hostile": "wrogi"}
    for r in rows:
        bits: list[str] = []
        bits.append(str(r.get("npc_name") or "?"))
        if r.get("role"):
            bits.append(f"({r['role']})")
        if r.get("first_met_location"):
            bits.append(f"— spotkany w: {r['first_met_location']}")
        rel = relation_pl.get(str(r.get("relation_status") or "neutral"), "neutralny")
        bits.append(f"— relacja: {rel}")
        purchase_count = int(r.get("purchase_count") or 0)
        if purchase_count > 0:
            if purchase_count >= 5:
                bits.append(f"— stały klient ({purchase_count} zakupów)")
            else:
                bits.append(f"— był klientem ({purchase_count}× zakup)")
        line = "- " + " ".join(bits)
        if r.get("notes"):
            line += f"; notatka: {r['notes']}"
        if r.get("catalog_description"):
            desc = str(r["catalog_description"]).strip()
            first = desc.split(". ", 1)[0]
            if first and first not in (r.get("notes") or ""):
                line += f" (katalog: {first[:120]})"
        # Inject personality traits for shop NPCs so GM can flavor their dialogue
        if r.get("is_shop") and r.get("catalog_personality_json"):
            try:
                pjson = json.loads(str(r["catalog_personality_json"]))
                personality = str(pjson.get("personality") or "").strip()
                topics = pjson.get("topics") or []
                if personality:
                    line += f"; charakter: {personality[:100]}"
                if topics:
                    line += f"; tematy: {', '.join(str(t) for t in topics[:3])}"
            except Exception:
                pass
        lines.append(line)
    return "\n".join(lines)


# ── D3 (#378) — NPC_MEMORY tag: explicit remembered facts ─────────────────────

# [NPC_MEMORY: Imię | zapamiętany fakt] — name and fact separated by a pipe so the
# fact itself may contain colons. Case-insensitive, DOTALL off (facts are one line).
NPC_MEMORY_RE = re.compile(
    r"\[NPC_MEMORY:\s*([^|\]]+?)\s*\|\s*([^\]]+?)\s*\]", re.IGNORECASE
)

# Max accumulated facts kept per NPC — keeps the injected prompt block bounded.
MAX_NPC_MEMORY_FACTS = 8


def parse_npc_memory_tags(text: str) -> list[tuple[str, str]]:
    """Extract (npc_name, fact) pairs from `[NPC_MEMORY: name | fact]` tags."""
    out: list[tuple[str, str]] = []
    for m in NPC_MEMORY_RE.finditer(text or ""):
        name = (m.group(1) or "").strip()
        fact = (m.group(2) or "").strip()
        if name and fact:
            out.append((name, fact))
    return out


def strip_npc_memory_tags(text: str) -> str:
    """Remove all `[NPC_MEMORY:...]` tags from narrative shown to the player."""
    if not text:
        return text or ""
    return NPC_MEMORY_RE.sub("", text).strip()


def append_npc_memory(
    *,
    campaign_id: int,
    name: str,
    memory: str,
    conn: sqlite3.Connection | None = None,
    max_facts: int = MAX_NPC_MEMORY_FACTS,
) -> dict[str, Any]:
    """Append a remembered fact to an NPC's accumulated memory (`notes`).

    Facts accumulate (";"-joined) instead of clobbering, are de-duplicated, and
    capped to the last `max_facts`. Creates the roster row via record_npc_met if
    the NPC isn't known yet. The fact is injected on the next visit through the
    existing format_known_npcs_block (`notes` field). Mirrors D1/D2 pending flow
    in spirit: an LLM-emitted tag deterministically persists state.
    """
    name = (name or "").strip()
    memory = (memory or "").strip()
    if not name or not memory:
        return {"ok": False, "reason": "empty"}

    managed = conn is None
    if managed:
        conn = _conn()
    try:
        row = conn.execute(
            "SELECT id, notes FROM campaign_known_npcs WHERE campaign_id = ? AND npc_name = ?",
            (campaign_id, name),
        ).fetchone()

        if not row:
            record_npc_met(campaign_id=campaign_id, name=name, notes=memory, conn=conn)
            if managed:
                conn.commit()
            return {"ok": True, "created": True, "facts": [memory]}

        existing = (row["notes"] or "").strip()
        facts = [f.strip() for f in existing.split(";") if f.strip()] if existing else []
        if memory in facts:
            return {"ok": True, "created": False, "facts": facts, "duplicate": True}

        facts.append(memory)
        facts = facts[-max_facts:]
        conn.execute(
            "UPDATE campaign_known_npcs SET notes = ?, updated_at = datetime('now') WHERE id = ?",
            ("; ".join(facts), row["id"]),
        )
        if managed:
            conn.commit()
        return {"ok": True, "created": False, "facts": facts}
    finally:
        if managed:
            conn.close()
