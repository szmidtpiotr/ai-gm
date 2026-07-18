import copy
import json
import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException, Path
from fastapi.params import Depends
from pydantic import BaseModel

from app.core.db_runtime import resolve_db_path
from app.routers.admin import require_admin_token

router = APIRouter(tags=["admin-cheat"])
DB_PATH = resolve_db_path()


def _sqlite_table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (name,),
    ).fetchone()
    return row is not None


def _resolve_inventory_add_key(
    conn: sqlite3.Connection, raw_key: str, preferred_kind: str | None = None
) -> tuple[str, str]:
    """
    Map raw cheat key to (canonical_catalog_key, column_name).

    column_name is weapon_key or item_key (8H: consumables catalog → item_key;
    consumable_key column is legacy-only for old inventory rows).
    """
    k = str(raw_key or "").strip()
    if not k:
        raise ValueError("empty key")

    def w(canonical: str) -> tuple[str, str]:
        return canonical, "weapon_key"

    def i(canonical: str) -> tuple[str, str]:
        return canonical, "item_key"

    has_w = _sqlite_table_exists(conn, "game_config_weapons")
    has_c = _sqlite_table_exists(conn, "game_config_consumables")
    has_i = _sqlite_table_exists(conn, "game_config_items")
    pref = str(preferred_kind or "").strip().lower()

    def resolve_consumable_pref() -> tuple[str, str]:
        if has_i:
            row = conn.execute(
                "SELECT key FROM game_config_items WHERE key = ? AND item_type = 'consumable' LIMIT 1",
                (k,),
            ).fetchone()
            if row:
                return i(str(row["key"]))
            alt = k[11:] if k.startswith("consumable_") else k
            row = conn.execute(
                "SELECT key FROM game_config_items WHERE key = ? AND item_type = 'consumable' LIMIT 1",
                (alt,),
            ).fetchone()
            if row:
                return i(str(row["key"]))
        if has_c:
            row = conn.execute(
                "SELECT key FROM game_config_consumables WHERE key = ? LIMIT 1",
                (k,),
            ).fetchone()
            if row:
                return i(str(row["key"]))
            alt = k[11:] if k.startswith("consumable_") else k
            row = conn.execute(
                "SELECT key FROM game_config_consumables WHERE key = ? LIMIT 1",
                (alt,),
            ).fetchone()
            if row:
                return i(str(row["key"]))
        return i(k[11:] if k.startswith("consumable_") else k)

    if pref == "weapon":
        if has_w:
            row = conn.execute(
                "SELECT key FROM game_config_weapons WHERE key = ? LIMIT 1",
                (k,),
            ).fetchone()
            if row:
                return w(str(row["key"]))
            if k.startswith("weapon_"):
                alt = k[7:]
                row = conn.execute(
                    "SELECT key FROM game_config_weapons WHERE key = ? LIMIT 1",
                    (alt,),
                ).fetchone()
                if row:
                    return w(str(row["key"]))
        return w(k[7:] if k.startswith("weapon_") else k)

    if pref == "consumable":
        return resolve_consumable_pref()

    if has_w:
        row = conn.execute(
            "SELECT key FROM game_config_weapons WHERE key = ? LIMIT 1",
            (k,),
        ).fetchone()
        if row:
            return w(str(row["key"]))
        if k.startswith("weapon_"):
            alt = k[7:]
            row = conn.execute(
                "SELECT key FROM game_config_weapons WHERE key = ? LIMIT 1",
                (alt,),
            ).fetchone()
            if row:
                return w(str(row["key"]))

    # Legacy consumable catalog wins over mis-typed rows in game_config_items (e.g. quest stub
    # blocking INSERT OR IGNORE ... FROM game_config_consumables during 8H migration).
    if has_c:
        crow = conn.execute(
            "SELECT key FROM game_config_consumables WHERE key = ? LIMIT 1",
            (k,),
        ).fetchone()
        if crow:
            return i(str(crow["key"]))
        if k.startswith("consumable_"):
            alt_c = k[11:]
            crow = conn.execute(
                "SELECT key FROM game_config_consumables WHERE key = ? LIMIT 1",
                (alt_c,),
            ).fetchone()
            if crow:
                return i(str(crow["key"]))

    if has_i:
        row = conn.execute(
            "SELECT key, item_type FROM game_config_items WHERE key = ? LIMIT 1",
            (k,),
        ).fetchone()
        if row:
            ik = str(row["key"])
            it = str(row["item_type"] or "").strip().lower() or "misc"
            if it == "weapon" and has_w:
                wrow = conn.execute(
                    "SELECT key FROM game_config_weapons WHERE key = ? LIMIT 1",
                    (ik,),
                ).fetchone()
                if wrow:
                    return w(str(wrow["key"]))
            return i(ik)

    if has_c:
        row = conn.execute(
            "SELECT key FROM game_config_consumables WHERE key = ? LIMIT 1",
            (k,),
        ).fetchone()
        if row:
            return i(str(row["key"]))
        if k.startswith("consumable_"):
            alt = k[11:]
            row = conn.execute(
                "SELECT key FROM game_config_consumables WHERE key = ? LIMIT 1",
                (alt,),
            ).fetchone()
            if row:
                return i(str(row["key"]))

    if k.startswith("weapon_"):
        return w(k)
    if k.startswith("consumable_"):
        return i(k[11:] if len(k) > 11 else k)
    return i(k)


def _occupied_equipment_slots(conn: sqlite3.Connection, character_id: int) -> dict[str, bool]:
    o = {"main_hand": False, "off_hand": False, "armor": False}
    rows = conn.execute(
        """
        SELECT slot FROM character_inventory
        WHERE character_id = ? AND equipped = 1 AND slot IS NOT NULL AND slot != ''
        """,
        (int(character_id),),
    ).fetchall()
    for r in rows:
        s = str(r["slot"] or "").lower()
        if s in o:
            o[s] = True
    return o


def _pick_weapon_equip_slot(
    conn: sqlite3.Connection, character_id: int, weapon_catalog_key: str
) -> str:
    """Match frontend inventory.js pickEquipSlot: shields → off_hand when free, else hands."""
    occupied = _occupied_equipment_slots(conn, character_id)
    key_lower = weapon_catalog_key.lower()
    lab = ""
    row = conn.execute(
        "SELECT label FROM game_config_weapons WHERE key = ? LIMIT 1",
        (weapon_catalog_key,),
    ).fetchone()
    if row and row["label"] is not None:
        lab = str(row["label"]).lower()
    if "shield" in key_lower or "tarcz" in lab or "shield" in lab:
        if not occupied["off_hand"]:
            return "off_hand"
        if not occupied["main_hand"]:
            return "main_hand"
        return "off_hand"
    if not occupied["main_hand"]:
        return "main_hand"
    if not occupied["off_hand"]:
        return "off_hand"
    return "main_hand"


def _armor_auto_slot(
    conn: sqlite3.Connection, character_id: int, coverage: str
) -> str | None:
    """armor_coverage → anatomiczny slot manekina (zgodnie z loot_service.equip_item).

    Pary kończyn: wolna strona (najpierw lewa). 'full' → torso. Coverage bez slotu w
    manekinie (nieznane) → None (zostaw w plecaku, nie zakładaj na siłę).
    """
    cov = str(coverage or "").lower()
    if cov in ("torso", "full"):
        return "torso"
    if cov in ("head", "hands", "feet", "back"):
        return cov
    if cov in ("limb_arm", "limb_leg"):
        left, right = ("l_arm", "r_arm") if cov == "limb_arm" else ("l_leg", "r_leg")
        taken = {
            str(r["slot"])
            for r in conn.execute(
                "SELECT slot FROM character_inventory "
                "WHERE character_id = ? AND equipped = 1 AND slot IN (?, ?)",
                (int(character_id), left, right),
            ).fetchall()
        }
        return left if left not in taken else right
    return None


def _auto_equip_new_inventory_row(
    conn: sqlite3.Connection,
    character_id: int,
    inventory_id: int,
    col: str,
    canonical_key: str,
) -> str | None:
    """
    After cheat INSERT, assign equipped + slot for weapons and armor items.
    Returns slot name if equipped, else None.
    """
    cid = int(character_id)
    iid = int(inventory_id)
    slot: str | None = None
    if col == "weapon_key":
        slot = _pick_weapon_equip_slot(conn, cid, canonical_key)
    elif col == "item_key":
        row = conn.execute(
            "SELECT item_type, armor_coverage FROM game_config_items WHERE key = ? LIMIT 1",
            (canonical_key,),
        ).fetchone()
        it = str(row["item_type"] or "").lower() if row else ""
        if it == "armor":
            # Wylicz anatomiczny slot z armor_coverage (manekin gracza nie zna slotu 'armor').
            # Coverage bez slotu (feet/back/nieznane) → None: zostaw w plecaku, bez auto-zakładania.
            slot = _armor_auto_slot(
                conn, cid, str((row["armor_coverage"] if row else "") or "").lower()
            )
    else:
        return None

    if not slot:
        return None

    conn.execute(
        "UPDATE character_inventory SET equipped = 0, slot = NULL WHERE character_id = ? AND slot = ?",
        (cid, slot),
    )
    conn.execute(
        "UPDATE character_inventory SET equipped = 1, slot = ? WHERE id = ?",
        (slot, iid),
    )
    return slot


def _inventory_key_remove_variants(raw_key: str) -> list[str]:
    """Aliases so remove matches bare keys and legacy weapon_/consumable_ typos."""
    k = str(raw_key or "").strip()
    if not k:
        return []
    out: list[str] = []
    seen: set[str] = set()

    def add(x: str) -> None:
        if x and x not in seen:
            seen.add(x)
            out.append(x)

    add(k)
    if k.startswith("weapon_"):
        add(k[7:])
    else:
        add("weapon_" + k)
    if k.startswith("consumable_"):
        add(k[11:])
    else:
        add("consumable_" + k)
    return out


AVAILABLE_CMDS = [
    "add gold",
    "set gold",
    "add health",
    "set health",
    "add stat",
    "set skill",
    "set mana",
    "add mana",
    "add condition",
    "remove condition",
    "set level",
    "set location",
    "add item",
    "remove item",
    "clear inventory",
    "combat end",
    "quest add",
    "quest complete",
    "grant companion",
    "show state",
]

# HI1 (#623): nowe luki zapisu inspektora — zawsze guardowane + audytowane.
INSPECTOR_NEW_CMDS = {"set skill", "set mana", "add mana", "add condition", "remove condition"}
# Operacyjne komendy, których guard live_locked NIE blokuje (np. „combat end" MUSI działać
# w trakcie walki — to nią kończy; „show state" to odczyt).
GUARD_EXEMPT_CMDS = {"show state", "combat end"}


def character_inspector_live_lock(
    conn: sqlite3.Connection, campaign_id: int
) -> tuple[bool, str | None]:
    """HI1: czy bohater jest w „żywym" stanie blokującym edycję inspektora.

    HI4 (#627): logika przeniesiona do `inspector_guard` (jedno źródło — współdzielone
    z equip/zaklęciami). Ta funkcja deleguje, zachowując sygnaturę dla istniejących
    wywołań w tym module.
    """
    from app.services import inspector_guard

    return inspector_guard.live_lock_by_campaign(conn, campaign_id)


def _write_inspector_audit(
    conn: sqlite3.Connection,
    character_id: int,
    cmd: str,
    req: "CheatRequest",
    result: dict[str, Any],
) -> None:
    """HI1: zapisz mutację inspektora do admin_audit_log (kto/co/delta)."""
    try:
        old_values = json.dumps(
            {"key": req.key, "value": req.value, "stat": req.stat}, ensure_ascii=False
        )
        new_values = json.dumps(result, ensure_ascii=False)
        conn.execute(
            "INSERT INTO admin_audit_log (table_name, row_key, operation, old_values, new_values) "
            "VALUES (?, ?, ?, ?, ?)",
            ("characters", str(character_id), f"inspector:{cmd}", old_values, new_values),
        )
    except sqlite3.OperationalError:
        pass


def _stat_modifier(value: int) -> int:
    from app.core.mechanics import stat_modifier as _core
    return _core(value)


class CheatRequest(BaseModel):
    cmd: str
    value: int | str | None = None
    key: str | None = None
    stat: str | None = None
    kind: str | None = None
    # HI1 (#623): inspektor — guard live_locked + audyt.
    inspector: bool = False
    force: bool = False


@router.post("/admin/cheat/{character_id}")
def admin_cheat(
    character_id: int = Path(...),
    req: CheatRequest = ...,
    _: None = Depends(require_admin_token),
) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        char = conn.execute(
            "SELECT id, campaign_id, location, sheet_json, COALESCE(gold_gp, 0) AS gold_gp "
            "FROM characters WHERE id = ?",
            (character_id,),
        ).fetchone()
        if not char:
            raise HTTPException(status_code=404, detail="character_not_found")

        sheet: dict[str, Any] = json.loads(char["sheet_json"] or "{}")
        campaign_id = int(char["campaign_id"] or 0)
        result: dict[str, Any] = {}
        pending_new_act: tuple[dict[str, Any], dict[str, Any]] | None = None
        cmd = req.cmd.strip().lower()

        # HI1 (#623): wywołanie traktowane jak inspektorskie gdy klient ustawił flagę
        # `inspector` LUB użył nowej luki zapisu. Takie mutacje są guardowane (live_locked)
        # i audytowane.
        is_inspector_call = bool(req.inspector) or cmd in INSPECTOR_NEW_CMDS
        if is_inspector_call and cmd not in GUARD_EXEMPT_CMDS and not req.force:
            locked, lock_reason = character_inspector_live_lock(conn, campaign_id)
            if locked:
                raise HTTPException(
                    status_code=409,
                    detail={"reason": "live_locked", "lock_reason": lock_reason},
                )

        if cmd == "add gold":
            amount = int(req.value or 0)
            conn.execute(
                "UPDATE characters SET gold_gp = gold_gp + ? WHERE id = ?",
                (amount, character_id),
            )
            new_gold = conn.execute(
                "SELECT COALESCE(gold_gp,0) FROM characters WHERE id = ?",
                (character_id,),
            ).fetchone()[0]
            try:
                from app.services.economy_service import journal_gold_delta
                journal_gold_delta(conn, character_id, amount, "admin_cheat_add", campaign_id=campaign_id or None)
            except Exception:
                pass
            result = {"gold_gp": new_gold}

        elif cmd == "set gold":
            amount = max(0, int(req.value or 0))
            prev = conn.execute(
                "SELECT COALESCE(gold_gp,0) FROM characters WHERE id = ?", (character_id,)
            ).fetchone()[0]
            conn.execute(
                "UPDATE characters SET gold_gp = ? WHERE id = ?",
                (amount, character_id),
            )
            try:
                from app.services.economy_service import journal_gold_delta
                journal_gold_delta(
                    conn, character_id, amount - int(prev or 0),
                    "admin_cheat_set", campaign_id=campaign_id or None,
                    set_absolute=amount,
                )
            except Exception:
                pass
            result = {"gold_gp": amount}

        elif cmd in ("add health", "set health"):
            max_hp = int(sheet.get("max_hp", sheet.get("current_hp", 1)) or 1)
            cur_hp = int(sheet.get("current_hp", max_hp) or max_hp)

            if str(req.value).strip().lower() == "max":
                sheet["current_hp"] = max_hp
            elif cmd == "add health":
                sheet["current_hp"] = max(0, min(max_hp, cur_hp + int(req.value or 0)))
            else:
                sheet["current_hp"] = max(0, min(max_hp, int(req.value or 0)))

            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                (json.dumps(sheet, ensure_ascii=False), character_id),
            )
            result = {"current_hp": sheet["current_hp"], "max_hp": max_hp}

        elif cmd == "add stat":
            stat_key = (req.stat or "").upper()
            if stat_key not in ("STR", "DEX", "CON", "INT", "WIS", "CHA"):
                raise HTTPException(status_code=422, detail="invalid_stat")
            stats: dict[str, Any] = sheet.get("stats") or {}
            stats[stat_key] = int(stats.get(stat_key, 0)) + int(req.value or 0)
            sheet["stats"] = stats
            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                (json.dumps(sheet, ensure_ascii=False), character_id),
            )
            result = {"stat": stat_key, "new_value": stats[stat_key]}

        elif cmd == "set skill":
            skill_key = str(req.key or "").strip()
            if not skill_key:
                raise HTTPException(status_code=422, detail="skill_key_required")
            try:
                rank = int(req.value)
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail="invalid_rank") from None
            from app.services.xp_service import _rank_ceiling_for_skill

            ceiling = _rank_ceiling_for_skill(skill_key)
            if rank < 0 or rank > ceiling:
                raise HTTPException(
                    status_code=422,
                    detail={"error": "invalid_rank", "min": 0, "max": ceiling},
                )
            skills: dict[str, Any] = sheet.get("skills") or {}
            skills[skill_key] = rank
            sheet["skills"] = skills
            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                (json.dumps(sheet, ensure_ascii=False), character_id),
            )
            result = {"skill": skill_key, "rank": rank}

        elif cmd in ("set mana", "add mana"):
            max_mana = int(sheet.get("max_mana", sheet.get("current_mana", 0)) or 0)
            cur_mana = int(sheet.get("current_mana", max_mana) or 0)
            if str(req.value).strip().lower() == "max":
                sheet["current_mana"] = max_mana
            elif cmd == "add mana":
                sheet["current_mana"] = max(0, min(max_mana, cur_mana + int(req.value or 0)))
            else:
                sheet["current_mana"] = max(0, min(max_mana, int(req.value or 0)))
            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                (json.dumps(sheet, ensure_ascii=False), character_id),
            )
            result = {"current_mana": sheet["current_mana"], "max_mana": max_mana}

        elif cmd == "add condition":
            ckey = str(req.key or "").strip()
            if not ckey:
                raise HTTPException(status_code=422, detail="condition_key_required")
            label = ckey
            try:
                row = conn.execute(
                    "SELECT key, label FROM game_config_conditions WHERE key = ? AND is_active = 1 LIMIT 1",
                    (ckey,),
                ).fetchone()
                if row is None:
                    raise HTTPException(status_code=422, detail="invalid_condition")
                label = str(row["label"] or ckey)
            except sqlite3.OperationalError:
                # Brak katalogu kondycji — przepuść (środowiska bez seeda).
                pass
            conds_raw = sheet.get("conditions")
            conds: list[Any] = conds_raw if isinstance(conds_raw, list) else []
            already = any(
                isinstance(c, dict) and str(c.get("key") or "") == ckey for c in conds
            ) or ckey in conds
            if not already:
                conds.append({"key": ckey, "label": label, "source": "inspector"})
            sheet["conditions"] = conds
            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                (json.dumps(sheet, ensure_ascii=False), character_id),
            )
            result = {"added": ckey, "conditions": conds}

        elif cmd == "remove condition":
            ckey = str(req.key or "").strip()
            if not ckey:
                raise HTTPException(status_code=422, detail="condition_key_required")
            conds_raw = sheet.get("conditions")
            conds = conds_raw if isinstance(conds_raw, list) else []
            conds = [
                c
                for c in conds
                if not (
                    (isinstance(c, dict) and str(c.get("key") or "") == ckey)
                    or c == ckey
                )
            ]
            sheet["conditions"] = conds
            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                (json.dumps(sheet, ensure_ascii=False), character_id),
            )
            result = {"removed": ckey, "conditions": conds}

        elif cmd == "set level":
            sheet["level"] = max(1, int(req.value or 1))
            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                (json.dumps(sheet, ensure_ascii=False), character_id),
            )
            result = {"level": sheet["level"]}

        elif cmd == "recalc vitals":
            # #1024: backfill max_hp/max_mana for characters whose HP never grew on level-up.
            from app.services.vitality_service import calculate_hp, calculate_mana
            level = int(sheet.get("level") or 1)
            archetype = str(sheet.get("archetype") or "warrior").lower()
            stats = sheet.get("stats") or {}
            con = int(stats.get("CON", 10) or 10)
            int_stat = int(stats.get("INT", 10) or 10)
            old_max_hp = int(sheet.get("max_hp") or 0)
            old_max_mana = int(sheet.get("max_mana") or 0)
            new_max_hp = calculate_hp(archetype, con, level)
            new_max_mana = calculate_mana(archetype, int_stat, level)
            sheet["max_hp"] = new_max_hp
            sheet["max_mana"] = new_max_mana
            # current_hp/mana: keep proportional if not at full, or cap at new max
            cur_hp = int(sheet.get("current_hp") or 0)
            cur_mana = int(sheet.get("current_mana") or 0)
            if old_max_hp > 0 and cur_hp < old_max_hp:
                sheet["current_hp"] = min(cur_hp, new_max_hp)
            else:
                sheet["current_hp"] = new_max_hp
            if old_max_mana > 0 and cur_mana < old_max_mana:
                sheet["current_mana"] = min(cur_mana, new_max_mana)
            else:
                sheet["current_mana"] = new_max_mana
            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                (json.dumps(sheet, ensure_ascii=False), character_id),
            )
            result = {
                "max_hp": new_max_hp,
                "max_mana": new_max_mana,
                "old_max_hp": old_max_hp,
                "old_max_mana": old_max_mana,
                "archetype": archetype,
                "level": level,
                "con": con,
                "int": int_stat,
            }

        elif cmd == "set location":
            loc = str(req.key or "").strip()
            if not loc:
                raise HTTPException(status_code=422, detail="location_key_required")
            conn.execute(
                "UPDATE characters SET location = ? WHERE id = ?",
                (loc, character_id),
            )
            result = {"location": loc}

        elif cmd == "add item":
            raw = str(req.key or "").strip()
            if not raw:
                raise HTTPException(status_code=422, detail="item_key_required")
            try:
                canonical, col = _resolve_inventory_add_key(conn, raw, req.kind)
            except ValueError:
                raise HTTPException(status_code=422, detail="item_key_required") from None
            conn.execute(
                f"INSERT INTO character_inventory (character_id, {col}) VALUES (?, ?)",
                (character_id, canonical),
            )
            inv_row = conn.execute("SELECT last_insert_rowid() AS id").fetchone()
            inv_id = int(inv_row["id"]) if inv_row and inv_row["id"] is not None else 0
            equipped_slot: str | None = None
            if inv_id > 0:
                try:
                    equipped_slot = _auto_equip_new_inventory_row(
                        conn, character_id, inv_id, col, canonical
                    )
                except sqlite3.OperationalError:
                    equipped_slot = None
            result = {"added": canonical}
            if equipped_slot:
                result["equipped_slot"] = equipped_slot

        elif cmd == "remove item":
            item_key = str(req.key or "").strip()
            if not item_key:
                raise HTTPException(status_code=422, detail="item_key_required")
            variants = _inventory_key_remove_variants(item_key)
            if not variants:
                raise HTTPException(status_code=422, detail="item_key_required")
            placeholders = ",".join("?" * len(variants))
            conn.execute(
                f"""
                DELETE FROM character_inventory
                WHERE character_id = ?
                  AND (
                    item_key IN ({placeholders})
                    OR weapon_key IN ({placeholders})
                    OR consumable_key IN ({placeholders})
                  )
                """,
                (character_id, *variants, *variants, *variants),
            )
            result = {"removed": item_key}

        elif cmd == "clear inventory":
            conn.execute(
                "DELETE FROM character_inventory WHERE character_id = ?",
                (character_id,),
            )
            result = {"cleared": True}

        elif cmd == "combat end":
            conn.execute(
                "UPDATE active_combat "
                "SET status = 'ended', ended_reason = 'admin_cheat' "
                "WHERE campaign_id = ? AND status = 'active'",
                (campaign_id,),
            )
            result = {"combat_ended": True, "campaign_id": campaign_id}

        elif cmd == "quest add":
            key = str(req.key or "").strip()
            if not key:
                raise HTTPException(status_code=422, detail="quest_key_required")
            quests_active: list[str] = sheet.get("quests_active") or []
            if key not in quests_active:
                quests_active.append(key)
            sheet["quests_active"] = quests_active
            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                (json.dumps(sheet, ensure_ascii=False), character_id),
            )
            result = {"quest_added": key, "quests_active": quests_active}

        elif cmd == "quest complete":
            key = str(req.key or "").strip()
            if not key:
                raise HTTPException(status_code=422, detail="quest_key_required")
            old_sheet_snapshot = copy.deepcopy(sheet)
            active: list[str] = list(sheet.get("quests_active") or [])
            completed: list[str] = list(sheet.get("quests_completed") or [])
            if key in active:
                active.remove(key)
            if key not in completed:
                completed.append(key)
            sheet["quests_active"] = active
            sheet["quests_completed"] = completed
            conn.execute(
                "UPDATE characters SET sheet_json = ? WHERE id = ?",
                (json.dumps(sheet, ensure_ascii=False), character_id),
            )
            result = {
                "quest_completed": key,
                "quests_active": active,
                "quests_completed": completed,
            }
            pending_new_act = (old_sheet_snapshot, sheet)

        elif cmd == "show state":
            gold = int(
                conn.execute(
                    "SELECT COALESCE(gold_gp,0) FROM characters WHERE id = ?",
                    (character_id,),
                ).fetchone()[0]
                or 0
            )
            location = str(
                conn.execute(
                    "SELECT location FROM characters WHERE id = ?",
                    (character_id,),
                ).fetchone()[0]
                or ""
            )
            try:
                inv_rows = conn.execute(
                    "SELECT item_key, weapon_key, consumable_key FROM character_inventory "
                    "WHERE character_id = ? ORDER BY id ASC",
                    (character_id,),
                ).fetchall()
                inventory = [
                    str(r["item_key"] or r["weapon_key"] or r["consumable_key"])
                    for r in inv_rows
                    if (r["item_key"] or r["weapon_key"] or r["consumable_key"])
                ]
            except sqlite3.OperationalError:
                inventory = []

            result = {
                "current_hp": sheet.get("current_hp"),
                "max_hp": sheet.get("max_hp"),
                "gold_gp": gold,
                "level": sheet.get("level"),
                "location": location,
                "stats": sheet.get("stats"),
                "quests_active": sheet.get("quests_active") or [],
                "quests_completed": sheet.get("quests_completed") or [],
                "inventory": inventory,
            }

        elif cmd == "grant companion":
            # #1192 FAZA TW: przyznaj towarzysza/wierzchowca bez kosztu (własny).
            from app.services import companion_service as _cmp
            comp_key = str(req.key or req.value or "").strip()
            if not comp_key:
                raise HTTPException(status_code=422, detail={"error": "missing_companion_key"})
            try:
                granted = _cmp.grant_companion(conn, character_id, comp_key, source="admin")
                result = {"granted": granted}
            except ValueError as e:
                raise HTTPException(status_code=400, detail={"error": str(e)}) from e

        else:
            raise HTTPException(
                status_code=422,
                detail={"error": "unknown_cmd", "available": AVAILABLE_CMDS},
            )

        # HI1 (#623): audyt mutacji inspektora (pomijamy czysty odczyt „show state").
        if is_inspector_call and cmd != "show state":
            _write_inspector_audit(conn, character_id, cmd, req, result)

        conn.commit()
        if pending_new_act is not None:
            from app.services.new_act_service import maybe_trigger_new_act_after_main_quest

            old_s, new_s = pending_new_act
            extra = maybe_trigger_new_act_after_main_quest(
                campaign_id=campaign_id,
                character_id=character_id,
                old_sheet=old_s,
                new_sheet=new_s,
            )
            if extra and extra.get("ok"):
                result["new_act"] = extra
        return {"ok": True, "cmd": req.cmd, "result": result}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from None
    finally:
        conn.close()


@router.get("/admin/characters/{character_id}/full")
def admin_character_full(
    character_id: int = Path(...),
    _: None = Depends(require_admin_token),
) -> dict[str, Any]:
    """HI1 (#623): czysty agregat bohatera dla Inspektora — odpowiednik
    `sandbox.py:get_character_full`, ale w routerze admina, działa dla idle i active,
    z `is_live_locked` (guard tury/walki). REUSE `loot_service` + `spell_service`.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, name, sheet_json, COALESCE(gold_gp, 0) AS gold_gp, "
            "campaign_id, user_id, status, is_active "
            "FROM characters WHERE id = ?",
            (character_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="character_not_found")
        sheet = json.loads(row["sheet_json"] or "{}")
        campaign_id = int(row["campaign_id"] or 0)
        locked, lock_reason = character_inspector_live_lock(conn, campaign_id)
        # Skille: unia pełnego katalogu z rankami arkusza — arkusz przechowuje tylko
        # podzbiór z kreatora, a Inspektor musi móc nadać KAŻDY skill (np. arcane_ward,
        # mana_shield), więc brakujące klucze katalogu dostają rangę 0.
        skills = {k: int(v or 0) for k, v in (sheet.get("skills") or {}).items()}
        for cat_row in conn.execute("SELECT key FROM game_config_skills"):
            skills.setdefault(cat_row["key"], 0)
    finally:
        conn.close()

    # Inventory + spells: wywołaj usługi bezpośrednio (jak sandbox), tolerując brak danych.
    try:
        from app.services import loot_service

        inventory = loot_service.get_character_inventory(character_id)
    except Exception:
        inventory = {}
    try:
        from app.services.spell_service import get_character_spells

        spells = get_character_spells(character_id)
    except Exception:
        spells = []

    stats = sheet.get("stats") or {}
    stat_modifiers = {k: _stat_modifier(v) for k, v in stats.items() if isinstance(v, (int, float))}

    return {
        "id": row["id"],
        "name": row["name"],
        "gold_gp": row["gold_gp"] or 0,
        "archetype": sheet.get("archetype"),
        "level": int(sheet.get("level") or 1),
        "status": row["status"],
        "campaign_id": campaign_id or None,
        "owner_id": row["user_id"],
        "stats": stats,
        "stat_modifiers": stat_modifiers,
        "skills": skills,
        "hp": int(sheet.get("current_hp") or 0),
        "max_hp": int(sheet.get("max_hp") or 0),
        "mana": int(sheet.get("current_mana") or 0),
        "max_mana": int(sheet.get("max_mana") or 0),
        "conditions": sheet.get("conditions") or [],
        "inventory": inventory,
        "spells": spells,
        "xp": int(sheet.get("xp") or sheet.get("xp_lifetime_earned") or 0),
        "quests_active": sheet.get("quests_active") or [],
        "quests_completed": sheet.get("quests_completed") or [],
        "is_live_locked": locked,
        "live_lock_reason": lock_reason,
    }
