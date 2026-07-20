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

import structlog
from app.core.db_runtime import resolve_db_path

logger = structlog.get_logger()

DB_PATH = Path(resolve_db_path())

# Cap exposed to MG. More history → bigger prompt → no real upside since the
# user explicitly chose "last 10 met" during BUG-03 discovery.
DEFAULT_CONTEXT_LIMIT = 10

VALID_RELATIONS = ("friendly", "neutral", "hostile")

_PURCHASE_COUNT_COL = "purchase_count"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _has_stats(raw: Any) -> bool:
    """True if a stored stats_json holds an actual stat block (not NULL/empty/'{}')."""
    if not raw:
        return False
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return False
    return isinstance(parsed, dict) and len(parsed) > 0


def ensure_npc_stats(
    conn: sqlite3.Connection, campaign_id: int, npc_name: str
) -> dict[str, int] | None:
    """Lazily resolve + persist the 7 ability stats of a campaign NPC (FAZA S, S3).

    Called ONLY from the opposed-skill-test path (S4) — background NPCs never pay for
    stats. Resolution order:
      1. campaign_known_npcs.stats_json already set → parse and return (stability:
         the same innkeeper always rolls with the same stats, per campaign).
      2. else npcs.stats_json template (global, admin-authored) → use it.
      3. else derive from archetype via actor_stats.stats_for_actor (same keyword
         heuristic enemies use in S2 — the archetype table is NOT forked here).
    The resolved block is written back to campaign_known_npcs (row upserted by name),
    so step 1 hits on every later call.

    Nameless targets ("a random passer-by") get no row and return None — the caller
    falls back to a fixed DC from skill_counters (handled in S4).
    """
    name = (npc_name or "").strip()
    if not name:
        return None

    from app.services.actor_stats import parse_stats_json, stats_for_actor

    existing = conn.execute(
        "SELECT id, stats_json FROM campaign_known_npcs WHERE campaign_id = ? AND npc_name = ?",
        (campaign_id, name),
    ).fetchone()

    if existing and _has_stats(existing["stats_json"]):
        return parse_stats_json(existing["stats_json"])

    # Derive: template wins over archetype.
    template_id = _lookup_catalog_npc_id(conn, name)
    stats: dict[str, int] | None = None
    if template_id is not None:
        trow = conn.execute(
            "SELECT stats_json FROM npcs WHERE id = ?", (template_id,)
        ).fetchone()
        if trow and _has_stats(trow["stats_json"]):
            stats = parse_stats_json(trow["stats_json"])
    if stats is None:
        stats = stats_for_actor(name)

    stored = json.dumps(stats, ensure_ascii=False)
    if existing:
        conn.execute(
            "UPDATE campaign_known_npcs SET stats_json = ?, updated_at = datetime('now') WHERE id = ?",
            (stored, existing["id"]),
        )
    else:
        conn.execute(
            """
            INSERT INTO campaign_known_npcs (campaign_id, npc_id, npc_name, stats_json)
            VALUES (?, ?, ?, ?)
            """,
            (campaign_id, template_id, name, stored),
        )
    conn.commit()
    return stats


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


# ── #1294 (Warstwa 1) — seed roster from the GM plan ──────────────────────────
# The plan's `key_npcs[]` is the authored/generated cast. Seeding it into
# campaign_known_npcs removes the reliance on the LLM voluntarily emitting
# `[NPC_MEMORY]` / `npc_met` for NPCs that were designed up-front. Idempotent, so
# it's safe to call on every turn (backfills existing campaigns on next turn) and
# from every mode's turn path (new campaign / template / MP).

# Importance tiers that earn a roster row. `minor` = background flavour, skipped.
SEED_IMPORTANCE = ("critical", "supporting")


def _load_plan(conn: sqlite3.Connection, campaign_id: int) -> dict[str, Any]:
    """Best-effort read of a campaign's gm_plan_json. Returns {} on any miss."""
    try:
        row = conn.execute(
            "SELECT gm_plan_json FROM campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
    except sqlite3.OperationalError:
        return {}
    if not row:
        return {}
    raw = row["gm_plan_json"] if "gm_plan_json" in row.keys() else row[0]
    if not raw:
        return {}
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def seed_known_npcs_from_plan(
    conn: sqlite3.Connection,
    campaign_id: int,
    *,
    importance_tiers: tuple[str, ...] = SEED_IMPORTANCE,
) -> list[str]:
    """Seed campaign_known_npcs from `gm_plan_json.key_npcs`.

    Seeds NPCs whose `importance` is in `importance_tiers` and that are not
    flagged `alive=False`. Delegates to `record_npc_met` (idempotent on
    (campaign_id, npc_name)), so repeat calls are no-ops and the catalog `npc_id`
    is linked when the plan name/key matches an `npcs` row. Returns the list of
    NPC names that were newly created this call. Non-fatal by design.
    """
    plan = _load_plan(conn, campaign_id)
    key_npcs = plan.get("key_npcs")
    if not isinstance(key_npcs, list):
        return []

    created: list[str] = []
    for n in key_npcs:
        if not isinstance(n, dict):
            continue
        name = str(n.get("name") or "").strip()
        if not name:
            continue
        if n.get("alive") is False:
            continue
        importance = str(n.get("importance") or "").strip().lower()
        if importance and importance not in importance_tiers:
            continue
        try:
            res = record_npc_met(
                campaign_id=campaign_id,
                name=name,
                role=(str(n.get("role")).strip() if n.get("role") else None),
                notes=(importance or None),
                conn=conn,
            )
            if res.get("ok") and res.get("new"):
                created.append(name)
        except Exception as ex:  # never let seeding break a turn
            logger.warning(
                "known_npc_seed_failed", campaign_id=campaign_id, name=name, error=str(ex)
            )
    if created:
        logger.info(
            "known_npcs_seeded_from_plan", campaign_id=campaign_id, count=len(created)
        )
    return created


# ── #1295 (Warstwa 2) — deterministic capture from narration ─────────────────
# Closed-vocabulary scan (plan.key_npcs names ∪ npcs.label). No NER: a narrated
# name only becomes a roster row if it is already a known entity somewhere. Truly
# novel names still rely on the [NPC_MEMORY] tag — a deliberate boundary that
# avoids false positives from arbitrary prose.

# A name must be at least this long to be used as a match token (guards against
# noisy 1-2 char fragments matching everywhere).
_MIN_TOKEN_LEN = 3


def _match_tokens(name: str) -> list[str]:
    """Return the strings to word-boundary match for a display name.

    Full name plus, for multi-word names, the leading token (the given name) so
    that "Brunn" matches the roster entry "Brunn Żelaznoręki".
    """
    name = (name or "").strip()
    if not name:
        return []
    tokens = [name]
    parts = name.split()
    if len(parts) > 1 and len(parts[0]) >= _MIN_TOKEN_LEN:
        tokens.append(parts[0])
    return tokens


def capture_known_names_in_narration(
    conn: sqlite3.Connection,
    campaign_id: int,
    text: str,
    *,
    turn_num: int | None = None,
) -> list[str]:
    """Scan narration for known-entity names and record any not yet in the roster.

    Vocabulary = plan.key_npcs names ∪ catalog npcs.label. Matching is
    word-boundary, case-insensitive. Idempotent against the current roster.
    Returns the list of names newly recorded this call.
    """
    text = text or ""
    if not text.strip():
        return []

    # Build the vocabulary: (match_tokens, canonical_name, role).
    entries: list[tuple[list[str], str, str | None]] = []
    seen_vocab: set[str] = set()

    plan = _load_plan(conn, campaign_id)
    for n in plan.get("key_npcs") or []:
        if not isinstance(n, dict):
            continue
        if n.get("alive") is False:
            continue
        name = str(n.get("name") or "").strip()
        if not name or name.lower() in seen_vocab:
            continue
        seen_vocab.add(name.lower())
        entries.append(
            (_match_tokens(name), name, str(n.get("role")).strip() if n.get("role") else None)
        )

    try:
        for row in conn.execute(
            "SELECT label FROM npcs WHERE label IS NOT NULL AND TRIM(label) != ''"
        ):
            label = str(row["label"]).strip()
            if not label or label.lower() in seen_vocab:
                continue
            seen_vocab.add(label.lower())
            entries.append((_match_tokens(label), label, None))
    except sqlite3.OperationalError:
        pass  # npcs table absent — plan-only vocab still works

    known = {
        str(r["npc_name"]).lower()
        for r in conn.execute(
            "SELECT npc_name FROM campaign_known_npcs WHERE campaign_id = ?", (campaign_id,)
        )
        if r["npc_name"]
    }

    captured: list[str] = []
    for tokens, name, role in entries:
        if name.lower() in known:
            continue
        hit = any(
            re.search(rf"(?<!\w){re.escape(tok)}(?!\w)", text, re.IGNORECASE)
            for tok in tokens
        )
        if not hit:
            continue
        try:
            record_npc_met(
                campaign_id=campaign_id,
                name=name,
                role=role,
                first_met_turn=turn_num,
                conn=conn,
            )
            known.add(name.lower())
            captured.append(name)
        except Exception as ex:
            logger.warning(
                "known_npc_capture_failed", campaign_id=campaign_id, name=name, error=str(ex)
            )
    if captured:
        logger.info(
            "known_npcs_captured_from_narration",
            campaign_id=campaign_id,
            count=len(captured),
        )
    return captured
