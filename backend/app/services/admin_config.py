import json
import re
import sqlite3


DB_PATH = "/data/ai_gm.db"
KEY_RE = re.compile(r"^[a-z0-9_]{1,40}$")
DAMAGE_DIE_RE = re.compile(r"^\d*d\d+$")
ALLOWED_CLASSES = {"warrior", "ranger", "scholar"}


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
