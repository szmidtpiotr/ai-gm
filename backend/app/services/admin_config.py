import json
import re
import sqlite3


DB_PATH = "/data/ai_gm.db"
KEY_RE = re.compile(r"^[a-z0-9_]{1,40}$")
DAMAGE_DIE_RE = re.compile(r"^\d*d\d+$")
ALLOWED_CLASSES = {"warrior", "ranger", "scholar"}
ALLOWED_ITEM_TYPES = {"weapon", "armor", "consumable", "misc", "quest"}


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
        SELECT key, label, damage_die, linked_stat, allowed_classes, is_active, locked_at, created_at, updated_at
        FROM game_config_weapons
        ORDER BY key ASC
        """
    )
    for row in rows:
        try:
            row["allowed_classes"] = json.loads(row.get("allowed_classes") or "[]")
        except Exception:
            row["allowed_classes"] = []
    return rows


def list_enemies() -> list[dict]:
    return _fetch_all(
        """
        SELECT key, label, hp_base, ac_base, attack_bonus, damage_die, description, is_active, locked_at, created_at, updated_at
        FROM game_config_enemies
        ORDER BY key ASC
        """
    )


def list_conditions() -> list[dict]:
    return _fetch_all(
        """
        SELECT key, label, effect_json, description, is_active, locked_at, created_at, updated_at
        FROM game_config_conditions
        ORDER BY key ASC
        """
    )


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
    sort_order: int = 0,
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

        conn.execute(
            """
            INSERT INTO game_config_skills (key, label, linked_stat, rank_ceiling, sort_order, locked_at, description)
            VALUES (?, ?, ?, ?, ?, NULL, ?)
            """,
            (key, label, linked_stat, rank_ceiling, sort_order, description or ""),
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
) -> dict:
    safe_key = _validate_key(key)
    safe_damage_die = _validate_damage_die(damage_die)
    safe_allowed_classes = _validate_allowed_classes(allowed_classes)

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
                key, label, damage_die, linked_stat, allowed_classes, is_active, locked_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, datetime('now'), datetime('now'))
            """,
            (safe_key, label, safe_damage_die, linked_stat, safe_allowed_classes, 1 if is_active else 0),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, damage_die, linked_stat, allowed_classes, is_active, locked_at, created_at, updated_at
            FROM game_config_weapons WHERE key = ?
            """,
            (safe_key,),
        )
        if new_row:
            new_row["allowed_classes"] = json.loads(new_row.get("allowed_classes") or "[]")
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
) -> dict:
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

        conn.execute(
            """
            UPDATE game_config_weapons
            SET label = ?, damage_die = ?, linked_stat = ?, allowed_classes = ?, is_active = ?, updated_at = datetime('now')
            WHERE key = ?
            """,
            (
                label if label is not None else current["label"],
                final_damage_die,
                final_linked_stat,
                final_allowed_classes,
                final_is_active,
                safe_key,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, damage_die, linked_stat, allowed_classes, is_active, locked_at, created_at, updated_at
            FROM game_config_weapons WHERE key = ?
            """,
            (safe_key,),
        )
        old_for_audit = dict(current)
        old_for_audit["allowed_classes"] = json.loads(old_for_audit.get("allowed_classes") or "[]")
        if new_row:
            new_row["allowed_classes"] = json.loads(new_row.get("allowed_classes") or "[]")
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
) -> dict:
    safe_key = _validate_key(key)
    safe_damage_die = _validate_damage_die(damage_die)
    if hp_base < 1:
        raise ValueError("invalid_hp_base")
    if ac_base < 1:
        raise ValueError("invalid_ac_base")
    if attack_bonus < 0:
        raise ValueError("invalid_attack_bonus")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        existing = _fetch_one(conn, "SELECT key FROM game_config_enemies WHERE key = ?", (safe_key,))
        if existing:
            raise ValueError("enemy_exists")
        conn.execute(
            """
            INSERT INTO game_config_enemies (
                key, label, hp_base, ac_base, attack_bonus, damage_die, description, is_active, locked_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, datetime('now'), datetime('now'))
            """,
            (
                safe_key,
                label,
                hp_base,
                ac_base,
                attack_bonus,
                safe_damage_die,
                description,
                1 if is_active else 0,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, hp_base, ac_base, attack_bonus, damage_die, description, is_active, locked_at, created_at, updated_at
            FROM game_config_enemies WHERE key = ?
            """,
            (safe_key,),
        )
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
) -> dict:
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

        final_hp_base = hp_base if hp_base is not None else current["hp_base"]
        final_ac_base = ac_base if ac_base is not None else current["ac_base"]
        final_attack_bonus = attack_bonus if attack_bonus is not None else current["attack_bonus"]
        final_damage_die = _validate_damage_die(damage_die) if damage_die is not None else current["damage_die"]
        if final_hp_base < 1:
            raise ValueError("invalid_hp_base")
        if final_ac_base < 1:
            raise ValueError("invalid_ac_base")
        if final_attack_bonus < 0:
            raise ValueError("invalid_attack_bonus")

        conn.execute(
            """
            UPDATE game_config_enemies
            SET label = ?, hp_base = ?, ac_base = ?, attack_bonus = ?, damage_die = ?, description = ?, is_active = ?, updated_at = datetime('now')
            WHERE key = ?
            """,
            (
                label if label is not None else current["label"],
                final_hp_base,
                final_ac_base,
                final_attack_bonus,
                final_damage_die,
                description if description is not None else current.get("description"),
                (1 if is_active else 0) if is_active is not None else current.get("is_active", 1),
                safe_key,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, hp_base, ac_base, attack_bonus, damage_die, description, is_active, locked_at, created_at, updated_at
            FROM game_config_enemies WHERE key = ?
            """,
            (safe_key,),
        )
        _audit(conn, "game_config_enemies", safe_key, "UPDATE", current, new_row)
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
                key, label, effect_json, description, is_active, locked_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, NULL, datetime('now'), datetime('now'))
            """,
            (safe_key, label, safe_effect_json, description, 1 if is_active else 0),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, effect_json, description, is_active, locked_at, created_at, updated_at
            FROM game_config_conditions WHERE key = ?
            """,
            (safe_key,),
        )
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
) -> dict:
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

        final_effect_json = (
            _normalize_effect_json(effect_json)
            if effect_json is not None
            else current.get("effect_json") or "{}"
        )
        conn.execute(
            """
            UPDATE game_config_conditions
            SET label = ?, effect_json = ?, description = ?, is_active = ?, updated_at = datetime('now')
            WHERE key = ?
            """,
            (
                label if label is not None else current["label"],
                final_effect_json,
                description if description is not None else current.get("description"),
                (1 if is_active else 0) if is_active is not None else current.get("is_active", 1),
                safe_key,
            ),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, effect_json, description, is_active, locked_at, created_at, updated_at
            FROM game_config_conditions WHERE key = ?
            """,
            (safe_key,),
        )
        _audit(conn, "game_config_conditions", safe_key, "UPDATE", current, new_row)
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
        SELECT key, label, item_type, description, value_gp, weight, effect_json, is_active,
               locked_at, created_at, updated_at
        FROM game_config_items
        ORDER BY label COLLATE NOCASE ASC, key ASC
        """
    )
    for row in rows:
        row["is_active"] = bool(row.get("is_active", 1))
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
) -> dict:
    safe_key = _validate_key(key)
    safe_type = _validate_item_type(item_type)
    if value_gp < 0:
        raise ValueError("invalid_value_gp")
    if weight < 0:
        raise ValueError("invalid_weight")
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
                key, label, item_type, description, value_gp, weight, effect_json, is_active,
                locked_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, datetime('now'), datetime('now'))
            """,
            (safe_key, label, safe_type, description or "", int(value_gp), float(weight), eff, 1 if is_active else 0),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, item_type, description, value_gp, weight, effect_json, is_active,
                   locked_at, created_at, updated_at
            FROM game_config_items WHERE key = ?
            """,
            (safe_key,),
        )
        if new_row:
            new_row["is_active"] = bool(new_row.get("is_active", 1))
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
) -> dict:
    safe_key = _validate_key(key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        current = _fetch_one(
            conn,
            """
            SELECT key, label, item_type, description, value_gp, weight, effect_json, is_active,
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
        if final_gp < 0:
            raise ValueError("invalid_value_gp")
        if final_w < 0:
            raise ValueError("invalid_weight")

        if effect_json is None:
            final_effect = current.get("effect_json")
        elif isinstance(effect_json, str) and not effect_json.strip():
            final_effect = None
        else:
            final_effect = _normalize_effect_json(effect_json)

        final_active = (1 if is_active else 0) if is_active is not None else int(current.get("is_active", 1))

        conn.execute(
            """
            UPDATE game_config_items
            SET label = ?, item_type = ?, description = ?, value_gp = ?, weight = ?, effect_json = ?,
                is_active = ?, updated_at = datetime('now')
            WHERE key = ?
            """,
            (final_label, final_type, final_desc, final_gp, final_w, final_effect, final_active, safe_key),
        )
        new_row = _fetch_one(
            conn,
            """
            SELECT key, label, item_type, description, value_gp, weight, effect_json, is_active,
                   locked_at, created_at, updated_at
            FROM game_config_items WHERE key = ?
            """,
            (safe_key,),
        )
        if new_row:
            new_row["is_active"] = bool(new_row.get("is_active", 1))
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
            SELECT key, label, item_type, description, value_gp, weight, effect_json, is_active,
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
            "SELECT COUNT(*) AS c FROM game_config_loot_entries WHERE item_key = ?",
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
        _audit(conn, "game_config_loot_tables", safe_key, "UPDATE", dict(current), new_row)
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
            SELECT e.id, e.loot_table_key, e.item_key, e.weight, e.qty_min, e.qty_max,
                   i.label AS item_label
            FROM game_config_loot_entries e
            JOIN game_config_items i ON i.key = e.item_key
            WHERE e.loot_table_key = ?
            ORDER BY i.label COLLATE NOCASE ASC, e.item_key ASC
            """,
            (safe_key,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def upsert_loot_entry(
    loot_table_key: str,
    item_key: str,
    weight: int,
    qty_min: int,
    qty_max: int,
) -> dict:
    lt = _validate_key(loot_table_key)
    ik = _validate_key(item_key)
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
        item = _fetch_one(conn, "SELECT key FROM game_config_items WHERE key = ?", (ik,))
        if not item:
            raise ValueError("item_not_found")
        conn.execute(
            """
            INSERT INTO game_config_loot_entries (loot_table_key, item_key, weight, qty_min, qty_max)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(loot_table_key, item_key) DO UPDATE SET
                weight = excluded.weight,
                qty_min = excluded.qty_min,
                qty_max = excluded.qty_max
            """,
            (lt, ik, weight, qty_min, qty_max),
        )
        row = _fetch_one(
            conn,
            """
            SELECT e.id, e.loot_table_key, e.item_key, e.weight, e.qty_min, e.qty_max, i.label AS item_label
            FROM game_config_loot_entries e
            JOIN game_config_items i ON i.key = e.item_key
            WHERE e.loot_table_key = ? AND e.item_key = ?
            """,
            (lt, ik),
        )
        conn.commit()
        return row or {}
    finally:
        conn.close()


def delete_loot_entry(loot_table_key: str, item_key: str) -> None:
    lt = _validate_key(loot_table_key)
    ik = _validate_key(item_key)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = _fetch_one(
            conn,
            """
            SELECT id, loot_table_key, item_key, weight, qty_min, qty_max
            FROM game_config_loot_entries WHERE loot_table_key = ? AND item_key = ?
            """,
            (lt, ik),
        )
        if not cur:
            raise KeyError("not_found")
        conn.execute(
            "DELETE FROM game_config_loot_entries WHERE loot_table_key = ? AND item_key = ?",
            (lt, ik),
        )
        _audit(conn, "game_config_loot_entries", f"{lt}:{ik}", "DELETE", dict(cur), None)
        conn.commit()
    finally:
        conn.close()
