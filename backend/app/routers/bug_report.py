"""
Bug report endpoint for beta testers.

POST /api/bug-report — authenticated; collects game state + posts GitHub issue.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

DB_PATH = "/data/ai_gm.db"
GITHUB_API = "https://api.github.com"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BugReportReq(BaseModel):
    observation: str
    reproduction: str = ""
    report_type: str = "bug"
    campaign_id: int | None = None
    js_errors: list[dict] | None = None


def _collect_context(user_id: int, campaign_id: int | None) -> dict[str, Any]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        user_row = conn.execute(
            "SELECT id, username, display_name FROM users WHERE id = ? LIMIT 1", (user_id,)
        ).fetchone()
        user_info: dict = dict(user_row) if user_row else {"id": user_id}

        if not campaign_id:
            row = conn.execute(
                "SELECT id FROM campaigns WHERE owner_user_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            if row:
                campaign_id = row["id"]

        character_info: dict = {}
        character_id_val: int | None = None
        last_turns: list[dict] = []
        campaign_info: dict = {}
        inventory: list[dict] = []
        combat_rolls: list[dict] = []
        active_combat_info: dict = {}

        if campaign_id:
            camp = conn.execute(
                "SELECT id, title, status FROM campaigns WHERE id = ? LIMIT 1", (campaign_id,)
            ).fetchone()
            if camp:
                campaign_info = dict(camp)

            char = conn.execute(
                """
                SELECT id, name, sheet_json, status
                FROM characters WHERE campaign_id = ? AND user_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (campaign_id, user_id),
            ).fetchone()
            if char:
                character_id_val = char["id"]
                sheet: dict = {}
                try:
                    sheet = json.loads(char["sheet_json"] or "{}")
                except Exception:
                    pass
                hp = sheet.get("hp", {})
                if isinstance(hp, dict):
                    hp_current = hp.get("current", "?")
                    hp_max = hp.get("max", "?")
                else:
                    hp_current = hp if hp is not None else "?"
                    hp_max = "?"
                mana = sheet.get("mana", {})
                mana_current = mana.get("current", None) if isinstance(mana, dict) else mana
                character_info = {
                    "id": char["id"],
                    "name": char["name"],
                    "status": char["status"],
                    "hp_current": hp_current,
                    "hp_max": hp_max,
                    "mana_current": mana_current,
                    "mana_max": mana.get("max", None) if isinstance(mana, dict) else None,
                    "level": sheet.get("level", "?"),
                    "archetype": sheet.get("archetype", "?"),
                    "conditions": sheet.get("conditions", []),
                    "stats": sheet.get("stats", {}),
                    "gold": sheet.get("gold", 0),
                }

            turns = conn.execute(
                """
                SELECT turn_number, route, user_text, assistant_text, created_at
                FROM campaign_turns
                WHERE campaign_id = ?
                ORDER BY turn_number DESC LIMIT 10
                """,
                (campaign_id,),
            ).fetchall()
            last_turns = [dict(t) for t in reversed(turns)]

            cr = conn.execute(
                """
                SELECT ct.turn_number, ct.actor, ct.event_type, ct.roll_value,
                       ct.damage, ct.hp_after, ct.target_name, ct.hit, ct.narrative
                FROM combat_turns ct
                JOIN active_combat ac ON ac.id = ct.combat_id
                WHERE ac.campaign_id = ?
                ORDER BY ct.id DESC LIMIT 20
                """,
                (campaign_id,),
            ).fetchall()
            combat_rolls = [dict(r) for r in reversed(cr)]

            ac = conn.execute(
                "SELECT round, current_turn, combatants, status FROM active_combat WHERE campaign_id = ? ORDER BY id DESC LIMIT 1",
                (campaign_id,),
            ).fetchone()
            if ac:
                try:
                    combatants = json.loads(ac["combatants"] or "[]")
                except Exception:
                    combatants = []
                active_combat_info = {
                    "round": ac["round"],
                    "current_turn": ac["current_turn"],
                    "status": ac["status"],
                    "combatants": combatants,
                }

        if character_id_val:
            inv = conn.execute(
                """
                SELECT item_key, weapon_key, consumable_key, quantity, equipped, slot, label
                FROM character_inventory WHERE character_id = ?
                """,
                (character_id_val,),
            ).fetchall()
            inventory = [dict(i) for i in inv]

        return {
            "user": user_info,
            "campaign": campaign_info,
            "character": character_info,
            "last_turns": last_turns,
            "inventory": inventory,
            "combat_rolls": combat_rolls,
            "active_combat": active_combat_info,
        }
    finally:
        conn.close()


def _build_github_body(req: BugReportReq, ctx: dict, user_agent: str) -> str:
    char = ctx.get("character", {})
    camp = ctx.get("campaign", {})
    user = ctx.get("user", {})
    turns = ctx.get("last_turns", [])
    inventory = ctx.get("inventory", [])
    combat_rolls = ctx.get("combat_rolls", [])
    active_combat = ctx.get("active_combat", {})

    char_line = ""
    if char:
        char_line = (
            f"HP: {char.get('hp_current','?')}/{char.get('hp_max','?')}, "
            f"level: {char.get('level','?')}, archetype: {char.get('archetype','?')}, "
            f"gold: {char.get('gold', 0)}"
        )
        if char.get("mana_current") is not None:
            char_line += f", mana: {char.get('mana_current','?')}/{char.get('mana_max','?')}"
        conds = char.get("conditions") or []
        if conds:
            char_line += f", conditions: {', '.join(str(c) for c in conds)}"

    stats = char.get("stats", {})
    stats_line = " | ".join(f"{k}: {v}" for k, v in stats.items()) if stats else "—"

    turns_md = ""
    for t in turns:
        turns_md += f"\n**Turn {t.get('turn_number','?')} [{t.get('route','?')}]**\n"
        turns_md += f"*Player:* {str(t.get('user_text') or '')[:500]}\n"
        assistant = str(t.get("assistant_text") or "")[:800]
        if assistant:
            turns_md += f"*GM:* {assistant}\n"

    inv_lines = []
    for item in inventory:
        key = item.get("item_key") or item.get("weapon_key") or item.get("consumable_key") or "?"
        label = item.get("label") or key
        qty = item.get("quantity", 1)
        eq = " [equipped]" if item.get("equipped") else ""
        inv_lines.append(f"- {label} ×{qty}{eq}")
    inventory_md = "\n".join(inv_lines) if inv_lines else "(puste)"

    rolls_md = ""
    if combat_rolls:
        for r in combat_rolls:
            hit_icon = "✅" if r.get("hit") else "❌"
            roll_str = f"d20={r.get('roll_value','?')}" if r.get("roll_value") is not None else ""
            dmg_str = f" dmg={r.get('damage','?')}" if r.get("damage") is not None else ""
            hp_str = f" hp_after={r.get('hp_after','?')}" if r.get("hp_after") is not None else ""
            rolls_md += f"\n- T{r.get('turn_number','?')} {hit_icon} **{r.get('actor','?')}** [{r.get('event_type','?')}] → {r.get('target_name','?')} | {roll_str}{dmg_str}{hp_str}"
            if r.get("narrative"):
                rolls_md += f"\n  _{str(r['narrative'])[:200]}_"

    combat_md = ""
    if active_combat:
        combat_md = f"Round: {active_combat.get('round','?')}, status: {active_combat.get('status','?')}, turn: {active_combat.get('current_turn','?')}\n"
        for c in active_combat.get("combatants", []):
            if isinstance(c, dict):
                combat_md += f"- {c.get('name','?')}: HP {c.get('hp_current','?')}/{c.get('hp_max','?')}, zone: {c.get('zone','?')}\n"

    js_errors_md = ""
    if req.js_errors:
        js_errors_md = "\n".join(
            f"- `{e.get('message','?')}` at {e.get('filename','?')}:{e.get('lineno','?')}"
            for e in req.js_errors[:10]
        )

    body = f"""**Obserwacja:** {req.observation}

**Reprodukcja:** {req.reproduction}

---

<details><summary>📊 Stan postaci</summary>

{char_line or '(brak aktywnej kampanii)'}

**Statystyki:** {stats_line}

**Kampania:** `{camp.get('title','?')}` (ID: {camp.get('id','?')}, status: {camp.get('status','?')})
**Postać:** {char.get('name','?')} (ID: {char.get('id','?')})

</details>

<details><summary>🎒 Ekwipunek</summary>

{inventory_md}

</details>

<details><summary>📜 Ostatnie tury (max 10)</summary>

{turns_md or '(brak tur)'}

</details>
"""

    if combat_rolls or active_combat:
        body += f"""
<details><summary>⚔️ Stan walki + rzuty</summary>

{combat_md or ''}
{rolls_md or '(brak rzutów)'}

</details>
"""

    if js_errors_md:
        body += f"""
<details><summary>⚠️ Błędy JS</summary>

{js_errors_md}

</details>
"""

    body += f"""
---
**Gracz:** `{user.get('username','?')}` (ID: {user.get('id','?')})
**Czas:** `{_now_iso()}`
**Przeglądarka:** `{user_agent[:200]}`
"""

    return body


@router.post("/bug-report")
async def submit_bug_report(
    req: BugReportReq,
    authorization: str | None = Header(default=None),
    user_agent: str | None = Header(default=None),
):
    from app.core.jwt_auth import require_current_user
    payload = require_current_user(authorization)
    user_id = int(payload.get("sub") or 0)

    if not (req.observation or "").strip():
        raise HTTPException(status_code=400, detail="observation is required")

    # Verify is_tester flag
    conn_check = sqlite3.connect(DB_PATH)
    conn_check.row_factory = sqlite3.Row
    try:
        u = conn_check.execute(
            "SELECT COALESCE(is_tester, 0) AS is_tester FROM users WHERE id = ? LIMIT 1", (user_id,)
        ).fetchone()
        if not u or not int(u["is_tester"] or 0):
            raise HTTPException(status_code=403, detail="Bug reporting not enabled for this account")
    finally:
        conn_check.close()

    github_pat = os.getenv("GITHUB_PAT", "").strip()
    github_repo = os.getenv("GITHUB_REPO", "szmidtpiotr/ai-gm").strip()

    ctx = _collect_context(user_id, req.campaign_id)
    ua = (user_agent or "unknown")[:300]

    is_feature = (req.report_type or "bug") == "feature"
    type_tag = "[FEATURE]" if is_feature else "[BUG]"
    gh_labels = ["enhancement", "tester-report"] if is_feature else ["bug", "tester-report"]
    title = f"{type_tag} {ctx['user'].get('username','?')} — {(req.observation or '')[:60]}"
    body = _build_github_body(req, ctx, ua)

    github_issue_url: str | None = None
    github_issue_number: int | None = None

    if github_pat and github_repo:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{GITHUB_API}/repos/{github_repo}/issues",
                    headers={
                        "Authorization": f"Bearer {github_pat}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    json={
                        "title": title,
                        "body": body,
                        "labels": gh_labels,
                    },
                )
                if resp.status_code == 201:
                    data = resp.json()
                    github_issue_url = data.get("html_url")
                    github_issue_number = data.get("number")
                    logger.info("bug_report_github_created", issue=github_issue_number, user_id=user_id)
                else:
                    logger.error("bug_report_github_failed", status=resp.status_code, body=resp.text[:500])
        except Exception as e:
            logger.error("bug_report_github_error", error=str(e))
    else:
        logger.warning("bug_report_no_github_pat", user_id=user_id)

    # Save locally regardless of GitHub success
    conn_save = sqlite3.connect(DB_PATH)
    try:
        conn_save.execute(
            """
            INSERT INTO bug_reports
                (user_id, campaign_id, observation, reproduction, report_type, context_json,
                 github_issue_url, github_issue_number, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                req.campaign_id,
                req.observation,
                req.reproduction,
                req.report_type or "bug",
                json.dumps(ctx, ensure_ascii=False),
                github_issue_url,
                github_issue_number,
                _now_iso(),
            ),
        )
        conn_save.commit()
    except Exception as e:
        logger.error("bug_report_db_error", error=str(e))
    finally:
        conn_save.close()

    return {
        "ok": True,
        "github_issue_url": github_issue_url,
        "github_issue_number": github_issue_number,
    }
