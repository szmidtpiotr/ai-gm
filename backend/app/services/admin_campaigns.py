"""Admin: campaigns, GM plan tooling, and summary regeneration."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from app.services.gm_plan_divergence import evaluate_campaign_plan_divergence
from app.services.gm_plan_generation_service import retry_initial_gm_plan_for_campaign
from app.services.gm_plan_schema import format_gm_plan_block, normalize_gm_plan
from app.services.history_summary_service import (
    SUMMARY_AUDIENCE_PLAYER,
    generate_campaign_summary,
    persist_summary,
    touch_rollup_cooldown_anchor,
)

DB_PATH = "/data/ai_gm.db"


def list_campaigns_by_owner(owner_user_id: int) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
                c.id,
                c.title,
                c.status,
                c.created_at,
                c.gm_plan_json,
                (SELECT COUNT(*) FROM campaign_turns ct WHERE ct.campaign_id = c.id) AS turn_count,
                (SELECT MAX(ct2.created_at) FROM campaign_turns ct2 WHERE ct2.campaign_id = c.id)
                    AS last_turn_at
            FROM campaigns c
            WHERE c.owner_user_id = ?
            ORDER BY c.id DESC
            """,
            (owner_user_id,),
        ).fetchall()
        items: list[dict] = []
        for r in rows:
            item = dict(r)
            try:
                plan = normalize_gm_plan(str(item.get("gm_plan_json") or ""))
                item["gm_plan_ready"] = bool(format_gm_plan_block(str(item.get("gm_plan_json") or "")).strip())
                item["active_arc_id"] = plan.get("active_arc_id")
            except Exception:
                item["gm_plan_ready"] = False
                item["active_arc_id"] = None
            item.pop("gm_plan_json", None)
            items.append(item)
        return items
    finally:
        conn.close()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def get_campaign_gm_plan_admin(campaign_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT id, title, status, owner_user_id, language, model_id, gm_plan_json
            FROM campaigns
            WHERE id = ?
            """,
            (campaign_id,),
        ).fetchone()
        if not row:
            raise KeyError("campaign_not_found")
        characters_count = 0
        try:
            crow = conn.execute(
                "SELECT COUNT(*) AS n FROM characters WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
            characters_count = int(crow["n"] if crow else 0)
        except sqlite3.OperationalError:
            characters_count = 0
        raw_plan = str(row["gm_plan_json"] or "")
        normalized = normalize_gm_plan(raw_plan)
        divergence = evaluate_campaign_plan_divergence(
            conn,
            campaign_id=campaign_id,
            raw_plan=raw_plan,
            limit=4,
        )
        return {
            "campaign_id": int(row["id"]),
            "title": str(row["title"] or ""),
            "status": str(row["status"] or ""),
            "owner_user_id": int(row["owner_user_id"] or 0),
            "language": str(row["language"] or "pl"),
            "model_id": str(row["model_id"] or ""),
            "gm_plan_json": normalized,
            "gm_plan_raw": raw_plan,
            "formatted_plan": format_gm_plan_block(raw_plan),
            "gm_plan_ready": bool(format_gm_plan_block(raw_plan).strip()),
            "characters_count": characters_count,
            "divergence": divergence,
        }
    finally:
        conn.close()


def replace_campaign_gm_plan_admin(campaign_id: int, gm_plan_json: dict) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()
        if not row:
            raise KeyError("campaign_not_found")
        normalized = normalize_gm_plan(json.dumps(gm_plan_json or {}, ensure_ascii=False))
        conn.execute(
            "UPDATE campaigns SET gm_plan_json = ? WHERE id = ?",
            (json.dumps(normalized, ensure_ascii=False), campaign_id),
        )
        conn.commit()
    finally:
        conn.close()
    return get_campaign_gm_plan_admin(campaign_id)


def advance_campaign_scene_admin(campaign_id: int, note: str = "") -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, gm_plan_json FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()
        if not row:
            raise KeyError("campaign_not_found")

        tr = conn.execute(
            """
            SELECT MAX(turn_number) AS m
            FROM campaign_turns
            WHERE campaign_id = ? AND route = 'narrative'
            """,
            (campaign_id,),
        ).fetchone()
        through_turn = int(tr["m"] or 0) if tr else 0

        plan = normalize_gm_plan(str(row["gm_plan_json"] or ""))
        arcs: dict = plan.get("arcs") if isinstance(plan.get("arcs"), dict) else {}
        active = plan.get("active_arc_id")
        if isinstance(active, str) and active.strip() and active in arcs:
            key = active
        elif arcs:
            key = next(iter(arcs.keys()))
        else:
            key = "default"
            arcs["default"] = {
                "id": "default",
                "title": "",
                "status": "active",
                "scene_goals": [],
                "hooks": {},
            }
        arc = arcs.get(key) if isinstance(arcs.get(key), dict) else {}
        ordn = int(arc.get("current_scene_ordinal") or plan.get("current_scene_ordinal") or 0) + 1
        arc["current_scene_ordinal"] = ordn
        log = arc.get("scene_log")
        if not isinstance(log, list):
            log = []
        entry = {"ordinal": ordn, "ended_at": _now_iso(), "through_turn": through_turn}
        nt = str(note or "").strip()
        if nt:
            entry["note"] = nt
        log.append(entry)
        arc["scene_log"] = log
        arcs[key] = arc
        plan["arcs"] = arcs
        plan["active_arc_id"] = key
        normalized = normalize_gm_plan(json.dumps(plan, ensure_ascii=False))
        conn.execute(
            "UPDATE campaigns SET gm_plan_json = ? WHERE id = ?",
            (json.dumps(normalized, ensure_ascii=False), campaign_id),
        )
        conn.commit()
    finally:
        conn.close()
    return get_campaign_gm_plan_admin(campaign_id)


def regenerate_campaign_gm_plan_admin(campaign_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, owner_user_id FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()
        if not row:
            raise KeyError("campaign_not_found")
        owner_id = int(row["owner_user_id"] or 0)
        ok, err = retry_initial_gm_plan_for_campaign(
            conn,
            campaign_id=campaign_id,
            owner_user_id=owner_id,
        )
        if not ok:
            raise ValueError(err or "gm_plan_regeneration_failed")
    finally:
        conn.close()
    return get_campaign_gm_plan_admin(campaign_id)


def regenerate_campaign_summary_admin(campaign_id: int) -> dict:
    """
    Regenerate stored AI summary for a campaign (admin).
    Uses campaign owner for per-user LLM settings.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, owner_user_id FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()
        if not row:
            raise KeyError("campaign_not_found")
        owner_id = int(row["owner_user_id"])
    finally:
        conn.close()

    try:
        result = generate_campaign_summary(
            campaign_id=campaign_id,
            user_id=owner_id,
            max_turns=200,
            audience=SUMMARY_AUDIENCE_PLAYER,
        )
    except ValueError as e:
        if str(e) == "campaign_not_found":
            raise KeyError("campaign_not_found") from e
        raise

    summary_id = None
    text = (result.get("summary") or "").strip()
    if text:
        conn2 = sqlite3.connect(DB_PATH)
        try:
            summary_id = persist_summary(
                conn2,
                campaign_id=campaign_id,
                summary_text=result["summary"],
                model_used=str(result.get("model_used") or ""),
                included_turn_count=int(result.get("included_turn_count") or 0),
                audience=SUMMARY_AUDIENCE_PLAYER,
            )
            touch_rollup_cooldown_anchor(conn2, campaign_id)
        finally:
            conn2.close()

    return {
        "ok": True,
        "campaign_id": campaign_id,
        "persisted": bool(summary_id),
        "warning": result.get("warning"),
    }
