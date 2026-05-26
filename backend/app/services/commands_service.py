import json
import sqlite3
from dataclasses import dataclass
from typing import Any

DB_PATH = "/data/ai_gm.db"


@dataclass
class CommandResult:
    ok: bool
    type: str
    command: str
    payload: dict[str, Any]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def is_command(text: str) -> bool:
    return (text or "").strip().startswith("/")


def execute_command_logic(character_id: int, text: str, forced_d20: int | None = None) -> CommandResult:
    text = (text or "").strip()

    if not text.startswith("/"):
        raise ValueError("Not a command")

    parts = text.split(" ", 1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute("SELECT * FROM characters WHERE id = ?", (character_id,))
        row = cur.fetchone()

        if not row:
            raise LookupError("Character not found")

        sheet = json.loads(row["sheet_json"])

        if cmd == "/help":
            return CommandResult(
                ok=True,
                type="command",
                command="/help",
                payload={
                    "ok": True,
                    "type": "command",
                    "command": "/help",
                    "message": "Commands: /help, /name, /sheet, /inv, /roll, /say, /do, /ooc"
                },
            )

        if cmd == "/name":
            if not arg:
                raise ValueError("Usage: /name NEW_NAME")

            sheet["name"] = arg
            cur.execute(
                "UPDATE characters SET name = ?, sheet_json = ? WHERE id = ?",
                (arg, json.dumps(sheet), character_id)
            )
            conn.commit()

            return CommandResult(
                ok=True,
                type="command",
                command="/name",
                payload={
                    "result": {  # ← Wrap in "result"
                        "character_name": arg
                    }
                },
            )

        if cmd == "/sheet":
            return CommandResult(
                ok=True,
                type="command",
                command="/sheet",
                payload={
                    "result": {  # ← Wrap in "result" for frontend
                        "sheet": sheet
                    }
                },
            )

        # Stage 8 D1 — `/debug` subcommands. Admin-only path: this function is
        # called from the admin-gated POST /api/debug/command endpoint; we don't
        # re-check the admin flag here. The HTTP layer is the gate.
        if cmd == "/debug":
            return _execute_debug_command(cur, conn, character_id, row, sheet, arg, forced_d20=forced_d20)

        raise ValueError(f"Unknown command: {cmd}")
    finally:
        conn.close()


def _execute_debug_command(cur, conn, character_id: int, char_row, sheet: dict, arg: str, forced_d20: int | None = None) -> CommandResult:
    """Implements `/debug ...` subcommands. Mutates DB where requested."""
    sub_parts = arg.split(" ", 1) if arg else [""]
    sub = sub_parts[0].strip().lower()
    sub_arg = sub_parts[1].strip() if len(sub_parts) > 1 else ""

    # Default: dump-state when called with no subcommand
    if not sub or sub == "dump-state":
        # Pull last turn (any campaign) for quick reference
        try:
            cur.execute(
                """
                SELECT id, campaign_id, turn_number, route, user_text, assistant_text, created_at
                FROM campaign_turns
                WHERE campaign_id = (SELECT campaign_id FROM characters WHERE id = ?)
                ORDER BY id DESC LIMIT 1
                """,
                (character_id,),
            )
            last = cur.fetchone()
            last_turn = dict(last) if last else None
        except Exception:
            last_turn = None
        return CommandResult(
            ok=True, type="command", command="/debug dump-state",
            payload={"result": {
                "sub": "dump-state",
                "character_id": character_id,
                "name": char_row["name"],
                "campaign_id": char_row["campaign_id"],
                "status": char_row["status"],
                "sheet": sheet,
                "last_turn": last_turn,
            }},
        )

    if sub == "set-hp":
        try:
            target = int(sub_arg)
        except (TypeError, ValueError):
            raise ValueError("Usage: /debug set-hp N")
        max_hp = int(sheet.get("max_hp") or 1)
        new_hp = max(0, min(max_hp, target))
        sheet["current_hp"] = new_hp
        cur.execute(
            "UPDATE characters SET sheet_json = ? WHERE id = ?",
            (json.dumps(sheet, ensure_ascii=False), character_id),
        )
        conn.commit()
        return CommandResult(
            ok=True, type="command", command="/debug set-hp",
            payload={"result": {"sub": "set-hp", "current_hp": new_hp, "max_hp": max_hp, "clamped": new_hp != target}},
        )

    if sub == "set-state":
        if not sub_arg:
            raise ValueError("Usage: /debug set-state NARRATIVE|COMBAT|SKILL_TEST_PENDING")
        target = sub_arg.upper().strip()
        # WSM's VALID_STATES set: see world_state_machine.py.
        valid = ("NARRATIVE", "COMBAT", "SKILL_TEST_PENDING", "FEAR_TEST_PENDING", "DEATH_SAVE_PENDING")
        if target not in valid:
            raise ValueError(f"State must be one of: {', '.join(valid)}")
        campaign_id = char_row["campaign_id"]
        if not campaign_id:
            raise ValueError("Character has no active campaign")
        cur.execute("SELECT session_flags FROM game_sessions WHERE id = ?", (str(campaign_id),))
        srow = cur.fetchone()
        try:
            flags = json.loads(srow["session_flags"]) if srow and srow["session_flags"] else {}
        except Exception:
            flags = {}
        # WSM reads session_flags["state"] — NOT "state_machine". Writing the
        # right key is what makes this command actually move the engine.
        previous = flags.get("state", "NARRATIVE")
        flags["state"] = target
        # SKILL_TEST_PENDING (and other *_PENDING states) require a matching
        # pending payload — without it the resolver has nothing to roll.
        # Auto-seed a minimal pending_skill_test stub so the player UI can
        # surface the Roll Popup; admin can edit the values from the drawer.
        warning = None
        if target == "SKILL_TEST_PENDING" and "pending_skill_test" not in flags:
            import random as _rand
            import uuid as _uuid
            flags["pending_skill_test"] = {
                "skill_test_id": f"st-dbg-{_uuid.uuid4().hex[:8]}",
                "skill_key": "athletics",
                "skill_label": "Atletyka (debug)",
                "dc": 12,
                "modifier_breakdown": {
                    "governing_stat": "STR",
                    "stat_mod": 0,
                    "skill_rank": 0,
                    "proficiency": 0,
                    "total": 0,
                },
                # Stage 10-C+ — server-committed d20 so /debug-seeded pendings
                # behave the same as real ones (no client reroll possible).
                "committed_d20": _rand.randint(1, 20),
                "source": "debug_set_state",
            }
            warning = "Auto-seed: dodano stub pending_skill_test (Atletyka DC 12)."
        if target == "COMBAT" and "combat_state" not in flags:
            warning = "UWAGA: brak active combat_state — engine może być w niespójnym stanie."
        if target == "FEAR_TEST_PENDING" and "pending_fear_test" not in flags:
            warning = "UWAGA: brak pending_fear_test — resolver nie ma czego rozwiązać."
        if target == "DEATH_SAVE_PENDING":
            warning = "UWAGA: postać będzie zablokowana aż do rzutu na śmierć."
        cur.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE id = ?",
            (json.dumps(flags, ensure_ascii=False), str(campaign_id)),
        )
        conn.commit()
        return CommandResult(
            ok=True, type="command", command="/debug set-state",
            payload={"result": {
                "sub": "set-state",
                "state": target,
                "previous": previous,
                "campaign_id": campaign_id,
                "warning": warning,
            }},
        )

    if sub == "reset-cooldowns":
        sheet["short_rests_used"] = 0
        sheet["death_saves_failed"] = 0
        cur.execute(
            "UPDATE characters SET sheet_json = ? WHERE id = ?",
            (json.dumps(sheet, ensure_ascii=False), character_id),
        )
        # Wipe dungeon cooldown rows for this character.
        cur.execute("DELETE FROM character_dungeon_runs WHERE character_id = ?", (character_id,))
        conn.commit()
        return CommandResult(
            ok=True, type="command", command="/debug reset-cooldowns",
            payload={"result": {"sub": "reset-cooldowns", "short_rests_used": 0, "death_saves_failed": 0}},
        )

    if sub == "roll":
        return _execute_roll_command(cur, conn, character_id, char_row, sheet, sub_arg, forced_d20=forced_d20)

    if sub == "xp":
        return _execute_xp_command(cur, conn, character_id, sheet, sub_arg)

    raise ValueError(
        f"Unknown debug subcommand: /debug {sub}. "
        f"Available: dump-state, set-hp N, set-state STATE, reset-cooldowns, roll [SKILL], xp add|set N"
    )


def _resolve_skill_input(conn, raw: str) -> str | None:
    """Translate a user-typed skill arg to canonical skill key.
    Accepts: 'stealth', 'skradanie', 'Skradanie', 'percepcja' etc.
    Returns key if found, None otherwise.
    """
    if not raw or not conn:
        return None
    norm = raw.strip().lower()
    try:
        rows = conn.execute("SELECT key, label FROM game_config_skills").fetchall()
        for r in rows:
            k = str(r["key"]).lower()
            lbl = str(r["label"] or "").lower()
            if k == norm or lbl == norm or k == norm.replace(" ", "_"):
                return str(r["key"])
        # Substring fallback — start-with match on label
        for r in rows:
            lbl = str(r["label"] or "").lower()
            if lbl and lbl.startswith(norm):
                return str(r["key"])
    except Exception:
        pass
    return None


def _execute_roll_command(cur, conn, character_id: int, char_row, sheet: dict, skill_arg: str, forced_d20: int | None = None) -> "CommandResult":
    """Admin-only /debug roll [skill_key] [value?] — seeds a pending_skill_test and returns skill_test_pending payload.
    If forced_d20 is provided (1-20), it is committed as the authoritative roll value instead of a random one.
    """
    import random as _rand
    import uuid as _uuid
    from app.services.skill_service import calc_skill_modifier_info, _skill_label, _get_counter

    campaign_id = char_row["campaign_id"]
    if not campaign_id:
        raise ValueError("Character has no active campaign — assign one first")

    raw_arg = (skill_arg or "").strip()
    if not raw_arg:
        skill_key = "athletics"
    else:
        # Try matching as label (Polish name) first, fall back to key form
        skill_key = _resolve_skill_input(conn, raw_arg) or raw_arg.lower().replace(" ", "_")

    # Validate skill exists in DB or known set — fall back gracefully
    mod_info = calc_skill_modifier_info(sheet, skill_key)
    label = _skill_label(skill_key)
    counter = _get_counter(conn, skill_key)
    dc = counter.get("dc", 12)

    committed = int(forced_d20) if (forced_d20 is not None and 1 <= int(forced_d20) <= 20) else _rand.randint(1, 20)
    pending = {
        "skill_test_id": f"st-roll-{_uuid.uuid4().hex[:8]}",
        "skill_key": skill_key,
        "skill_label": label,
        "dc": dc,
        "counter": counter,
        "modifier_breakdown": mod_info,
        "committed_d20": committed,
        "source": "admin_roll_forced" if forced_d20 is not None else "admin_roll_command",
    }

    gs_row = conn.execute(
        "SELECT id, session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    if not gs_row:
        raise ValueError("No game session found for this campaign — start one first")

    try:
        flags = json.loads(gs_row["session_flags"] or "{}")
    except Exception:
        flags = {}

    flags["pending_skill_test"] = pending
    flags["state"] = "SKILL_TEST_PENDING"

    conn.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
        (json.dumps(flags, ensure_ascii=False), campaign_id),
    )
    conn.commit()

    return CommandResult(
        ok=True, type="command", command="/debug roll",
        payload={
            "skill_test_pending": pending,
            "result": {
                "sub": "roll",
                "skill_key": skill_key,
                "skill_label": label,
                "dc": dc,
                "committed_d20": pending["committed_d20"],
                "modifier": mod_info["total"],
            },
        },
    )


def _execute_xp_command(cur, conn, character_id: int, sheet: dict, arg: str) -> "CommandResult":
    """Admin `/debug xp add N` / `/debug xp set N` — direct XP injection for testing."""
    from app.services.xp_service import grant_character_xp, apply_levelup_if_needed, get_hero_level

    parts = (arg or "").strip().split()
    if len(parts) < 2:
        raise ValueError("Usage: /debug xp add N  |  /debug xp set N")

    op = parts[0].lower()
    try:
        n = int(parts[1])
    except (ValueError, TypeError):
        raise ValueError("N must be an integer")

    if op not in ("add", "set"):
        raise ValueError("Usage: /debug xp add N  |  /debug xp set N")

    if op == "set":
        if n < 0:
            raise ValueError("N must be >= 0 for set")
        sheet["xp_available"] = n
        # Also adjust lifetime so level stays consistent
        lifetime_old = int(sheet.get("xp_lifetime_earned") or 0)
        xp_avail_old = int(sheet.get("xp_available") or 0)
        # Bump lifetime by the delta (set only increases lifetime, never decreases)
        delta = max(0, n - xp_avail_old)
        sheet["xp_lifetime_earned"] = lifetime_old + delta
        sheet["xp_available"] = n
    else:  # add
        if n <= 0:
            raise ValueError("N must be > 0 for add")
        sheet["xp_available"] = int(sheet.get("xp_available") or 0) + n
        sheet["xp_lifetime_earned"] = int(sheet.get("xp_lifetime_earned") or 0) + n

    levelup = apply_levelup_if_needed(sheet, conn)

    cur.execute(
        "UPDATE characters SET sheet_json = ? WHERE id = ?",
        (json.dumps(sheet, ensure_ascii=False), character_id),
    )
    conn.commit()

    return CommandResult(
        ok=True, type="command", command=f"/debug xp {op}",
        payload={"result": {
            "sub": f"xp {op}",
            "op": op,
            "amount": n,
            "xp_available": int(sheet["xp_available"]),
            "xp_lifetime_earned": int(sheet.get("xp_lifetime_earned") or 0),
            "level": get_hero_level(sheet),
            "level_up": levelup,
        }},
    )