import logging
import sqlite3

_log = logging.getLogger(__name__)


def build_inventory_block(conn: sqlite3.Connection, character_id: int) -> str:
    """Build an inventory context block for LLM system prompt injection.

    Prevents LLM from hallucinating 'you lost all your items' when character
    has a full inventory — injected as factual constraint per turn.
    Returns "" on any DB error so the caller is never blocked.
    """
    try:
        return _build(conn, character_id)
    except Exception as e:
        _log.warning("inventory_context_build_failed", character_id=character_id, error=str(e))
        return ""


def _has_game_items_table(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("SELECT 1 FROM game_items LIMIT 1")
        return True
    except Exception:
        return False


def _build(conn: sqlite3.Connection, character_id: int) -> str:
    char = conn.execute(
        "SELECT gold_gp FROM characters WHERE id = ?", (character_id,)
    ).fetchone()
    if char is None:
        return ""

    gold = char["gold_gp"] if char["gold_gp"] is not None else 0

    # U11b (#557): czyta z game_items; fallback do starych tabel gdy baza nie ma game_items
    if _has_game_items_table(conn):
        equipped_weapons = conn.execute(
            """SELECT ci.weapon_key, ci.slot,
                      COALESCE(gi.label, ci.weapon_key) AS label,
                      json_extract(gi.weapon_data, '$.damage_die') AS damage_die
               FROM character_inventory ci
               LEFT JOIN game_items gi ON gi.key = ci.weapon_key AND gi.kind = 'weapon'
               WHERE ci.character_id = ? AND ci.weapon_key IS NOT NULL AND ci.equipped = 1
               ORDER BY ci.slot""",
            (character_id,),
        ).fetchall()

        equipped_items = conn.execute(
            """SELECT ci.item_key, ci.slot,
                      COALESCE(gi.label, ci.item_key) AS label
               FROM character_inventory ci
               LEFT JOIN game_items gi ON gi.key = ci.item_key
               WHERE ci.character_id = ? AND ci.item_key IS NOT NULL
                     AND ci.item_key != '__narrative__' AND ci.equipped = 1
               ORDER BY ci.slot""",
            (character_id,),
        ).fetchall()

        backpack_rows = conn.execute(
            """SELECT ci.item_key, ci.weapon_key, ci.consumable_key, ci.quantity,
                      COALESCE(gi.label, ci.item_key, ci.weapon_key, ci.consumable_key) AS label
               FROM character_inventory ci
               LEFT JOIN game_items gi ON gi.key = COALESCE(
                   NULLIF(TRIM(COALESCE(ci.weapon_key, '')), ''),
                   NULLIF(TRIM(COALESCE(ci.item_key, '')), ''),
                   NULLIF(TRIM(COALESCE(ci.consumable_key, '')), '')
               )
               WHERE ci.character_id = ? AND ci.equipped = 0
                     AND (ci.item_key IS NULL OR ci.item_key != '__narrative__')
               ORDER BY ci.acquired_at DESC
               LIMIT 10""",
            (character_id,),
        ).fetchall()
    else:
        # Fallback: stare tabele (testowe bazy bez game_items, przed U11c)
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

    # #1304 (opcja A) — flavour descriptions of held items so the narrator can react
    # faithfully when a player declares e.g. "używam lunety by dostrzec, co dalej".
    # Descriptions live in TWO tables: game_items (seeds like the Luneta) AND
    # game_config_items (Kuźnia reward-spine / forge items — tpl<N>_* keys). We union
    # both so template-creator items are covered, not just seeds. Capped to keep the
    # prompt lean; kept in a SEPARATE section from the mechanical facts above, with an
    # explicit guardrail: the description is colour only, no roll bonuses / mechanics.
    if _has_game_items_table(conn):
        flavour_rows = conn.execute(
            """WITH held AS (
                   SELECT item_key, MAX(acquired_at) AS acq
                   FROM character_inventory
                   WHERE character_id = ? AND item_key IS NOT NULL
                         AND item_key != '__narrative__'
                   GROUP BY item_key
               )
               SELECT COALESCE(gi.label, gci.label, h.item_key) AS label,
                      COALESCE(gi.description, gci.description) AS description,
                      COALESCE(gi.rarity, gci.rarity, 0) AS rarity, h.acq
               FROM held h
               LEFT JOIN game_items gi ON gi.key = h.item_key
               LEFT JOIN game_config_items gci ON gci.key = h.item_key
               WHERE TRIM(COALESCE(gi.description, gci.description, '')) != ''
               ORDER BY rarity DESC, h.acq DESC
               LIMIT 30""",
            (character_id,),
        ).fetchall()
    else:
        flavour_rows = conn.execute(
            """SELECT COALESCE(gci.label, ci.item_key) AS label, gci.description,
                      COALESCE(gci.rarity, 0) AS rarity, MAX(ci.acquired_at) AS acq
               FROM character_inventory ci
               JOIN game_config_items gci ON gci.key = ci.item_key
               WHERE ci.character_id = ? AND ci.item_key IS NOT NULL
                     AND ci.item_key != '__narrative__'
                     AND TRIM(COALESCE(gci.description, '')) != ''
               GROUP BY gci.key
               ORDER BY rarity DESC, acq DESC
               LIMIT 30""",
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

    # #1304 — separate flavour section (see query above). Guardrail line is explicit so the
    # LLM treats these as narrative colour, never as a mechanical licence.
    # Dedupe by label (multiple keys can share a label, e.g. two identical pergaminy)
    # and drop empty placeholder descriptions ("Narracyjny przedmiot: <label>" carries no
    # colour). Cap at 6 lines so the prompt stays lean.
    flavour_out: list[tuple[str, str]] = []
    seen_labels: set[str] = set()
    for r in flavour_rows:
        label = (r["label"] or "").strip()
        desc = (r["description"] or "").strip()
        if not label or label in seen_labels:
            continue
        if not desc or desc.lower().startswith("narracyjny przedmiot:"):
            continue
        seen_labels.add(label)
        if len(desc) > 220:
            desc = desc[:217].rstrip() + "…"
        flavour_out.append((label, desc))
        if len(flavour_out) >= 6:
            break

    if flavour_out:
        lines.append("")
        lines.append(
            "[PRZEDMIOTY FABULARNE — opis wyłącznie dla kolorytu narracji; "
            "gdy gracz deklaruje użycie takiego przedmiotu, opisz efekt zgodnie z jego opisem, "
            "ale NIE przyznawaj bonusów do rzutów ani efektów mechanicznych — mechanika należy do silnika]"
        )
        for label, desc in flavour_out:
            lines.append(f"- {label}: {desc}")

    return "\n".join(lines)
