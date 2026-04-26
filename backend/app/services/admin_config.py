import json
import re
import sqlite3


DB_PATH = "/data/ai_gm.db"
KEY_RE = re.compile(r"^[a-z0-9_]{1,40}$")
DAMAGE_DIE_RE = re.compile(r"^\d*d\d+$")
ALLOWED_CLASSES = {"warrior", "ranger", "scholar"}
ALLOWED_ITEM_TYPES = {"weapon", "armor", "consumable", "misc", "quest"}
ALLOWED_WEAPON_TYPES = {"melee", "ranged", "spell"}
ALLOWED_DAMAGE_TYPES = {"physical", "magic", "fire", "poison", "misc"}
ALLOWED_TIERS = {"weak", "standard", "elite", "boss"}
ALLOWED_EFFECT_TYPES = {"heal_hp", "restore_mana", "remove_condition", "add_condition", "stat_buff", "misc"}
ALLOWED_EFFECT_TARGETS = {"self", "ally", "any"}


def _fetch_all(query: str) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(query).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _fetch_one(conn: sqlite3.Connection, query: str, params: tuple) -> dict | None:
    row = conn.execute(query, params).fetchone()
    return dict(row) if row else None


def _audit(
    conn: sqlite3.Connection,
    table_name: str,
    row_key: str,
    operation: str,
    old_values: dict | None,
    new_values: dict | None,
) -> None:
    conn.execute(
        """
        INSERT INTO admin_audit_log (table_name, row_key, operation, old_values, new_values)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            table_name,
            row_key,
            operation,
            json.dumps(old_values, ensure_ascii=False) if old_values is not None else None,
            json.dumps(new_values, ensure_ascii=False) if new_values is not None else None,
        ),
    )


def _validate_key(key: str) -> str:
    k = (key or "").strip()
    if not KEY_RE.fullmatch(k):
        raise ValueError("invalid_key")
    return k


def _validate_damage_die(damage_die: str) -> str:
    d = (damage_die or "").strip().lower()
    if not DAMAGE_DIE_RE.fullmatch(d):
        raise ValueError("invalid_damage_die")
    return d


def _validate_allowed_classes(values: list[str]) -> str:
    if not isinstance(values, list) or not values:
        raise ValueError("invalid_allowed_classes")
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        item = str(raw).strip().lower()
        if item not in ALLOWED_CLASSES:
            raise ValueError("invalid_allowed_classes")
        if item not in seen:
            normalized.append(item)
            seen.add(item)
    return json.dumps(normalized, ensure_ascii=False)


def _normalize_effect_json(effect_json: str) -> str:
    try:
        parsed = json.loads(effect_json)
    except Exception as exc:
        raise ValueError("invalid_effect_json") from exc
    return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))


def _validate_item_type(item_type: str) -> str:
    t = (item_type or "").strip().lower()
    if t not in ALLOWED_ITEM_TYPES:
        raise ValueError("invalid_item_type")
    return t


def _validate_weapon_type(v: str) -> str:
    t = (v or "").strip().lower()
    if t not in ALLOWED_WEAPON_TYPES:
        raise ValueError("invalid_weapon_type")
    return t


def _validate_damage_type(v: str) -> str:
    t = (v or "").strip().lower()
    if t not in ALLOWED_DAMAGE_TYPES:
        raise ValueError("invalid_damage_type")
    return t


def _validate_tier(v: str) -> str:
    t = (v or "").strip().lower()
    if t not in ALLOWED_TIERS:
        raise ValueError("invalid_tier")
    return t


def _validate_drop_chance(v: float | None, *, current: float | None = None) -> float:
    if v is None:
        return float(current if current is not None else 1.0)
    x = float(v)
    if x < 0.0 or x > 1.0 or x != x:  # NaN
        raise ValueError("invalid_drop_chance")
    return x


def _validate_effect_type(v: str) -> str:
    t = (v or "").strip().lower()
    if t not in ALLOWED_EFFECT_TYPES:
        raise ValueError("invalid_effect_type")
    return t


def _validate_effect_target(v: str) -> str:
    t = (v or "").strip().lower()
    if t not in ALLOWED_EFFECT_TARGETS:
        raise ValueError("invalid_effect_target")
    return t


def _validate_proficiency_classes(values: list[str] | None) -> str:
    if values is None:
        raise ValueError("invalid_proficiency_classes")
    if len(values) == 0:
        return "[]"
    return _validate_allowed_classes(values)


def _validate_conditions_immune(values: list[str] | None) -> str:
    if values is None:
        return "[]"
    if not isinstance(values, list):
        raise ValueError("invalid_conditions_immune")
    out: list[str] = []
    for raw in values:
        k = str(raw).strip().lower()
        if not KEY_RE.fullmatch(k):
            raise ValueError("invalid_conditions_immune")
        out.append(k)
    return json.dumps(out, ensure_ascii=False)


def _validate_effect_dice(effect_dice: str | None) -> str | None:
    if effect_dice is None or not str(effect_dice).strip():
        return None
    return _validate_damage_die(str(effect_dice))


def list_stats() -> list[dict]:
    return _fetch_all(
        """
        SELECT key, label, description, sort_order, locked_at
        FROM game_config_stats
        ORDER BY sort_order ASC, key ASC
        """
    )


def list_skills() -> list[dict]:
    return _fetch_all(
        """
        SELECT key, label, linked_stat, rank_ceiling, sort_order, locked_at, description
        FROM game_config_skills
        ORDER BY sort_order ASC, key ASC
        """
    )


def list_dc() -> list[dict]:
    return _fetch_all(
        """
        SELECT key, label, value, sort_order, locked_at, description
        FROM game_config_dc
        ORDER BY sort_order ASC, key ASC
        """
    )


def list_weapons() -> list[dict]:
    rows = _fetch_all(
        """
        SELECT key, label, damage_die, weapon_type, linked_stat, allowed_classes,
               two_handed, finesse, range_m, weight_kg, description, note,
               is_active, locked_at, created_at, updated_at
        FROM game_config_weapons
        ORDER BY key ASC
        """
    )
    for row in rows:
        try:
            row["allowed_classes"] = json.loads(row.get("allowed_classes") or "[]")
        except Exception:
            row["allowed_classes"] = []
        row["two_handed"] = bool(row.get("two_handed"))
        row["finesse"] = bool(row.get("finesse"))
    return rows


def list_enemies() -> list[dict]:
    rows = _fetch_all(
        """
        SELECT key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die,
               tier, attacks_per_turn, damage_bonus, damage_type,
               xp_award, conditions_immune, loot_table_key, drop_chance, note,
               description, is_active, locked_at, created_at, updated_at
        FROM game_config_enemies
        ORDER BY key ASC
        """
    )
    for row in rows:
        try:
            row["conditions_immune"] = json.loads(row.get("conditions_immune") or "[]")
        except Exception:
            row["conditions_immune"] = []
        if row.get("drop_chance") is None:
            row["drop_chance"] = 1.0
        else:
            row["drop_chance"] = float(row["drop_chance"])
    return rows


def list_conditions() -> list[dict]:
    rows = _fetch_all(
        """
        SELECT key, label, effect_json, description, is_active, stackable, auto_remove,
               locked_at, created_at, updated_at
        FROM game_config_conditions
        ORDER BY key ASC
        """
    )
    for row in rows:
        row["stackable"] = bool(row.get("stackable"))
    return rows


def update_stat(
    key: str,
    *,
    label: str | None,
    description: str | None,
    sort_order: int | None,
    force: bool,
) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            "SELECT key, label, description, sort_order, locked_at FROM game_config_stats WHERE key = ?",
            (key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")

        updates = {
            "label": label if label is not None else current["label"],
            "description": description if description is not None else current["description"],
            "sort_order": sort_order if sort_order is not None else current["sort_order"],
        }
        conn.execute(
            """
            UPDATE game_config_stats
            SET label = ?, description = ?, sort_order = ?
            WHERE key = ?
            """,
            (updates["label"], updates["description"], updates["sort_order"], key),
        )
        new_row = _fetch_one(
            conn,
            "SELECT key, label, description, sort_order, locked_at FROM game_config_stats WHERE key = ?",
            (key,),
        )
        _audit(conn, "game_config_stats", key, "UPDATE", current, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def update_skill(
    key: str,
    *,
    label: str | None,
    linked_stat: str | None,
    rank_ceiling: int | None,
    sort_order: int | None,
    description: str | None,
    force: bool,
) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, linked_stat, rank_ceiling, sort_order, locked_at, description
            FROM game_config_skills WHERE key = ?
            """,
            (key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")

        final_linked_stat = linked_stat if linked_stat is not None else current["linked_stat"]
        stat_exists = _fetch_one(conn, "SELECT key FROM game_config_stats WHERE key = ?", (final_linked_stat,))
        if not stat_exists:
            raise ValueError("invalid_linked_stat")

        final_rank = rank_ceiling if rank_ceiling is not None else current["rank_ceiling"]
        if final_rank < 1:
            raise ValueError("invalid_rank_ceiling")

        updates = {
            "label": label if label is not None else current["label"],
            "linked_stat": final_linked_stat,
            "rank_ceiling": final_rank,
            "sort_order": sort_order if sort_order is not None else current["sort_order"],
            "description": description if description is not None else current.get("description"),
        }
        conn.execute(
            """
            UPDATE game_config_skills
            SET label = ?, linked_stat = ?, rank_ceiling = ?, sort_order = ?, description = ?
            WHERE key = ?
            """,
            (
                updates["label"],
                updates["linked_stat"],
                updates["rank_ceiling"],
                updates["sort_order"],
                updates["description"],
                key,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, linked_stat, rank_ceiling, sort_order, locked_at, description
            FROM game_config_skills WHERE key = ?
            """,
            (key,),
        )
        _audit(conn, "game_config_skills", key, "UPDATE", current, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def update_dc(
    key: str,
    *,
    label: str | None,
    value: int | None,
    sort_order: int | None,
    description: str | None,
    force: bool,
) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            "SELECT key, label, value, sort_order, locked_at, description FROM game_config_dc WHERE key = ?",
            (key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")

        updates = {
            "label": label if label is not None else current["label"],
            "value": value if value is not None else current["value"],
            "sort_order": sort_order if sort_order is not None else current["sort_order"],
            "description": description if description is not None else current.get("description"),
        }
        if updates["value"] < 1:
            raise ValueError("invalid_dc_value")

        conn.execute(
            """
            UPDATE game_config_dc
            SET label = ?, value = ?, sort_order = ?, description = ?
            WHERE key = ?
            """,
            (updates["label"], updates["value"], updates["sort_order"], updates["description"], key),
        )
        new_row = _fetch_one(
            conn,
            "SELECT key, label, value, sort_order, locked_at, description FROM game_config_dc WHERE key = ?",
            (key,),
        )
        _audit(conn, "game_config_dc", key, "UPDATE", current, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def create_skill(
    *,
    key: str,
    label: str,
    linked_stat: str,
    rank_ceiling: int = 5,
    sort_order: int | None = None,
    description: str | None = None,
) -> dict:
    if rank_ceiling < 1:
        raise ValueError("invalid_rank_ceiling")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        existing = _fetch_one(conn, "SELECT key FROM game_config_skills WHERE key = ?", (key,))
        if existing:
            raise ValueError("skill_exists")

        stat_exists = _fetch_one(conn, "SELECT key FROM game_config_stats WHERE key = ?", (linked_stat,))
        if not stat_exists:
            raise ValueError("invalid_linked_stat")

        if sort_order is None:
            mx = conn.execute("SELECT COALESCE(MAX(sort_order), -1) AS m FROM game_config_skills").fetchone()
            so = int(mx["m"]) + 1
        else:
            so = int(sort_order)

        conn.execute(
            """
            INSERT INTO game_config_skills (key, label, linked_stat, rank_ceiling, sort_order, locked_at, description)
            VALUES (?, ?, ?, ?, ?, NULL, ?)
            """,
            (key, label, linked_stat, rank_ceiling, so, description or ""),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, linked_stat, rank_ceiling, sort_order, locked_at, description
            FROM game_config_skills WHERE key = ?
            """,
            (key,),
        )
        _audit(conn, "game_config_skills", key, "INSERT", None, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def _character_uses_skill(conn: sqlite3.Connection, skill_key: str) -> tuple[int, int | None]:
    rows = conn.execute("SELECT id, sheet_json FROM characters").fetchall()
    for row in rows:
        sheet_raw = row["sheet_json"] or "{}"
        try:
            parsed = json.loads(sheet_raw)
        except Exception:
            parsed = {}
        skills = parsed.get("skills") if isinstance(parsed, dict) else None
        if isinstance(skills, dict) and skill_key in skills:
            return row["id"], int(skills.get(skill_key) or 0)
    return 0, None


def delete_skill(key: str, *, force: bool) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, linked_stat, rank_ceiling, sort_order, locked_at
            FROM game_config_skills WHERE key = ?
            """,
            (key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")

        character_id, rank = _character_uses_skill(conn, key)
        if character_id:
            raise LookupError(f"skill_in_use:{character_id}:{rank}")

        conn.execute("DELETE FROM game_config_skills WHERE key = ?", (key,))
        _audit(conn, "game_config_skills", key, "DELETE", current, None)
        conn.commit()
    finally:
        conn.close()


def create_weapon(
    *,
    key: str,
    label: str,
    damage_die: str,
    linked_stat: str,
    allowed_classes: list[str],
    is_active: bool = True,
    description: str = "",
    weapon_type: str = "melee",
    two_handed: bool = False,
    finesse: bool = False,
    range_m: int | None = None,
    weight_kg: float = 0.0,
    note: str | None = None,
) -> dict:
    safe_key = _validate_key(key)
    safe_damage_die = _validate_damage_die(damage_die)
    safe_allowed_classes = _validate_allowed_classes(allowed_classes)
    safe_weapon_type = _validate_weapon_type(weapon_type)
    if weight_kg < 0:
        raise ValueError("invalid_weight_kg")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        existing = _fetch_one(conn, "SELECT key FROM game_config_weapons WHERE key = ?", (safe_key,))
        if existing:
            raise ValueError("weapon_exists")
        stat_exists = _fetch_one(conn, "SELECT key FROM game_config_stats WHERE key = ?", (linked_stat,))
        if not stat_exists:
            raise ValueError("invalid_linked_stat")

        conn.execute(
            """
            INSERT INTO game_config_weapons (
                key, label, damage_die, weapon_type, linked_stat, allowed_classes,
                two_handed, finesse, range_m, weight_kg, description, note,
                is_active, locked_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, datetime('now'), datetime('now'))
            """,
            (
                safe_key,
                label,
                safe_damage_die,
                safe_weapon_type,
                linked_stat,
                safe_allowed_classes,
                1 if two_handed else 0,
                1 if finesse else 0,
                range_m,
                float(weight_kg),
                description or "",
                note,
                1 if is_active else 0,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, damage_die, weapon_type, linked_stat, allowed_classes,
                   two_handed, finesse, range_m, weight_kg, description, note,
                   is_active, locked_at, created_at, updated_at
            FROM game_config_weapons WHERE key = ?
            """,
            (safe_key,),
        )
        if new_row:
            new_row["allowed_classes"] = json.loads(new_row.get("allowed_classes") or "[]")
            new_row["two_handed"] = bool(new_row.get("two_handed"))
            new_row["finesse"] = bool(new_row.get("finesse"))
        _audit(conn, "game_config_weapons", safe_key, "CREATE", None, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def update_weapon(
    key: str,
    *,
    label: str | None,
    damage_die: str | None,
    linked_stat: str | None,
    allowed_classes: list[str] | None,
    is_active: bool | None,
    force: bool,
    description: str | None = None,
    weapon_type: str | None = None,
    two_handed: bool | None = None,
    finesse: bool | None = None,
    range_m: int | None = None,
    weight_kg: float | None = None,
    note: str | None = None,
) -> dict:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, damage_die, weapon_type, linked_stat, allowed_classes,
                   two_handed, finesse, range_m, weight_kg, description, note,
                   is_active, locked_at, created_at, updated_at
            FROM game_config_weapons WHERE key = ?
            """,
            (safe_key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")

        final_damage_die = _validate_damage_die(damage_die) if damage_die is not None else current["damage_die"]
        final_linked_stat = linked_stat if linked_stat is not None else current["linked_stat"]
        stat_exists = _fetch_one(conn, "SELECT key FROM game_config_stats WHERE key = ?", (final_linked_stat,))
        if not stat_exists:
            raise ValueError("invalid_linked_stat")
        final_allowed_classes = (
            _validate_allowed_classes(allowed_classes)
            if allowed_classes is not None
            else current.get("allowed_classes") or "[]"
        )
        final_is_active = (1 if is_active else 0) if is_active is not None else current.get("is_active", 1)
        final_weapon_type = (
            _validate_weapon_type(weapon_type) if weapon_type is not None else current.get("weapon_type") or "melee"
        )
        final_desc = description if description is not None else (current.get("description") or "")
        final_two = (1 if two_handed else 0) if two_handed is not None else int(current.get("two_handed", 0))
        final_finesse = (1 if finesse else 0) if finesse is not None else int(current.get("finesse", 0))
        if range_m is not None:
            final_range_m = int(range_m)
        else:
            final_range_m = current.get("range_m")
        final_weight_kg = (
            float(weight_kg) if weight_kg is not None else float(current.get("weight_kg") or 0.0)
        )
        if final_weight_kg < 0:
            raise ValueError("invalid_weight_kg")
        final_note = note if note is not None else current.get("note")

        conn.execute(
            """
            UPDATE game_config_weapons
            SET label = ?, damage_die = ?, weapon_type = ?, linked_stat = ?, allowed_classes = ?,
                two_handed = ?, finesse = ?, range_m = ?, weight_kg = ?, description = ?, note = ?,
                is_active = ?, updated_at = datetime('now')
            WHERE key = ?
            """,
            (
                label if label is not None else current["label"],
                final_damage_die,
                final_weapon_type,
                final_linked_stat,
                final_allowed_classes,
                final_two,
                final_finesse,
                final_range_m,
                final_weight_kg,
                final_desc,
                final_note,
                final_is_active,
                safe_key,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, damage_die, weapon_type, linked_stat, allowed_classes,
                   two_handed, finesse, range_m, weight_kg, description, note,
                   is_active, locked_at, created_at, updated_at
            FROM game_config_weapons WHERE key = ?
            """,
            (safe_key,),
        )
        old_for_audit = dict(current)
        old_for_audit["allowed_classes"] = json.loads(old_for_audit.get("allowed_classes") or "[]")
        old_for_audit["two_handed"] = bool(old_for_audit.get("two_handed"))
        old_for_audit["finesse"] = bool(old_for_audit.get("finesse"))
        if new_row:
            new_row["allowed_classes"] = json.loads(new_row.get("allowed_classes") or "[]")
            new_row["two_handed"] = bool(new_row.get("two_handed"))
            new_row["finesse"] = bool(new_row.get("finesse"))
        _audit(conn, "game_config_weapons", safe_key, "UPDATE", old_for_audit, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def _character_uses_weapon(conn: sqlite3.Connection, weapon_key: str) -> int:
    rows = conn.execute("SELECT id, sheet_json FROM characters").fetchall()
    for row in rows:
        sheet_raw = row["sheet_json"] or "{}"
        try:
            parsed = json.loads(sheet_raw)
        except Exception:
            parsed = {}
        if not isinstance(parsed, dict):
            continue
        if parsed.get("weapon") == weapon_key or parsed.get("equipped_weapon") == weapon_key:
            return int(row["id"])
        weapons = parsed.get("weapons")
        if isinstance(weapons, list) and weapon_key in weapons:
            return int(row["id"])
        if isinstance(weapons, dict) and weapon_key in weapons:
            return int(row["id"])
    return 0


def delete_weapon(key: str, *, force: bool) -> None:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, damage_die, linked_stat, allowed_classes, is_active, locked_at, created_at, updated_at
            FROM game_config_weapons WHERE key = ?
            """,
            (safe_key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")
        character_id = _character_uses_weapon(conn, safe_key)
        if character_id:
            raise LookupError(f"weapon_in_use:{character_id}")

        loot_ref = conn.execute(
            """
            SELECT COUNT(*) AS c FROM game_config_loot_entries
            WHERE weapon_key IS NOT NULL AND weapon_key = ?
            """,
            (safe_key,),
        ).fetchone()
        if loot_ref and int(loot_ref["c"]) > 0:
            raise ValueError("in_use")

        conn.execute("DELETE FROM game_config_weapons WHERE key = ?", (safe_key,))
        current["allowed_classes"] = json.loads(current.get("allowed_classes") or "[]")
        _audit(conn, "game_config_weapons", safe_key, "DELETE", current, None)
        conn.commit()
    finally:
        conn.close()


def create_enemy(
    *,
    key: str,
    label: str,
    hp_base: int,
    ac_base: int,
    attack_bonus: int,
    damage_die: str,
    description: str | None = None,
    is_active: bool = True,
    tier: str = "standard",
    attacks_per_turn: int = 1,
    damage_bonus: int = 0,
    damage_type: str = "physical",
    xp_award: int = 0,
    conditions_immune: list[str] | None = None,
    loot_table_key: str | None = None,
    drop_chance: float = 1.0,
    note: str | None = None,
    dex_modifier: int = 0,
) -> dict:
    safe_key = _validate_key(key)
    safe_drop = _validate_drop_chance(drop_chance)
    safe_damage_die = _validate_damage_die(damage_die)
    if hp_base < 1:
        raise ValueError("invalid_hp_base")
    if ac_base < 1:
        raise ValueError("invalid_ac_base")
    if attack_bonus < 0:
        raise ValueError("invalid_attack_bonus")
    if attacks_per_turn < 1:
        raise ValueError("invalid_attacks_per_turn")
    if xp_award < 0:
        raise ValueError("invalid_xp_award")
    safe_tier = _validate_tier(tier)
    safe_damage_type = _validate_damage_type(damage_type)
    ci_json = _validate_conditions_immune(conditions_immune if conditions_immune is not None else [])

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        existing = _fetch_one(conn, "SELECT key FROM game_config_enemies WHERE key = ?", (safe_key,))
        if existing:
            raise ValueError("enemy_exists")
        if loot_table_key:
            lk = _validate_key(loot_table_key)
            lt = _fetch_one(conn, "SELECT key FROM game_config_loot_tables WHERE key = ?", (lk,))
            if not lt:
                raise ValueError("invalid_loot_table_key")
            loot_table_key = lk
        conn.execute(
            """
            INSERT INTO game_config_enemies (
                key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die,
                tier, attacks_per_turn, damage_bonus, damage_type,
                xp_award, conditions_immune, loot_table_key, drop_chance, note,
                description, is_active, locked_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, datetime('now'), datetime('now'))
            """,
            (
                safe_key,
                label,
                hp_base,
                ac_base,
                attack_bonus,
                int(dex_modifier or 0),
                safe_damage_die,
                safe_tier,
                attacks_per_turn,
                damage_bonus,
                safe_damage_type,
                xp_award,
                ci_json,
                loot_table_key,
                safe_drop,
                note,
                description,
                1 if is_active else 0,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die,
                   tier, attacks_per_turn, damage_bonus, damage_type,
                   xp_award, conditions_immune, loot_table_key, drop_chance, note,
                   description, is_active, locked_at, created_at, updated_at
            FROM game_config_enemies WHERE key = ?
            """,
            (safe_key,),
        )
        if new_row:
            try:
                new_row["conditions_immune"] = json.loads(new_row.get("conditions_immune") or "[]")
            except Exception:
                new_row["conditions_immune"] = []
            if new_row.get("drop_chance") is not None:
                new_row["drop_chance"] = float(new_row["drop_chance"])
        _audit(conn, "game_config_enemies", safe_key, "CREATE", None, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def update_enemy(
    key: str,
    *,
    label: str | None,
    hp_base: int | None,
    ac_base: int | None,
    attack_bonus: int | None,
    damage_die: str | None,
    description: str | None,
    is_active: bool | None,
    force: bool,
    tier: str | None = None,
    attacks_per_turn: int | None = None,
    damage_bonus: int | None = None,
    damage_type: str | None = None,
    xp_award: int | None = None,
    conditions_immune: list[str] | None = None,
    loot_table_key: str | None = None,
    note: str | None = None,
    drop_chance: float | None = None,
    dex_modifier: int | None = None,
) -> dict:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die,
                   tier, attacks_per_turn, damage_bonus, damage_type,
                   xp_award, conditions_immune, loot_table_key, drop_chance, note,
                   description, is_active, locked_at, created_at, updated_at
            FROM game_config_enemies WHERE key = ?
            """,
            (safe_key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")

        final_hp_base = hp_base if hp_base is not None else current["hp_base"]
        final_ac_base = ac_base if ac_base is not None else current["ac_base"]
        final_attack_bonus = attack_bonus if attack_bonus is not None else current["attack_bonus"]
        final_dex_modifier = dex_modifier if dex_modifier is not None else int(current.get("dex_modifier") or 0)
        final_damage_die = _validate_damage_die(damage_die) if damage_die is not None else current["damage_die"]
        if final_hp_base < 1:
            raise ValueError("invalid_hp_base")
        if final_ac_base < 1:
            raise ValueError("invalid_ac_base")
        if final_attack_bonus < 0:
            raise ValueError("invalid_attack_bonus")

        final_tier = _validate_tier(tier) if tier is not None else (current.get("tier") or "standard")
        final_attacks = attacks_per_turn if attacks_per_turn is not None else int(current.get("attacks_per_turn") or 1)
        final_dmg_bonus = damage_bonus if damage_bonus is not None else int(current.get("damage_bonus") or 0)
        final_dmg_type = (
            _validate_damage_type(damage_type) if damage_type is not None else (current.get("damage_type") or "physical")
        )
        final_xp = xp_award if xp_award is not None else int(current.get("xp_award") or 0)
        if final_attacks < 1:
            raise ValueError("invalid_attacks_per_turn")
        if final_xp < 0:
            raise ValueError("invalid_xp_award")
        final_ci = (
            _validate_conditions_immune(conditions_immune)
            if conditions_immune is not None
            else (current.get("conditions_immune") or "[]")
        )
        final_loot = current.get("loot_table_key")
        if loot_table_key is not None:
            if loot_table_key == "":
                final_loot = None
            else:
                lk = _validate_key(loot_table_key)
                lt = _fetch_one(conn, "SELECT key FROM game_config_loot_tables WHERE key = ?", (lk,))
                if not lt:
                    raise ValueError("invalid_loot_table_key")
                final_loot = lk
        final_note = note if note is not None else current.get("note")
        cur_drop = float(current.get("drop_chance") if current.get("drop_chance") is not None else 1.0)
        final_drop = _validate_drop_chance(drop_chance, current=cur_drop)

        conn.execute(
            """
            UPDATE game_config_enemies
            SET label = ?, hp_base = ?, ac_base = ?, attack_bonus = ?, dex_modifier = ?, damage_die = ?,
                tier = ?, attacks_per_turn = ?, damage_bonus = ?, damage_type = ?,
                xp_award = ?, conditions_immune = ?, loot_table_key = ?, drop_chance = ?, note = ?,
                description = ?, is_active = ?, updated_at = datetime('now')
            WHERE key = ?
            """,
            (
                label if label is not None else current["label"],
                final_hp_base,
                final_ac_base,
                final_attack_bonus,
                final_dex_modifier,
                final_damage_die,
                final_tier,
                final_attacks,
                final_dmg_bonus,
                final_dmg_type,
                final_xp,
                final_ci,
                final_loot,
                final_drop,
                final_note,
                description if description is not None else current.get("description"),
                (1 if is_active else 0) if is_active is not None else current.get("is_active", 1),
                safe_key,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, hp_base, ac_base, attack_bonus, dex_modifier, damage_die,
                   tier, attacks_per_turn, damage_bonus, damage_type,
                   xp_award, conditions_immune, loot_table_key, drop_chance, note,
                   description, is_active, locked_at, created_at, updated_at
            FROM game_config_enemies WHERE key = ?
            """,
            (safe_key,),
        )
        if new_row:
            try:
                new_row["conditions_immune"] = json.loads(new_row.get("conditions_immune") or "[]")
            except Exception:
                new_row["conditions_immune"] = []
            if new_row.get("drop_chance") is not None:
                new_row["drop_chance"] = float(new_row["drop_chance"])
        cur_audit = dict(current)
        try:
            cur_audit["conditions_immune"] = json.loads(cur_audit.get("conditions_immune") or "[]")
        except Exception:
            cur_audit["conditions_immune"] = []
        _audit(conn, "game_config_enemies", safe_key, "UPDATE", cur_audit, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def delete_enemy(key: str, *, force: bool) -> None:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, hp_base, ac_base, attack_bonus, damage_die, description, is_active, locked_at, created_at, updated_at
            FROM game_config_enemies WHERE key = ?
            """,
            (safe_key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")
        conn.execute("DELETE FROM game_config_enemies WHERE key = ?", (safe_key,))
        _audit(conn, "game_config_enemies", safe_key, "DELETE", current, None)
        conn.commit()
    finally:
        conn.close()


def create_condition(
    *,
    key: str,
    label: str,
    effect_json: str,
    description: str | None = None,
    is_active: bool = True,
    stackable: bool = False,
    auto_remove: str | None = None,
) -> dict:
    safe_key = _validate_key(key)
    safe_effect_json = _normalize_effect_json(effect_json)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        existing = _fetch_one(conn, "SELECT key FROM game_config_conditions WHERE key = ?", (safe_key,))
        if existing:
            raise ValueError("condition_exists")
        conn.execute(
            """
            INSERT INTO game_config_conditions (
                key, label, effect_json, description, is_active, stackable, auto_remove,
                locked_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, datetime('now'), datetime('now'))
            """,
            (safe_key, label, safe_effect_json, description, 1 if is_active else 0, 1 if stackable else 0, auto_remove),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, effect_json, description, is_active, stackable, auto_remove,
                   locked_at, created_at, updated_at
            FROM game_config_conditions WHERE key = ?
            """,
            (safe_key,),
        )
        if new_row:
            new_row["stackable"] = bool(new_row.get("stackable"))
        _audit(conn, "game_config_conditions", safe_key, "CREATE", None, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def update_condition(
    key: str,
    *,
    label: str | None,
    effect_json: str | None,
    description: str | None,
    is_active: bool | None,
    force: bool,
    stackable: bool | None = None,
    auto_remove: str | None = None,
) -> dict:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, effect_json, description, is_active, stackable, auto_remove,
                   locked_at, created_at, updated_at
            FROM game_config_conditions WHERE key = ?
            """,
            (safe_key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")

        final_effect_json = (
            _normalize_effect_json(effect_json)
            if effect_json is not None
            else current.get("effect_json") or "{}"
        )
        final_stackable = (1 if stackable else 0) if stackable is not None else int(current.get("stackable", 0))
        if auto_remove is not None:
            final_auto = auto_remove.strip() if isinstance(auto_remove, str) and auto_remove.strip() else None
        else:
            final_auto = current.get("auto_remove")

        conn.execute(
            """
            UPDATE game_config_conditions
            SET label = ?, effect_json = ?, description = ?, is_active = ?, stackable = ?, auto_remove = ?,
                updated_at = datetime('now')
            WHERE key = ?
            """,
            (
                label if label is not None else current["label"],
                final_effect_json,
                description if description is not None else current.get("description"),
                (1 if is_active else 0) if is_active is not None else current.get("is_active", 1),
                final_stackable,
                final_auto,
                safe_key,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, effect_json, description, is_active, stackable, auto_remove,
                   locked_at, created_at, updated_at
            FROM game_config_conditions WHERE key = ?
            """,
            (safe_key,),
        )
        if new_row:
            new_row["stackable"] = bool(new_row.get("stackable"))
        cur_audit = dict(current)
        cur_audit["stackable"] = bool(cur_audit.get("stackable"))
        _audit(conn, "game_config_conditions", safe_key, "UPDATE", cur_audit, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def delete_condition(key: str, *, force: bool) -> None:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, effect_json, description, is_active, locked_at, created_at, updated_at
            FROM game_config_conditions WHERE key = ?
            """,
            (safe_key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")
        conn.execute("DELETE FROM game_config_conditions WHERE key = ?", (safe_key,))
        _audit(conn, "game_config_conditions", safe_key, "DELETE", current, None)
        conn.commit()
    finally:
        conn.close()


def list_items() -> list[dict]:
    rows = _fetch_all(
        """
        SELECT key, label, item_type, description, value_gp, weight, weight_kg, effect_json, is_active,
               proficiency_classes, note,
               locked_at, created_at, updated_at
        FROM game_config_items
        ORDER BY label COLLATE NOCASE ASC, key ASC
        """
    )
    for row in rows:
        row["is_active"] = bool(row.get("is_active", 1))
        try:
            row["proficiency_classes"] = json.loads(row.get("proficiency_classes") or "[]")
        except Exception:
            row["proficiency_classes"] = []
    return rows


def create_item(
    *,
    key: str,
    label: str,
    item_type: str = "misc",
    description: str = "",
    value_gp: int = 0,
    weight: float = 0.0,
    effect_json: str | None = None,
    is_active: bool = True,
    proficiency_classes: list[str] | None = None,
    weight_kg: float = 0.0,
    note: str | None = None,
) -> dict:
    safe_key = _validate_key(key)
    safe_type = _validate_item_type(item_type)
    if value_gp < 0:
        raise ValueError("invalid_value_gp")
    if weight < 0:
        raise ValueError("invalid_weight")
    if weight_kg < 0:
        raise ValueError("invalid_weight_kg")
    pc_json = _validate_proficiency_classes(proficiency_classes if proficiency_classes is not None else [])
    eff: str | None
    if effect_json is None or (isinstance(effect_json, str) and not effect_json.strip()):
        eff = None
    else:
        eff = _normalize_effect_json(effect_json)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        existing = _fetch_one(conn, "SELECT key FROM game_config_items WHERE key = ?", (safe_key,))
        if existing:
            raise ValueError("item_exists")
        conn.execute(
            """
            INSERT INTO game_config_items (
                key, label, item_type, description, value_gp, weight, weight_kg, effect_json, is_active,
                proficiency_classes, note,
                locked_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, datetime('now'), datetime('now'))
            """,
            (
                safe_key,
                label,
                safe_type,
                description or "",
                int(value_gp),
                float(weight),
                float(weight_kg),
                eff,
                1 if is_active else 0,
                pc_json,
                note,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, item_type, description, value_gp, weight, weight_kg, effect_json, is_active,
                   proficiency_classes, note,
                   locked_at, created_at, updated_at
            FROM game_config_items WHERE key = ?
            """,
            (safe_key,),
        )
        if new_row:
            new_row["is_active"] = bool(new_row.get("is_active", 1))
            try:
                new_row["proficiency_classes"] = json.loads(new_row.get("proficiency_classes") or "[]")
            except Exception:
                new_row["proficiency_classes"] = []
        _audit(conn, "game_config_items", safe_key, "CREATE", None, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def update_item(
    key: str,
    *,
    label: str | None,
    item_type: str | None,
    description: str | None,
    value_gp: int | None,
    weight: float | None,
    effect_json: str | None,
    is_active: bool | None,
    force: bool,
    proficiency_classes: list[str] | None = None,
    weight_kg: float | None = None,
    note: str | None = None,
) -> dict:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, item_type, description, value_gp, weight, weight_kg, effect_json, is_active,
                   proficiency_classes, note,
                   locked_at, created_at, updated_at
            FROM game_config_items WHERE key = ?
            """,
            (safe_key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")

        final_type = _validate_item_type(item_type) if item_type is not None else current["item_type"]
        final_label = label if label is not None else current["label"]
        final_desc = description if description is not None else current.get("description") or ""
        final_gp = int(value_gp) if value_gp is not None else int(current["value_gp"])
        final_w = float(weight) if weight is not None else float(current["weight"])
        final_wkg = float(weight_kg) if weight_kg is not None else float(current.get("weight_kg") or 0.0)
        if final_gp < 0:
            raise ValueError("invalid_value_gp")
        if final_w < 0:
            raise ValueError("invalid_weight")
        if final_wkg < 0:
            raise ValueError("invalid_weight_kg")

        if effect_json is None:
            final_effect = current.get("effect_json")
        elif isinstance(effect_json, str) and not effect_json.strip():
            final_effect = None
        else:
            final_effect = _normalize_effect_json(effect_json)

        final_active = (1 if is_active else 0) if is_active is not None else int(current.get("is_active", 1))
        final_pc = (
            _validate_proficiency_classes(proficiency_classes)
            if proficiency_classes is not None
            else (current.get("proficiency_classes") or "[]")
        )
        final_note = note if note is not None else current.get("note")

        conn.execute(
            """
            UPDATE game_config_items
            SET label = ?, item_type = ?, description = ?, value_gp = ?, weight = ?, weight_kg = ?, effect_json = ?,
                is_active = ?, proficiency_classes = ?, note = ?, updated_at = datetime('now')
            WHERE key = ?
            """,
            (
                final_label,
                final_type,
                final_desc,
                final_gp,
                final_w,
                final_wkg,
                final_effect,
                final_active,
                final_pc,
                final_note,
                safe_key,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, item_type, description, value_gp, weight, weight_kg, effect_json, is_active,
                   proficiency_classes, note,
                   locked_at, created_at, updated_at
            FROM game_config_items WHERE key = ?
            """,
            (safe_key,),
        )
        if new_row:
            new_row["is_active"] = bool(new_row.get("is_active", 1))
            try:
                new_row["proficiency_classes"] = json.loads(new_row.get("proficiency_classes") or "[]")
            except Exception:
                new_row["proficiency_classes"] = []
        _audit(conn, "game_config_items", safe_key, "UPDATE", dict(current), new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def delete_item(key: str, *, force: bool) -> None:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, item_type, description, value_gp, weight, weight_kg, effect_json, is_active,
                   proficiency_classes, note,
                   locked_at, created_at, updated_at
            FROM game_config_items WHERE key = ?
            """,
            (safe_key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")
        ref = conn.execute(
            "SELECT COUNT(*) AS c FROM game_config_loot_entries WHERE item_key IS NOT NULL AND item_key = ?",
            (safe_key,),
        ).fetchone()
        if ref and int(ref["c"]) > 0:
            raise ValueError("in_use")
        conn.execute("DELETE FROM game_config_items WHERE key = ?", (safe_key,))
        cur_dict = dict(current)
        cur_dict["is_active"] = bool(cur_dict.get("is_active", 1))
        _audit(conn, "game_config_items", safe_key, "DELETE", cur_dict, None)
        conn.commit()
    finally:
        conn.close()


def list_consumables() -> list[dict]:
    rows = _fetch_all(
        """
        SELECT key, label, description, effect_type, effect_dice, effect_bonus, effect_target,
               weight_kg, charges, base_price, note, is_active, locked_at, created_at, updated_at
        FROM game_config_consumables
        ORDER BY label COLLATE NOCASE ASC, key ASC
        """
    )
    for row in rows:
        row["is_active"] = bool(row.get("is_active", 1))
    return rows


def create_consumable(
    *,
    key: str,
    label: str,
    description: str = "",
    effect_type: str = "misc",
    effect_dice: str | None = None,
    effect_bonus: int = 0,
    effect_target: str = "self",
    weight_kg: float = 0.0,
    charges: int = 1,
    base_price: int = 0,
    note: str | None = None,
    is_active: bool = True,
) -> dict:
    safe_key = _validate_key(key)
    et = _validate_effect_type(effect_type)
    tgt = _validate_effect_target(effect_target)
    dice = _validate_effect_dice(effect_dice)
    if charges < 1:
        raise ValueError("invalid_charges")
    if base_price < 0:
        raise ValueError("invalid_base_price")
    if weight_kg < 0:
        raise ValueError("invalid_weight_kg")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        existing = _fetch_one(conn, "SELECT key FROM game_config_consumables WHERE key = ?", (safe_key,))
        if existing:
            raise ValueError("consumable_exists")
        conn.execute(
            """
            INSERT INTO game_config_consumables (
                key, label, description, effect_type, effect_dice, effect_bonus, effect_target,
                weight_kg, charges, base_price, note, is_active, locked_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, datetime('now'), datetime('now'))
            """,
            (
                safe_key,
                label,
                description or "",
                et,
                dice,
                int(effect_bonus),
                tgt,
                float(weight_kg),
                int(charges),
                int(base_price),
                note,
                1 if is_active else 0,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, description, effect_type, effect_dice, effect_bonus, effect_target,
                   weight_kg, charges, base_price, note, is_active, locked_at, created_at, updated_at
            FROM game_config_consumables WHERE key = ?
            """,
            (safe_key,),
        )
        if new_row:
            new_row["is_active"] = bool(new_row.get("is_active", 1))
        _audit(conn, "game_config_consumables", safe_key, "CREATE", None, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def update_consumable(
    key: str,
    *,
    label: str | None,
    description: str | None,
    effect_type: str | None,
    effect_dice: str | None,
    effect_bonus: int | None,
    effect_target: str | None,
    weight_kg: float | None,
    charges: int | None,
    base_price: int | None,
    note: str | None,
    is_active: bool | None,
    new_key: str | None = None,
    force: bool,
) -> dict:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, description, effect_type, effect_dice, effect_bonus, effect_target,
                   weight_kg, charges, base_price, note, is_active, locked_at, created_at, updated_at
            FROM game_config_consumables WHERE key = ?
            """,
            (safe_key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")

        old_for_audit = dict(current)
        nk_req = (new_key or "").strip() if new_key is not None else ""
        if nk_req:
            nk = _validate_key(nk_req)
            if nk != safe_key:
                if _fetch_one(conn, "SELECT key FROM game_config_consumables WHERE key = ?", (nk,)):
                    raise ValueError("consumable_exists")
                conn.execute(
                    "UPDATE game_config_loot_entries SET consumable_key = ? WHERE consumable_key = ?",
                    (nk, safe_key),
                )
                conn.execute(
                    "UPDATE game_config_consumables SET key = ? WHERE key = ?",
                    (nk, safe_key),
                )
                safe_key = nk

        final_et = _validate_effect_type(effect_type) if effect_type is not None else current["effect_type"]
        final_tgt = _validate_effect_target(effect_target) if effect_target is not None else current["effect_target"]
        if effect_dice is None:
            final_dice = current.get("effect_dice")
        elif isinstance(effect_dice, str) and not effect_dice.strip():
            final_dice = None
        else:
            final_dice = _validate_effect_dice(effect_dice)
        final_bonus = int(effect_bonus) if effect_bonus is not None else int(current.get("effect_bonus") or 0)
        final_wkg = float(weight_kg) if weight_kg is not None else float(current.get("weight_kg") or 0.0)
        final_charges = int(charges) if charges is not None else int(current.get("charges") or 1)
        final_price = int(base_price) if base_price is not None else int(current.get("base_price") or 0)
        if final_charges < 1:
            raise ValueError("invalid_charges")
        if final_price < 0:
            raise ValueError("invalid_base_price")
        if final_wkg < 0:
            raise ValueError("invalid_weight_kg")

        conn.execute(
            """
            UPDATE game_config_consumables
            SET label = ?, description = ?, effect_type = ?, effect_dice = ?, effect_bonus = ?, effect_target = ?,
                weight_kg = ?, charges = ?, base_price = ?, note = ?, is_active = ?, updated_at = datetime('now')
            WHERE key = ?
            """,
            (
                label if label is not None else current["label"],
                description if description is not None else current.get("description") or "",
                final_et,
                final_dice,
                final_bonus,
                final_tgt,
                final_wkg,
                final_charges,
                final_price,
                note if note is not None else current.get("note"),
                (1 if is_active else 0) if is_active is not None else int(current.get("is_active", 1)),
                safe_key,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, description, effect_type, effect_dice, effect_bonus, effect_target,
                   weight_kg, charges, base_price, note, is_active, locked_at, created_at, updated_at
            FROM game_config_consumables WHERE key = ?
            """,
            (safe_key,),
        )
        if new_row:
            new_row["is_active"] = bool(new_row.get("is_active", 1))
        audit_row_key = str(new_row["key"]) if new_row else safe_key
        _audit(conn, "game_config_consumables", audit_row_key, "UPDATE", old_for_audit, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def delete_consumable(key: str, *, force: bool) -> None:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, description, effect_type, effect_dice, effect_bonus, effect_target,
                   weight_kg, charges, base_price, note, is_active, locked_at, created_at, updated_at
            FROM game_config_consumables WHERE key = ?
            """,
            (safe_key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")
        ref = conn.execute(
            """
            SELECT COUNT(*) AS c FROM game_config_loot_entries
            WHERE consumable_key IS NOT NULL AND consumable_key = ?
            """,
            (safe_key,),
        ).fetchone()
        if ref and int(ref["c"]) > 0:
            raise ValueError("in_use")
        conn.execute("DELETE FROM game_config_consumables WHERE key = ?", (safe_key,))
        cur_dict = dict(current)
        cur_dict["is_active"] = bool(cur_dict.get("is_active", 1))
        _audit(conn, "game_config_consumables", safe_key, "DELETE", cur_dict, None)
        conn.commit()
    finally:
        conn.close()


def list_loot_tables() -> list[dict]:
    rows = _fetch_all(
        """
        SELECT key, label, description, is_active, locked_at, created_at, updated_at
        FROM game_config_loot_tables
        ORDER BY label COLLATE NOCASE ASC, key ASC
        """
    )
    for row in rows:
        row["is_active"] = bool(row.get("is_active", 1))
    return rows


def create_loot_table(
    *,
    key: str,
    label: str,
    description: str = "",
    is_active: bool = True,
) -> dict:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        existing = _fetch_one(conn, "SELECT key FROM game_config_loot_tables WHERE key = ?", (safe_key,))
        if existing:
            raise ValueError("loot_table_exists")
        conn.execute(
            """
            INSERT INTO game_config_loot_tables (
                key, label, description, is_active, locked_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, NULL, datetime('now'), datetime('now'))
            """,
            (safe_key, label, description or "", 1 if is_active else 0),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, description, is_active, locked_at, created_at, updated_at
            FROM game_config_loot_tables WHERE key = ?
            """,
            (safe_key,),
        )
        if new_row:
            new_row["is_active"] = bool(new_row.get("is_active", 1))
        _audit(conn, "game_config_loot_tables", safe_key, "CREATE", None, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def update_loot_table(
    key: str,
    *,
    label: str | None,
    description: str | None,
    is_active: bool | None,
    new_key: str | None = None,
    force: bool,
) -> dict:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, description, is_active, locked_at, created_at, updated_at
            FROM game_config_loot_tables WHERE key = ?
            """,
            (safe_key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")
        old_for_audit = dict(current)
        nk_req = (new_key or "").strip() if new_key is not None else ""
        if nk_req:
            nk = _validate_key(nk_req)
            if nk != safe_key:
                if _fetch_one(conn, "SELECT key FROM game_config_loot_tables WHERE key = ?", (nk,)):
                    raise ValueError("loot_table_exists")
                conn.execute(
                    "UPDATE game_config_enemies SET loot_table_key = ? WHERE loot_table_key = ?",
                    (nk, safe_key),
                )
                conn.execute(
                    "UPDATE game_config_loot_entries SET loot_table_key = ? WHERE loot_table_key = ?",
                    (nk, safe_key),
                )
                conn.execute(
                    "UPDATE game_config_loot_tables SET key = ? WHERE key = ?",
                    (nk, safe_key),
                )
                safe_key = nk
        conn.execute(
            """
            UPDATE game_config_loot_tables
            SET label = ?, description = ?, is_active = ?, updated_at = datetime('now')
            WHERE key = ?
            """,
            (
                label if label is not None else current["label"],
                description if description is not None else current.get("description") or "",
                (1 if is_active else 0) if is_active is not None else int(current.get("is_active", 1)),
                safe_key,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, description, is_active, locked_at, created_at, updated_at
            FROM game_config_loot_tables WHERE key = ?
            """,
            (safe_key,),
        )
        if new_row:
            new_row["is_active"] = bool(new_row.get("is_active", 1))
        audit_row_key = str(new_row["key"]) if new_row else safe_key
        _audit(conn, "game_config_loot_tables", audit_row_key, "UPDATE", old_for_audit, new_row)
        conn.commit()
        return new_row or {}
    finally:
        conn.close()


def delete_loot_table(key: str, *, force: bool) -> None:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, description, is_active, locked_at, created_at, updated_at
            FROM game_config_loot_tables WHERE key = ?
            """,
            (safe_key,),
        )
        if not current:
            raise KeyError("not_found")
        if current.get("locked_at") and not force:
            raise PermissionError("locked")
        conn.execute("DELETE FROM game_config_loot_entries WHERE loot_table_key = ?", (safe_key,))
        conn.execute("DELETE FROM game_config_loot_tables WHERE key = ?", (safe_key,))
        cur_dict = dict(current)
        cur_dict["is_active"] = bool(cur_dict.get("is_active", 1))
        _audit(conn, "game_config_loot_tables", safe_key, "DELETE", cur_dict, None)
        conn.commit()
    finally:
        conn.close()


def _loot_entry_source_keys(
    item_key: str | None,
    consumable_key: str | None,
    weapon_key: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    ik = _validate_key(item_key) if item_key and str(item_key).strip() else None
    ck = _validate_key(consumable_key) if consumable_key and str(consumable_key).strip() else None
    wk = _validate_key(weapon_key) if weapon_key and str(weapon_key).strip() else None
    n = sum(1 for x in (ik, ck, wk) if x is not None)
    if n != 1:
        raise ValueError("invalid_loot_entry_source")
    return ik, ck, wk


def list_loot_entries(loot_table_key: str) -> list[dict]:
    safe_key = _validate_key(loot_table_key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        parent = _fetch_one(conn, "SELECT key FROM game_config_loot_tables WHERE key = ?", (safe_key,))
        if not parent:
            raise ValueError("loot_table_not_found")
        rows = conn.execute(
            """
            SELECT e.id, e.loot_table_key, e.item_key, e.consumable_key, e.weapon_key, e.weight, e.qty_min, e.qty_max,
                   i.label AS item_label,
                   c.label AS consumable_label,
                   w.label AS weapon_label,
                   COALESCE(i.label, c.label, w.label) AS source_label,
                   CASE
                       WHEN e.item_key IS NOT NULL THEN 'item'
                       WHEN e.consumable_key IS NOT NULL THEN 'consumable'
                       ELSE 'weapon'
                   END AS source_type
            FROM game_config_loot_entries e
            LEFT JOIN game_config_items i ON i.key = e.item_key
            LEFT JOIN game_config_consumables c ON c.key = e.consumable_key
            LEFT JOIN game_config_weapons w ON w.key = e.weapon_key
            WHERE e.loot_table_key = ?
            ORDER BY source_label COLLATE NOCASE ASC,
                     COALESCE(e.item_key, e.consumable_key, e.weapon_key) ASC
            """,
            (safe_key,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def upsert_loot_entry(
    loot_table_key: str,
    *,
    item_key: str | None = None,
    consumable_key: str | None = None,
    weapon_key: str | None = None,
    weight: int,
    qty_min: int,
    qty_max: int,
) -> dict:
    lt = _validate_key(loot_table_key)
    ik, ck, wk = _loot_entry_source_keys(item_key, consumable_key, weapon_key)
    if weight < 1:
        raise ValueError("invalid_weight")
    if qty_min < 1 or qty_max < 1 or qty_min > qty_max:
        raise ValueError("invalid_qty_range")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        parent = _fetch_one(conn, "SELECT key FROM game_config_loot_tables WHERE key = ?", (lt,))
        if not parent:
            raise ValueError("loot_table_not_found")
        if ik is not None:
            item = _fetch_one(conn, "SELECT key FROM game_config_items WHERE key = ?", (ik,))
            if not item:
                raise ValueError("item_not_found")
            conn.execute(
                """
                INSERT INTO game_config_loot_entries (loot_table_key, item_key, consumable_key, weapon_key, weight, qty_min, qty_max)
                VALUES (?, ?, NULL, NULL, ?, ?, ?)
                ON CONFLICT(loot_table_key, item_key) WHERE item_key IS NOT NULL DO UPDATE SET
                    weight = excluded.weight,
                    qty_min = excluded.qty_min,
                    qty_max = excluded.qty_max
                """,
                (lt, ik, weight, qty_min, qty_max),
            )
            row = _fetch_one(
                conn,
                """
                SELECT e.id, e.loot_table_key, e.item_key, e.consumable_key, e.weapon_key, e.weight, e.qty_min, e.qty_max,
                       i.label AS item_label,
                       c.label AS consumable_label,
                       w.label AS weapon_label,
                       COALESCE(i.label, c.label, w.label) AS source_label,
                       CASE
                           WHEN e.item_key IS NOT NULL THEN 'item'
                           WHEN e.consumable_key IS NOT NULL THEN 'consumable'
                           ELSE 'weapon'
                       END AS source_type
                FROM game_config_loot_entries e
                LEFT JOIN game_config_items i ON i.key = e.item_key
                LEFT JOIN game_config_consumables c ON c.key = e.consumable_key
                LEFT JOIN game_config_weapons w ON w.key = e.weapon_key
                WHERE e.loot_table_key = ? AND e.item_key = ?
                """,
                (lt, ik),
            )
        elif ck is not None:
            cons = _fetch_one(conn, "SELECT key FROM game_config_consumables WHERE key = ?", (ck,))
            if not cons:
                raise ValueError("consumable_not_found")
            conn.execute(
                """
                INSERT INTO game_config_loot_entries (loot_table_key, item_key, consumable_key, weapon_key, weight, qty_min, qty_max)
                VALUES (?, NULL, ?, NULL, ?, ?, ?)
                ON CONFLICT(loot_table_key, consumable_key) WHERE consumable_key IS NOT NULL DO UPDATE SET
                    weight = excluded.weight,
                    qty_min = excluded.qty_min,
                    qty_max = excluded.qty_max
                """,
                (lt, ck, weight, qty_min, qty_max),
            )
            row = _fetch_one(
                conn,
                """
                SELECT e.id, e.loot_table_key, e.item_key, e.consumable_key, e.weapon_key, e.weight, e.qty_min, e.qty_max,
                       i.label AS item_label,
                       c.label AS consumable_label,
                       w.label AS weapon_label,
                       COALESCE(i.label, c.label, w.label) AS source_label,
                       CASE
                           WHEN e.item_key IS NOT NULL THEN 'item'
                           WHEN e.consumable_key IS NOT NULL THEN 'consumable'
                           ELSE 'weapon'
                       END AS source_type
                FROM game_config_loot_entries e
                LEFT JOIN game_config_items i ON i.key = e.item_key
                LEFT JOIN game_config_consumables c ON c.key = e.consumable_key
                LEFT JOIN game_config_weapons w ON w.key = e.weapon_key
                WHERE e.loot_table_key = ? AND e.consumable_key = ?
                """,
                (lt, ck),
            )
        else:
            weap = _fetch_one(conn, "SELECT key FROM game_config_weapons WHERE key = ?", (wk,))
            if not weap:
                raise ValueError("weapon_not_found")
            conn.execute(
                """
                INSERT INTO game_config_loot_entries (loot_table_key, item_key, consumable_key, weapon_key, weight, qty_min, qty_max)
                VALUES (?, NULL, NULL, ?, ?, ?, ?)
                ON CONFLICT(loot_table_key, weapon_key) WHERE weapon_key IS NOT NULL DO UPDATE SET
                    weight = excluded.weight,
                    qty_min = excluded.qty_min,
                    qty_max = excluded.qty_max
                """,
                (lt, wk, weight, qty_min, qty_max),
            )
            row = _fetch_one(
                conn,
                """
                SELECT e.id, e.loot_table_key, e.item_key, e.consumable_key, e.weapon_key, e.weight, e.qty_min, e.qty_max,
                       i.label AS item_label,
                       c.label AS consumable_label,
                       w.label AS weapon_label,
                       COALESCE(i.label, c.label, w.label) AS source_label,
                       CASE
                           WHEN e.item_key IS NOT NULL THEN 'item'
                           WHEN e.consumable_key IS NOT NULL THEN 'consumable'
                           ELSE 'weapon'
                       END AS source_type
                FROM game_config_loot_entries e
                LEFT JOIN game_config_items i ON i.key = e.item_key
                LEFT JOIN game_config_consumables c ON c.key = e.consumable_key
                LEFT JOIN game_config_weapons w ON w.key = e.weapon_key
                WHERE e.loot_table_key = ? AND e.weapon_key = ?
                """,
                (lt, wk),
            )
        conn.commit()
        return row or {}
    finally:
        conn.close()


def delete_loot_entry(
    loot_table_key: str,
    item_key: str | None = None,
    consumable_key: str | None = None,
    weapon_key: str | None = None,
) -> None:
    lt = _validate_key(loot_table_key)
    ik, ck, wk = _loot_entry_source_keys(item_key, consumable_key, weapon_key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        if ik is not None:
            cur = _fetch_one(
                conn,
                """
                SELECT id, loot_table_key, item_key, consumable_key, weapon_key, weight, qty_min, qty_max
                FROM game_config_loot_entries WHERE loot_table_key = ? AND item_key = ?
                """,
                (lt, ik),
            )
            audit_id = f"{lt}:item:{ik}"
        elif ck is not None:
            cur = _fetch_one(
                conn,
                """
                SELECT id, loot_table_key, item_key, consumable_key, weapon_key, weight, qty_min, qty_max
                FROM game_config_loot_entries WHERE loot_table_key = ? AND consumable_key = ?
                """,
                (lt, ck),
            )
            audit_id = f"{lt}:consumable:{ck}"
        else:
            cur = _fetch_one(
                conn,
                """
                SELECT id, loot_table_key, item_key, consumable_key, weapon_key, weight, qty_min, qty_max
                FROM game_config_loot_entries WHERE loot_table_key = ? AND weapon_key = ?
                """,
                (lt, wk),
            )
            audit_id = f"{lt}:weapon:{wk}"
        if not cur:
            raise KeyError("not_found")
        if ik is not None:
            conn.execute(
                "DELETE FROM game_config_loot_entries WHERE loot_table_key = ? AND item_key = ?",
                (lt, ik),
            )
        elif ck is not None:
            conn.execute(
                "DELETE FROM game_config_loot_entries WHERE loot_table_key = ? AND consumable_key = ?",
                (lt, ck),
            )
        else:
            conn.execute(
                "DELETE FROM game_config_loot_entries WHERE loot_table_key = ? AND weapon_key = ?",
                (lt, wk),
            )
        _audit(conn, "game_config_loot_entries", audit_id, "DELETE", dict(cur), None)
        conn.commit()
    finally:
        conn.close()


def _validate_starter_items_json(raw: str | None) -> str:
    if raw is None or not str(raw).strip():
        return "[]"
    try:
        data = json.loads(str(raw))
    except json.JSONDecodeError as e:
        raise ValueError("invalid_starter_items_json") from e
    if not isinstance(data, list):
        raise ValueError("invalid_starter_items_json")
    for entry in data:
        if not isinstance(entry, dict):
            raise ValueError("invalid_starter_items_json")
        wk = entry.get("weapon_key")
        ik = entry.get("item_key")
        ck = entry.get("consumable_key")
        n = sum(1 for x in (wk, ik, ck) if x is not None and str(x).strip())
        if n != 1:
            raise ValueError("invalid_starter_items_json")
        if entry.get("quantity") is not None:
            q = int(entry["quantity"])
            if q < 1:
                raise ValueError("invalid_starter_items_json")
    return json.dumps(data, ensure_ascii=False)


def list_archetypes() -> list[dict]:
    return _fetch_all(
        """
        SELECT key, label, description, starter_items_json, starter_gold_gp, is_active,
               locked_at, created_at, updated_at
        FROM game_config_archetypes
        ORDER BY key ASC
        """
    )


def update_archetype(
    key: str,
    *,
    label: str | None = None,
    description: str | None = None,
    starter_items_json: str | None = None,
    starter_gold_gp: int | None = None,
    is_active: bool | None = None,
    force: bool = False,
) -> dict:
    _ = force
    safe_key = str(key or "").strip().lower()
    if not KEY_RE.match(safe_key):
        raise ValueError("invalid_key")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        old = _fetch_one(conn, "SELECT * FROM game_config_archetypes WHERE key = ?", (safe_key,))
        if not old:
            raise KeyError("not_found")
        if old.get("locked_at") and not force:
            raise PermissionError("locked")

        body: dict[str, object] = {}
        if label is not None:
            body["label"] = str(label).strip()
        if description is not None:
            body["description"] = str(description)
        if starter_items_json is not None:
            body["starter_items_json"] = _validate_starter_items_json(starter_items_json)
        if starter_gold_gp is not None:
            g = int(starter_gold_gp)
            if g < 0:
                raise ValueError("invalid_starter_gold_gp")
            body["starter_gold_gp"] = g
        if is_active is not None:
            body["is_active"] = 1 if is_active else 0
        if not body:
            return dict(old)

        sets = ", ".join(f"{k} = ?" for k in body)
        vals = list(body.values())
        vals.append(safe_key)
        conn.execute(
            f"UPDATE game_config_archetypes SET {sets}, updated_at = datetime('now') WHERE key = ?",
            vals,
        )
        new_row = _fetch_one(conn, "SELECT * FROM game_config_archetypes WHERE key = ?", (safe_key,))
        _audit(conn, "game_config_archetypes", safe_key, "UPDATE", old, new_row)
        conn.commit()
        return dict(new_row or {})
    finally:
        conn.close()
