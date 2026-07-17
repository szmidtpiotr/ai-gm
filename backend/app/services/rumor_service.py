"""Plotki (#1191 E4) — persistent rumors feeding the Atlas.

A successful `quest_rumor` social encounter creates a rumor pointing at a
DETERMINISTIC target drawn from a closed vocabulary (unvisited plan locations,
else a region enemy type) — never a free-text LLM tag (lesson from #1294).
Discovering that target later flips status heard→confirmed.

Every entry point is DB-error tolerant and campaign-safe: a failure here must
not break a turn.
"""

from __future__ import annotations

import json
import random
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

RUMOR_DB_PATH = "/data/ai_gm.db"

# #1190 — Numbers Policy (wartości startowe, Sandbox-tunable):
#   proporcja plotek PRAWDZIWYCH do fałszywych = 60/40.
#   Tylko cele MIEJSCA (lokacja/loch/skarb) mogą być fałszywe — „obietnica pustki":
#   gracz dociera na miejsce i nic tam nie ma → status debunked. Wroga/recepturę/event
#   demaskacja przez wizytę nie ma sensu (istnieją realnie), więc te są ZAWSZE prawdziwe.
TRUE_RUMOR_WEIGHT = 0.6
_PLACE_TARGET_TYPES = frozenset({"location", "dungeon", "treasure_site"})


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(RUMOR_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pick_target(conn: sqlite3.Connection, campaign_id: int,
                 character_id: int) -> Optional[dict[str, Any]]:
    """Choose a deterministic rumor target from a closed vocabulary.

    Priority: an unvisited plan key_location the hero has no open rumor about,
    else a region enemy type not yet in the bestiary. Returns
    {target_type, target_key, label} or None (→ plain-flavour rumor).
    """
    # existing open targets for this hero (avoid duplicates)
    try:
        open_targets = {
            (r["target_type"], r["target_key"])
            for r in conn.execute(
                "SELECT target_type, target_key FROM character_rumors "
                "WHERE character_id = ? AND status = 'heard'",
                (character_id,),
            ).fetchall()
        }
    except sqlite3.OperationalError:
        open_targets = set()

    # 0 — an incomplete treasure map the hero already holds (#1196): a rumour that
    # the rest of the map surfaced nearby. Highest priority — directly actionable.
    try:
        _tr = conn.execute(
            """
            SELECT wt.id, wt.label FROM world_treasures wt
            WHERE wt.character_id = ? AND wt.state = 'buried'
              AND (SELECT COUNT(*) FROM character_map_fragments f
                   WHERE f.treasure_id = wt.id AND f.character_id = wt.character_id) < wt.total_parts
            ORDER BY wt.id LIMIT 1
            """,
            (character_id,),
        ).fetchone()
        if _tr and ("treasure_site", str(_tr["id"])) not in open_targets:
            return {"target_type": "treasure_site", "target_key": str(_tr["id"]),
                    "label": _tr["label"] or "mapa skarbu"}
    except sqlite3.OperationalError:
        pass

    # 1 — unvisited plan locations
    row = conn.execute(
        "SELECT gm_plan_json FROM campaigns WHERE id = ?", (campaign_id,)
    ).fetchone()
    plan = {}
    if row and row["gm_plan_json"]:
        try:
            plan = json.loads(row["gm_plan_json"])
        except (json.JSONDecodeError, TypeError):
            plan = {}
    candidates: list[dict[str, Any]] = []
    for loc in plan.get("key_locations") or []:
        if not isinstance(loc, dict) or loc.get("visited"):
            continue
        key = loc.get("key")
        if not key or ("location", key) in open_targets:
            continue
        candidates.append({"target_type": "location", "target_key": key,
                           "label": loc.get("name") or key})
    if candidates:
        return random.choice(candidates)

    # 1.5 — #1190: nieukończony loch (game_dungeons) — plotka jako kanał dystrybucji
    # contentu (skieruj gracza do farmowalnego lochu). „Ukończony" = wpis w
    # character_dungeon_runs po location_key. Cel MIEJSCE → może być fałszywy.
    try:
        cleared = {
            r["location_key"]
            for r in conn.execute(
                "SELECT location_key FROM character_dungeon_runs WHERE character_id = ?",
                (character_id,),
            ).fetchall()
        }
        dungeon_rows = conn.execute(
            "SELECT key, label, location_key FROM game_dungeons "
            "WHERE COALESCE(is_active,1)=1 ORDER BY key"
        ).fetchall()
        dungeon_cands = [
            {"target_type": "dungeon", "target_key": r["key"], "label": r["label"] or r["key"]}
            for r in dungeon_rows
            if r["location_key"] not in cleared
            and ("dungeon", r["key"]) not in open_targets
        ]
        if dungeon_cands:
            return random.choice(dungeon_cands)
    except sqlite3.OperationalError:
        pass

    # 1.7 — #1190: aktywne wydarzenie regionalne (#1193) — plotka o „żywym świecie".
    # Event JEST faktem → zawsze prawdziwy. Region z reputation_service.
    try:
        from app.services.reputation_service import resolve_region
        from app.services import world_event_service as _wes
        _region = resolve_region(conn, campaign_id)
        _ev = _wes.get_active_event(conn, _region)
        if _ev:
            _ekey = str(_ev.get("id") or _ev.get("template_key") or _region)
            _elabel = (_ev.get("label") or _ev.get("title")
                       or _ev.get("name") or "niepokojące wieści")
            if ("event", _ekey) not in open_targets:
                return {"target_type": "event", "target_key": _ekey, "label": _elabel}
    except (sqlite3.OperationalError, ImportError):
        pass

    # 2 — a region enemy type not yet hunted
    try:
        enemy_rows = conn.execute(
            "SELECT key, label FROM game_config_enemies "
            "WHERE COALESCE(tier,'') != 'boss' ORDER BY key"
        ).fetchall()
        known = {
            r["enemy_key"]
            for r in conn.execute(
                "SELECT enemy_key FROM character_bestiary WHERE character_id = ?",
                (character_id,),
            ).fetchall()
        }
    except sqlite3.OperationalError:
        enemy_rows, known = [], set()
    enemy_cands = [
        {"target_type": "enemy", "target_key": r["key"], "label": r["label"] or r["key"]}
        for r in enemy_rows
        if r["key"] not in known and ("enemy", r["key"]) not in open_targets
    ]
    if enemy_cands:
        return random.choice(enemy_cands)

    # 3 — #1341 BL-D2: karczemna plotka zdradzająca SKŁADNIKI ukrytej receptury,
    # której bohater jeszcze nie odkrył. Cel deterministyczny (klucz receptury z
    # DB — zamknięte słownictwo, nie free-text LLM). Składniki wypisane w plotce,
    # ale receptura odkrywa się dopiero przez udany eksperyment.
    try:
        discovered = {
            r["recipe_key"]
            for r in conn.execute(
                "SELECT recipe_key FROM character_recipes WHERE character_id = ?",
                (character_id,),
            ).fetchall()
        }
        recipe_rows = conn.execute(
            "SELECT key, label, inputs_json FROM game_config_recipes "
            "WHERE is_active = 1 AND is_hidden = 1"
        ).fetchall()
    except sqlite3.OperationalError:
        discovered, recipe_rows = set(), []
    recipe_cands = []
    for r in recipe_rows:
        if r["key"] in discovered or ("recipe", r["key"]) in open_targets:
            continue
        try:
            comp = [str(e.get("item_key")) for e in json.loads(r["inputs_json"] or "[]")
                    if isinstance(e, dict) and e.get("item_key")]
        except (json.JSONDecodeError, TypeError):
            comp = []
        label = r["label"] or r["key"]
        if comp:
            label = f"{label} (składniki: {', '.join(comp)})"
        recipe_cands.append({"target_type": "recipe", "target_key": r["key"], "label": label})
    if recipe_cands:
        return random.choice(recipe_cands)

    return None


_FLAVOUR = {
    "location": "W karczmie szepczą, że warto zajrzeć do {label} — podobno kryje niejedno.",
    "enemy": "Przy kuflu ktoś klnie na {label} — mówią, że grasują gdzieś w okolicy.",
    "treasure_site": "Ktoś przy ogniu wspomina, że resztę takiej mapy jak twoja "
                     "widziano nieopodal — może uda się dokończyć zbiór.",
    "recipe": "Stary rzemieślnik przy kuflu mamrocze o zapomnianej recepturze: {label}. "
              "Podobno trzeba zmieszać to przy tyglu we właściwych proporcjach.",
    # #1190 — nowe cele: loch (kanał dystrybucji farmy) + wydarzenie regionalne.
    "dungeon": "Zawadiaka przy kuflu zaklina się, że w {label} można nieźle zarobić — "
               "o ile wyjdzie się stamtąd żywym.",
    "event": "Ludzie w karczmie ściszają głos: {label}. Podobno to nie koniec.",
    None: "Krążą po karczmie plotki i niesprawdzone wieści — nic konkretnego.",
}

# #1190 — warianty FAŁSZYWE dla celów-miejsc: kusząca, ale pusta obietnica. Świat
# nie jest wiarygodny w 100%. Etykieta celu (realna) uwiarygadnia bujdę.
_FLAVOUR_FALSE = {
    "location": "Pewien pijak zarzeka się, że w {label} zakopano skrzynię pełną złota — "
                "„sam widziałem mapę!”. Brzmi zbyt pięknie.",
    "dungeon": "Ktoś rozpowiada, że w {label} leży smoczy skarb bez strażnika. "
               "Darmowy łup? Coś tu nie gra.",
    "treasure_site": "Obcy przysięga, że twoją mapę można dokończyć tuż za rogiem — "
                     "wystarczy postawić mu jeszcze jedną kolejkę.",
}


def _region_for(conn: sqlite3.Connection, campaign_id: int) -> Optional[str]:
    """Best-effort campaign region for rumor tagging. None on any failure."""
    try:
        from app.services.reputation_service import resolve_region
        return resolve_region(conn, campaign_id)
    except Exception:
        return None


def _insert_rumor(c: sqlite3.Connection, cid: int, camp: int,
                  source_type: str, rng=random) -> Optional[dict[str, Any]]:
    """Pick a target, decide truth (place-types 60/40, others always true), write a
    row. Returns {rumor_id, rumor_text, target_type, target_key, truth_flag} or None."""
    target = _pick_target(c, camp, cid)
    ttype = target["target_type"] if target else None
    tkey = target["target_key"] if target else None
    label = target["label"] if target else None
    # #1190 — tylko cele-miejsca bywają fałszywe; reszta zawsze prawdziwa.
    truth = True
    if ttype in _PLACE_TARGET_TYPES and rng.random() >= TRUE_RUMOR_WEIGHT:
        truth = False
    if not truth and ttype in _FLAVOUR_FALSE:
        text = _FLAVOUR_FALSE[ttype].format(label=label or "")
    else:
        text = _FLAVOUR.get(ttype, _FLAVOUR[None]).format(label=label or "")
    now = _now_iso()
    region = _region_for(c, camp)
    cur = c.execute(
        "INSERT INTO character_rumors "
        "(character_id, campaign_id, rumor_text, target_type, target_key, status, "
        " heard_at, truth_flag, source_type, region, suspected) "
        "VALUES (?, ?, ?, ?, ?, 'heard', ?, ?, ?, ?, 0)",
        (cid, camp, text, ttype, tkey, now, 1 if truth else 0, source_type, region),
    )
    return {"rumor_id": int(cur.lastrowid), "rumor_text": text,
            "target_type": ttype, "target_key": tkey, "truth_flag": 1 if truth else 0}


def create_rumor(campaign_id: Any, character_id: Any,
                 conn: sqlite3.Connection | None = None) -> Optional[dict[str, Any]]:
    """Record a rumor on a successful quest_rumor encounter (#1191 path).

    Encounter rumors are a SOFT SUCCESS hook → always a true lead (truth_flag=1);
    only deliberate tavern eavesdropping (#1190 `eavesdrop_rumor`) can be false.
    Returns the rumor dict (incl. rumor_text) or None on no-op/failure."""
    try:
        cid = int(character_id)
        camp = int(campaign_id)
    except (TypeError, ValueError):
        return None
    own = conn is None
    c = conn or _conn()
    try:
        # encounter path: force truth by using a no-false rng (>= weight never hits)
        res = _insert_rumor(c, cid, camp, source_type="encounter", rng=_ALWAYS_TRUE_RNG)
        if own:
            c.commit()
        return res
    except Exception as e:
        logger.warning("rumor_create_failed", campaign_id=campaign_id,
                       character_id=character_id, error=str(e))
        return None
    finally:
        if own:
            c.close()


class _AlwaysTrueRNG:
    """random-like shim whose .random() forces the true-rumor branch."""
    @staticmethod
    def random() -> float:
        return 0.0  # 0.0 < TRUE_RUMOR_WEIGHT → always true


_ALWAYS_TRUE_RNG = _AlwaysTrueRNG()


def eavesdrop_rumor(campaign_id: Any, character_id: Any, paid: bool = False,
                    conn: sqlite3.Connection | None = None,
                    rng=random) -> Optional[dict[str, Any]]:
    """#1190 — a deliberate tavern eavesdrop / bought round. Records a rumor that
    may be false (60/40 for place-type targets). `paid` only tags the source
    (round vs eavesdrop); the caller handles gold + the suspicion test. Returns the
    rumor dict {rumor_id, rumor_text, target_type, target_key, truth_flag} or None."""
    try:
        cid = int(character_id)
        camp = int(campaign_id)
    except (TypeError, ValueError):
        return None
    own = conn is None
    c = conn or _conn()
    try:
        res = _insert_rumor(c, cid, camp,
                            source_type="round" if paid else "eavesdrop", rng=rng)
        if own:
            c.commit()
        return res
    except Exception as e:
        logger.warning("rumor_eavesdrop_failed", campaign_id=campaign_id,
                       character_id=character_id, error=str(e))
        return None
    finally:
        if own:
            c.close()


def mark_suspected(rumor_id: Any, conn: sqlite3.Connection | None = None) -> bool:
    """Flag a rumor as suspicious (the hero's WIS/CHA sniffed out a possible lie).
    Does NOT reveal the truth to the player — just raises a red flag. No-op safe."""
    try:
        rid = int(rumor_id)
    except (TypeError, ValueError):
        return False
    own = conn is None
    c = conn or _conn()
    try:
        c.execute("UPDATE character_rumors SET suspected = 1 WHERE id = ?", (rid,))
        if own:
            c.commit()
        return True
    except sqlite3.OperationalError as e:
        logger.warning("rumor_suspect_failed", error=str(e))
        return False
    finally:
        if own:
            c.close()


def confirm_rumors_for(campaign_id: Any, target_type: str, target_key: str,
                       conn: sqlite3.Connection | None = None) -> int:
    """Resolve all open rumors in this campaign matching a discovered target.

    #1190 — a TRUE rumor flips heard→confirmed; a FALSE one flips heard→debunked
    (the promised payoff wasn't there). Returns count resolved. Campaign-scoped,
    no-op safe."""
    if not target_type or not target_key:
        return 0
    try:
        camp = int(campaign_id)
    except (TypeError, ValueError):
        return 0
    own = conn is None
    c = conn or _conn()
    try:
        cur = c.execute(
            "UPDATE character_rumors SET "
            "  status = CASE WHEN COALESCE(truth_flag, 1) = 0 THEN 'debunked' ELSE 'confirmed' END, "
            "  confirmed_at = ? "
            "WHERE campaign_id = ? AND status = 'heard' "
            "AND target_type = ? AND target_key = ?",
            (_now_iso(), camp, target_type, target_key),
        )
        if own:
            c.commit()
        return cur.rowcount or 0
    except sqlite3.OperationalError as e:
        logger.warning("rumor_confirm_failed", error=str(e))
        return 0
    finally:
        if own:
            c.close()
