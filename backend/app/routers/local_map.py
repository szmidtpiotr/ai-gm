"""Local map API — #993 FAZA ML.

Player-facing endpoints for the local hex grid (map_level=1) inside a settlement.

  GET  /api/campaigns/{campaign_id}/local-map
       Returns the local hex grid for the hub the party currently occupies,
       plus the party's current local hex position (if any).

  POST /api/campaigns/{campaign_id}/local-travel
       Move the party to a local hex (+15 min game clock).
       Body: {"hex_id": <world_hexes.id>}
"""
from __future__ import annotations

import json
import random
import sqlite3
from typing import Optional
from app.core.db_runtime import resolve_db_path

# PT10 #1120: fallback enemy pool when local hex has no encounter_pool set
_LOCAL_ENCOUNTER_FALLBACK_POOL = ["bandit", "unknown_attacker", "goblin"]

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.location_factory import LocationSource, create_location
from app.services.local_hex_service import (
    LOCAL_MAP_THRESHOLD,
    LOCAL_TRAVEL_MINUTES,
    auto_assign_local_hex,
    count_active_sublocs,
    get_hub_hex_id,
    get_local_hexes,
    get_local_hex_for_subloc,
    normalize_hub_local_hexes,
)
from app.services.movement_service import (
    MovementProfile,
    MovementStep,
    run_step_sequence,
)
from app.services.world_service import (
    SETTLEMENT_SUBLOC_DEFAULTS,
    generate_sublocs_for_settlement,
    maybe_lazy_enrich_subloc,
)
from app.core.logging import get_logger

DB_PATH = resolve_db_path()
router = APIRouter(tags=["local-map"])
logger = get_logger(__name__)


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _get_campaign_session(conn: sqlite3.Connection, campaign_id: int) -> Optional[dict]:
    row = conn.execute(
        "SELECT id, session_flags, current_location_id FROM game_sessions WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    return dict(row) if row else None


def _get_location(conn: sqlite3.Connection, location_id: int) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM game_locations WHERE id = ? AND is_active = 1", (location_id,)
    ).fetchone()
    return dict(row) if row else None


def _hub_key_for_location(loc: dict) -> Optional[str]:
    """Resolve hub key: if loc is a sub-loc, return parent_key; if macro, return loc.key."""
    if loc.get("location_type") == "sub":
        return loc.get("parent_key")
    return loc["key"]


def _slug(text: str) -> str:
    import re, unicodedata
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "_", t).strip("_").lower()
    return t or "osada"


def _ensure_settlement_local_map(
    conn: sqlite3.Connection, campaign_id: int, flags: dict
) -> Optional[str]:
    """Lazy FAZA ML (#1212): gdy drużyna stoi na hexie-osadzie (village/town/city/…)
    bez sub-lokacji, wygeneruj zakątki wg typu + hexy map_level=1. Dzięki temu KAŻDA
    odwiedzona osada dostaje mapę lokalną, nie tylko te zatwierdzone w adminie.
    Zwraca hub_key lub None (hex nie jest osadą). Idempotentne."""
    cur = flags.get("current_hex") or {}
    q, r = cur.get("q"), cur.get("r")
    if q is None or r is None:
        return None
    hx = conn.execute(
        "SELECT id, hex_type, label, location_key FROM world_hexes "
        "WHERE q=? AND r=? AND map_level=0 AND is_active=1 LIMIT 1",
        (int(q), int(r)),
    ).fetchone()
    if not hx:
        return None
    subtypes = SETTLEMENT_SUBLOC_DEFAULTS.get(str(hx["hex_type"] or ""))
    if not subtypes:
        return None  # nie osada — brak mapy lokalnej

    hub_key = hx["location_key"]
    label = hx["label"] or f"Osada {q},{r}"
    if not hub_key:
        # #1526 (fala 3) — jedne drzwi. Ta sciezka pisala `world_hex_q/r` wprost
        # w INSERT, omijajac kanonicznego writera → reconcile odpinal huby przy
        # starcie backendu (#1305). Teraz heks wiaze fabryka.
        hub_key = create_location(
            conn,
            key=_slug(label),
            label=label,
            source=LocationSource.AUTO_GENERATED,
            location_type="macro",
            hex_q=int(q),
            hex_r=int(r),
            unique_key=True,
        )["key"]
    else:
        # get_hub_hex_id wymaga kotwicy world_hex_q/r na lokacji-hubie.
        conn.execute(
            "UPDATE game_locations SET world_hex_q=?, world_hex_r=? "
            "WHERE key=? AND (world_hex_q IS NULL OR world_hex_r IS NULL)",
            (int(q), int(r), hub_key),
        )
        conn.commit()

    if count_active_sublocs(conn, hub_key) < LOCAL_MAP_THRESHOLD:
        picks = list(subtypes)[:4]
        generate_sublocs_for_settlement(conn, hub_key, picks)
        first = conn.execute(
            "SELECT key FROM game_locations WHERE parent_key=? AND is_active=1 ORDER BY id ASC LIMIT 1",
            (hub_key,),
        ).fetchone()
        if first:
            auto_assign_local_hex(conn, first["key"], hub_key, campaign_id)
        conn.commit()
        logger.info(
            "settlement_local_map_generated",
            campaign_id=campaign_id, hub_key=hub_key, subtypes=picks,
        )
    return hub_key


def _check_local_encounter(target: dict, cleared_local_hexes: list) -> Optional[dict]:
    """PT10 #1120: Roll encounter for a local hex.

    Returns encounter dict {"enemy_key": str, "hex_label": str} if triggered, else None.
    Respects encounter_cleared guard (cleared_local_hexes = list of hex IDs already fought).
    """
    chance = float(target.get("encounter_chance") or 0.0)
    if chance <= 0.0:
        return None

    hex_id = target.get("id")
    if hex_id is not None and hex_id in cleared_local_hexes:
        return None

    if random.random() >= chance:
        return None

    pool = target.get("encounter_pool") or []
    if isinstance(pool, str):
        try:
            pool = json.loads(pool)
        except Exception:
            pool = []
    if not pool:
        pool = _LOCAL_ENCOUNTER_FALLBACK_POOL

    enemy_key = random.choice(pool)
    return {"enemy_key": enemy_key, "hex_label": target.get("label", "sub-lokacja")}


def _resolve_social_encounter(
    conn: sqlite3.Connection,
    campaign_id: int,
    target: dict,
    loc_key: Optional[str],
    encounter_result: dict,
    flags: dict,
    hint: dict,
) -> None:
    """PT-D2 #1125: split a triggered local encounter 50/50 into combat vs social.

    Combat half → leave encounter_result as-is (existing PT10 combat path).
    Social half → resolve a subtype-specific social event in-flight (d20 + stat +
    skill vs DC). Soft consequences (gold/hook); escalate to combat ONLY on Nat 1.
    Pickpocket failure deducts 10% gold (cap 50) now, but schedules a delayed 💰
    notice (1-3 turns) via session_flags.pending_gold_notices.

    Mutates encounter_result (adds 'kind'/'social') and hint in place. Never raises
    — any failure leaves the plain combat encounter untouched.
    """
    from app.services import social_encounter_service as ses

    kind = ses.classify_encounter_kind(random.random())
    encounter_result["kind"] = kind
    if kind == "combat":
        hint["kind"] = "combat"
        # #1147: carry the enemy so pop_local_travel_hint + the [COMBAT_START]
        # injection can actually spawn the fight.
        hint["enemy_key"] = encounter_result.get("enemy_key")
        return

    # Resolve sub-location subtype for the event pool
    subtype = "alley"
    if loc_key:
        _sub_row = conn.execute(
            "SELECT location_subtype FROM game_locations WHERE key = ? LIMIT 1",
            (loc_key,),
        ).fetchone()
        if _sub_row:
            subtype = ses.resolve_subtype(_sub_row["location_subtype"])

    # PT-D4d (#1133) — dobór z katalogu (game_config_encounters); pusty → hardcode.
    event = ses.pick_social_event(subtype, conn=conn)

    # Load the active character (stats + gold) for the in-flight skill check
    char = conn.execute(
        "SELECT id, sheet_json, gold_gp FROM characters "
        "WHERE campaign_id = ? AND is_active = 1 LIMIT 1",
        (campaign_id,),
    ).fetchone()
    if not char:
        # No character to resolve against — degrade to a pure soft flavor hook
        encounter_result.pop("enemy_key", None)
        encounter_result["social"] = {"event": event["key"], "subtype": subtype}
        hint.update({"kind": "social", "social_event": event["key"], "escalate": False})
        return

    from app.services.weapon_rules import stat_modifier
    sheet = json.loads(char["sheet_json"] or "{}")
    skills = sheet.get("skills") or {}
    stat_mod = stat_modifier(sheet, event["stat"])
    skill_rank = int(skills.get(event["skill"], 0) or 0)
    d20 = random.randint(1, 20)
    check = ses.resolve_skill_check(d20, stat_mod, skill_rank, event["dc"])

    outcome = ses.build_social_outcome(
        event_key=event["key"],
        subtype=subtype,
        gold=int(char["gold_gp"] or 0),
        skill_check=check,
        flags=flags,
        delay_turns=None,
        kind=event.get("kind"),  # #1133 — rekord z katalogu może mieć nowy klucz
    )

    # PT-D5 #1134 — guard_check różnicowane reputacją frakcji straży (#1103).
    # Czyta faction_tag encountera, pobiera reputację (scope_type='faction') i mapuje
    # na konsekwencję: wroga → grzywna, neutralna → standard, przyjazna → auto-pass.
    guard_meta = None
    gold_source = "pickpocket"
    if event["key"] == "guard_check":
        faction_tag = event.get("faction_tag")
        rep_value = 0
        if faction_tag:
            try:
                from app.services.reputation_service import get_reputation
                rep_value = get_reputation(
                    conn, int(char["id"]), str(faction_tag), scope_type="faction"
                )
            except Exception:
                rep_value = 0  # brak danych frakcji → neutralny fallback
        guard_meta = ses.faction_guard_outcome(
            rep_value, int(char["gold_gp"] or 0), check
        )
        outcome["gold_loss"] = int(guard_meta["gold_loss"])
        check["success"] = bool(guard_meta["success"])  # auto-pass / rewizja override
        gold_source = "guard_fine"

    # Deduct gold now (delayed reveal handled by pending_gold_notices)
    if outcome["gold_loss"] > 0:
        try:
            from app.services.economy_service import change_gold
            change_gold(
                conn,
                int(char["id"]),
                -int(outcome["gold_loss"]),
                source=gold_source,
                campaign_id=campaign_id,
                meta={"delayed": True, "subtype": subtype},
                allow_negative=False,
            )
        except Exception:
            pass  # gold mutation must never break movement

    escalate = bool(check["escalate_combat"])
    if escalate:
        # Nat 1 — social turns violent; keep combat encounter (enemy_key stays)
        encounter_result["kind"] = "combat_escalated"
    else:
        # Soft social encounter — no combat, drop the enemy
        encounter_result.pop("enemy_key", None)

    encounter_result["social"] = {
        "event": event["key"],
        "subtype": subtype,
        "success": bool(check["success"]),
        "escalate_combat": escalate,
        "gold_loss": int(outcome["gold_loss"]),
    }
    hint.update(
        {
            "kind": "combat_escalated" if escalate else "social",
            "social_event": event["key"],
            "escalate": escalate,
            "success": bool(check["success"]),
        }
    )
    if escalate:
        # #1147: Nat-1 escalation must spawn a real fight too.
        hint["enemy_key"] = encounter_result.get("enemy_key")
    # PT-D5 #1134 — dołóż postawę straży do payloadu (narracja + UI)
    if guard_meta:
        encounter_result["social"]["guard"] = {
            "attitude": guard_meta["attitude"],
            "resolution": guard_meta["resolution"],
            "auto_pass": guard_meta["auto_pass"],
        }
        hint["guard_attitude"] = guard_meta["attitude"]
        hint["guard_resolution"] = guard_meta["resolution"]


def roll_local_encounter(
    conn: sqlite3.Connection,
    campaign_id: int,
    target: dict,
    loc_key: Optional[str],
) -> Optional[dict]:
    """PT-F4 #1138: shared local-encounter roll for BOTH the /local-travel button
    and the narrative move path (`_sync_local_hex_narrative_move`).

    Rolls the risk of the target local hex (respecting encounter_cleared), and on a
    hit splits 50/50 combat vs social (`_resolve_social_encounter`). A SOFT social
    (kind == "social", not escalated) marks the hex cleared so repeated pass-throughs
    can't re-roll the pickpocket forever (combat / escalated still clear on victory).
    Persists `local_travel_hint`. Returns the encounter dict or None. Never raises.
    """
    try:
        sf_row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        flags = json.loads((sf_row["session_flags"] if sf_row else None) or "{}")
        cleared_local_hexes = flags.get("cleared_local_hexes") or []

        _steps = [
            MovementStep(key=None, cost=0.0),
            MovementStep(key=target.get("id"), cost=LOCAL_TRAVEL_MINUTES, data=target),
        ]
        _profile = MovementProfile(
            name="local",
            roll_risk=lambda s: _check_local_encounter(s.data, cleared_local_hexes),
        )
        encounter_result = run_step_sequence(_steps, _profile).encounter
        if not encounter_result:
            return None

        # Re-read flags (movement core may have written), then resolve the 50/50.
        sf_row2 = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        flags = json.loads((sf_row2["session_flags"] if sf_row2 else None) or "{}")
        hint: dict = {"destination_label": target.get("label", "sub-lokacja")}
        _resolve_social_encounter(conn, campaign_id, target, loc_key, encounter_result, flags, hint)

        # PT-F4 #1138: a soft social resolves in-flight and must NOT re-trigger on the
        # next pass — mark the hex cleared here (combat/escalated clear on victory).
        if encounter_result.get("kind") == "social":
            hex_id = target.get("id")
            cleared = flags.get("cleared_local_hexes") or []
            if hex_id is not None and hex_id not in cleared:
                cleared.append(hex_id)
                flags["cleared_local_hexes"] = cleared

        flags["local_travel_hint"] = hint
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
            (json.dumps(flags, ensure_ascii=False), campaign_id),
        )
        return encounter_result
    except Exception as _e:
        logger.warning("roll_local_encounter_failed", campaign_id=campaign_id, error=str(_e))
        return None


# ── GET /api/campaigns/{id}/local-map ─────────────────────────────────────────

@router.get("/campaigns/{campaign_id}/local-map")
def get_local_map(campaign_id: int):
    """Return local hex grid for the hub the party currently occupies.

    Response:
      {
        "hub_key": str,
        "hub_label": str,
        "hexes": [...],           # map_level=1 world_hexes rows
        "current_local_hex": {...} | null,  # party's local position
        "has_local_map": bool     # false when hub has <2 sub-locs
      }
    """
    conn = _db()
    try:
        session = _get_campaign_session(conn, campaign_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        flags = json.loads(session.get("session_flags") or "{}")

        # 1) hub z bieżącej lokacji (jeśli drużyna „w" lokacji).
        hub_key: Optional[str] = None
        current_loc_id = session.get("current_location_id")
        if current_loc_id:
            loc = _get_location(conn, current_loc_id)
            if loc:
                hub_key = _hub_key_for_location(loc)

        # 2) fallback + lazy-gen z bieżącego HEXA osady (Kamionka itp. bez lokacji /
        #    bez sub-lokacji). Idempotentne: generuje tylko gdy <2 sub-loki.
        if not hub_key or count_active_sublocs(conn, hub_key) < LOCAL_MAP_THRESHOLD:
            gen_hub = _ensure_settlement_local_map(conn, campaign_id, flags)
            if gen_hub:
                hub_key = gen_hub

        if not hub_key:
            return {"hub_key": None, "hub_label": None, "hexes": [], "current_local_hex": None, "has_local_map": False}

        # Resolve hub label
        hub_row = conn.execute(
            "SELECT label FROM game_locations WHERE key = ? AND is_active = 1", (hub_key,)
        ).fetchone()
        hub_label = hub_row["label"] if hub_row else hub_key

        # Self-heal legacy (pre-namespace) local hexes before they're ever rendered.
        normalize_hub_local_hexes(conn, hub_key)
        hexes = get_local_hexes(conn, hub_key)

        # Current local hex: read from session_flags.local_hex (flags już wczytane).
        current_local_hex = flags.get("local_hex")

        # Próg FAZA ML: mapa lokalna ma sens od ≥2 sub-lokacji. Pojedynczy samotny
        # hex renderował się jako „dziwna" pusta mapa — poniżej progu klient
        # pokazuje mapę świata (has_local_map=False). Zgodne z docstringiem.
        has_local_map = len(hexes) >= 2
        # R7 #1247 leak #2: when the hub has no local map (<2 sub-locs), never
        # echo a stale local_hex — it would leave the client thinking the party
        # is on a hex that doesn't exist. Keep the response internally consistent.
        if not has_local_map:
            current_local_hex = None
        else:
            # Pin „TU": gracz wchodzi do osady na hex wejściowy (pierwszy sub-loc).
            # Gdy local_hex nieustawiony ALBO nie pasuje do żadnego hexa (np. stare
            # współrzędne sprzed offsetu) — ustaw na hex wejściowy i zapisz.
            coords = {(int(h["q"]), int(h["r"])) for h in hexes}
            cur = current_local_hex or {}
            if (cur.get("q"), cur.get("r")) not in coords:
                entry = hexes[0]  # najstarszy sub-loc = wejście
                current_local_hex = {"q": int(entry["q"]), "r": int(entry["r"])}
                flags["local_hex"] = current_local_hex
                conn.execute(
                    "UPDATE game_sessions SET session_flags=? WHERE campaign_id=?",
                    (json.dumps(flags, ensure_ascii=False), campaign_id),
                )
                conn.commit()

        return {
            "hub_key": hub_key,
            "hub_label": hub_label,
            "hexes": hexes,
            "current_local_hex": current_local_hex,
            "has_local_map": has_local_map,
        }
    finally:
        conn.close()


# ── POST /api/campaigns/{id}/local-travel ─────────────────────────────────────

class LocalTravelRequest(BaseModel):
    hex_id: int


@router.post("/campaigns/{campaign_id}/local-travel")
def local_travel(campaign_id: int, body: LocalTravelRequest):
    """Move party to a local hex (+15 in-game minutes).

    Validates the target hex is map_level=1 and belongs to the hub the party
    is currently in.  Updates session_flags.local_hex and advances the clock.

    Response:
      {
        "moved": bool,
        "local_hex": {...},
        "location_key": str,
        "clock": {...}
      }
    """
    conn = _db()
    try:
        # Load target hex
        target_row = conn.execute(
            "SELECT * FROM world_hexes WHERE id = ? AND map_level = 1 AND is_active = 1",
            (body.hex_id,),
        ).fetchone()
        if not target_row:
            raise HTTPException(status_code=404, detail="Local hex not found")
        target = dict(target_row)

        session = _get_campaign_session(conn, campaign_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        current_loc_id = session.get("current_location_id")
        loc = _get_location(conn, current_loc_id) if current_loc_id else None
        hub_key = _hub_key_for_location(loc) if loc else None

        # AUDIT #1454: resolve the hub the party is CURRENTLY in, then ALWAYS require the
        # target to belong to it. The old `if hub_key:` guard was skipped whenever hub_key
        # was None (wilderness / non-hub sub-location) → the endpoint accepted ANY
        # map_level=1 hex in the whole world = teleport between settlements + rest-anywhere
        # (jump straight into an inn's safe_for_rest sub-hex). Fall back to the parent hub
        # of the local_hex in session_flags; if the hub still can't be resolved, reject.
        hub_hex_id = get_hub_hex_id(conn, hub_key) if hub_key else None
        if hub_hex_id is None:
            _cur_local = (json.loads(session.get("session_flags") or "{}").get("local_hex") or {})
            _cur_hex_id = _cur_local.get("hex_id")
            if _cur_hex_id:
                _cur_hex_row = conn.execute(
                    "SELECT parent_hex_id FROM world_hexes WHERE id = ? AND map_level = 1",
                    (_cur_hex_id,),
                ).fetchone()
                if _cur_hex_row and _cur_hex_row["parent_hex_id"] is not None:
                    hub_hex_id = int(_cur_hex_row["parent_hex_id"])
        if hub_hex_id is None:
            raise HTTPException(status_code=400, detail="Nie można ustalić huba lokalnego — wróć na mapę świata.")
        if target.get("parent_hex_id") != hub_hex_id:
            raise HTTPException(status_code=400, detail="Hex does not belong to current hub")

        # Resolve sub-location id if hex has a location_key
        loc_key = target.get("location_key")
        new_loc_id: int | None = None
        if loc_key:
            new_loc_row = conn.execute(
                "SELECT id FROM game_locations WHERE key = ? AND is_active = 1", (loc_key,)
            ).fetchone()
            if new_loc_row:
                new_loc_id = int(new_loc_row["id"])

        # Read current local hex id before updating — for already-here guard (#1115)
        _pre_sf = json.loads(session.get("session_flags") or "{}")
        current_hex_id = (_pre_sf.get("local_hex") or {}).get("hex_id")

        # #1112: atomic position write via canonical service
        from app.services.location_state_service import set_position
        set_position(
            conn,
            campaign_id=campaign_id,
            local_hex={
                "hex_id": target["id"],
                "q": target["q"],
                "r": target["r"],
                "location_key": loc_key,
            },
            current_location_id=new_loc_id,
        )
        # Keep local reference in sync for the return value
        _sf_row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        flags = json.loads(_sf_row["session_flags"] if _sf_row else "{}")

        # Advance clock +15 min — skip when player is already at target hex (#1115)
        clock_state: dict = {}
        encounter_result: Optional[dict] = None
        if body.hex_id != current_hex_id:
            try:
                from app.services.clock_service import advance_clock
                # AUDIT #1454 (#1390 nested-conn): pass conn=conn. set_position wrote on
                # `conn` but hasn't committed yet (commit is below); advance_clock without
                # conn= opened a SECOND connection to the same DB file → 'database is
                # locked', swallowed here → local move happened for FREE (no +15 min).
                clock_state = advance_clock(campaign_id, minutes=LOCAL_TRAVEL_MINUTES, reason="local_travel", conn=conn)
            except Exception as _clk_err:
                pass  # clock must never break movement

            # PT10 #1120 + PT11 #1121 + PT-F4 #1138: local encounter roll via the
            # shared helper (also used by the narrative move path).
            encounter_result = roll_local_encounter(conn, campaign_id, target, loc_key)

        conn.commit()

        if loc_key:
            try:
                maybe_lazy_enrich_subloc(conn, loc_key)
            except Exception:
                pass  # lazy enrichment must never break movement

        return {
            "moved": True,
            "local_hex": flags.get("local_hex"),
            "location_key": loc_key,
            "clock": clock_state,
            "encounter": encounter_result,
        }
    finally:
        conn.close()
