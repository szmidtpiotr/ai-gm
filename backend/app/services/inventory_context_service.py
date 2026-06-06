import sqlite3


def build_inventory_block(conn: sqlite3.Connection, character_id: int) -> str:
    """Build an inventory context block for LLM system prompt injection.

    Prevents LLM from hallucinating 'you lost all your items' when character
    has a full inventory — injected as factual constraint per turn.
    Returns "" on any DB error so the caller is never blocked.
    """
    try:
        return _build(conn, character_id)
    except Exception:
        return ""


def _build(conn: sqlite3.Connection, character_id: int) -> str:
    char = conn.execute(
        "SELECT gold_gp FROM characters WHERE id = ?", (character_id,)
    ).fetchone()
    if char is None:
        return ""

    gold = char["gold_gp"] if char["gold_gp"] is not None else 0

    equipped_weapons = conn.execute(
        """SELECT ci.weapon_key, ci.slot,
                  COALESCE(gw.label, ci.weapon_key) AS label,
                  gw.damage_die
           FROM character_inventory ci
           LEFT JOIN game_config_weapons gw ON gw.key = ci.weapon_key
           WHERE ci.character_id = ? AND ci.weapon_key IS NOT NULL AND ci.equipped = 1
           ORDER BY ci.slot""",
        (character_id,),
    ).fetchall()

    equipped_items = conn.execute(
        """SELECT ci.item_key, ci.slot,
                  COALESCE(gi.label, ci.item_key) AS label
           FROM character_inventory ci
           LEFT JOIN game_config_items gi ON gi.key = ci.item_key
           WHERE ci.character_id = ? AND ci.item_key IS NOT NULL
                 AND ci.item_key != '__narrative__' AND ci.equipped = 1
           ORDER BY ci.slot""",
        (character_id,),
    ).fetchall()

    backpack_rows = conn.execute(
        """SELECT ci.item_key, ci.weapon_key, ci.consumable_key, ci.quantity,
                  COALESCE(gi.label, gw.label, gc.label,
                           ci.item_key, ci.weapon_key, ci.consumable_key) AS label
           FROM character_inventory ci
           LEFT JOIN game_config_items gi ON gi.key = ci.item_key
           LEFT JOIN game_config_weapons gw ON gw.key = ci.weapon_key
           LEFT JOIN game_config_consumables gc ON gc.key = ci.consumable_key
           WHERE ci.character_id = ? AND ci.equipped = 0
                 AND (ci.item_key IS NULL OR ci.item_key != '__narrative__')
           ORDER BY ci.acquired_at DESC
           LIMIT 10""",
        (character_id,),
    ).fetchall()

    narrative_rows = conn.execute(
        """SELECT ci.label
           FROM character_inventory ci
           WHERE ci.character_id = ? AND ci.item_key = '__narrative__'
                 AND ci.label IS NOT NULL
           ORDER BY ci.acquired_at DESC
           LIMIT 5""",
        (character_id,),
    ).fetchall()

    lines = ["[EKWIPUNEK POSTACI — FAKTY MECHANICZNE]"]

    if equipped_weapons:
        parts = []
        for w in equipped_weapons:
            name = w["label"] or w["weapon_key"]
            die = w["damage_die"] or ""
            parts.append(f"{name} ({die})" if die else name)
        lines.append(f"Broń: {', '.join(parts)}")

    if equipped_items:
        parts = [r["label"] or r["item_key"] for r in equipped_items]
        lines.append(f"Wyposażenie: {', '.join(parts)}")

    if backpack_rows:
        parts = []
        for r in backpack_rows:
            name = r["label"] or r["item_key"] or r["weapon_key"] or r["consumable_key"] or "?"
            qty = r["quantity"]
            parts.append(f"{name} ×{qty}" if qty > 1 else name)
        lines.append(f"W plecaku: {', '.join(parts)}")

    lines.append(f"Złoto: {gold} GP")

    if narrative_rows:
        narr_parts = [r["label"] for r in narrative_rows if r["label"]]
        if narr_parts:
            lines.append(f"[Kluczowe przedmioty fabularne: {'; '.join(narr_parts)}]")

    return "\n".join(lines)
