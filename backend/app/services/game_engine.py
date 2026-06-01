import random
import re
import sqlite3
import json

from app.core.logging import get_logger
from app.core.turn_engine import buildmessages, loadrecentturns
from app.services.config_service import build_runtime_config_block
from app.services.gm_plan_schema import format_gm_plan_block
from app.services.dice import infer_roll_type, parse_character_sheet
from app.services.llm_service import generate_chat
from app.services.solo_death_service import DEATH_SAVE_FAILURE_THRESHOLD


logger = get_logger(__name__)


def resolve_enemy_loot(enemy_key: str) -> list[dict]:
    """
    Roll this enemy's drop_chance, then weight-pick one row from its loot table.
    Returns [{source_type, source_key, qty}, ...] with no duplicated catalog data.
    """
    from app.services.admin_config import DB_PATH, list_loot_entries

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT loot_table_key, drop_chance FROM game_config_enemies WHERE key = ?",
            (enemy_key,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return []
    lt = row["loot_table_key"]
    if not lt:
        return []
    dc = float(row["drop_chance"] if row["drop_chance"] is not None else 1.0)
    if random.random() > dc:
        return []

    entries = list_loot_entries(str(lt))
    if not entries:
        return []
    total_w = sum(max(1, int(e.get("weight") or 0)) for e in entries)
    if total_w < 1:
        return []
    r = random.random() * total_w
    acc = 0.0
    chosen = entries[-1]
    for e in entries:
        w = max(1, int(e.get("weight") or 0))
        acc += w
        if r < acc:
            chosen = e
            break
    st = str(chosen.get("source_type") or "item")
    if st == "item":
        sk = chosen.get("item_key")
    elif st == "consumable":
        sk = chosen.get("consumable_key")
    else:
        sk = chosen.get("weapon_key")
    qmin = max(1, int(chosen.get("qty_min") or 1))
    qmax = max(qmin, int(chosen.get("qty_max") or qmin))
    qty = random.randint(qmin, qmax)
    return [{"source_type": st, "source_key": sk, "qty": qty}]


# Heuristic: player message may signal attack intent (Polish + common enemy words).
_COMBAT_VERB_HINT = re.compile(
    r"(atak|ataku|ciach|cios|tnę|doby|broń|miecz|topór|łuk|kusz|"
    r"noż|walcz|strzel|rzucam|pięści|bandyt|straż|goblin|ork|"
    r"przeciwn|wrog|zabij|zran|uderz|tnij|rani)",
    re.IGNORECASE,
)


def _inactive_combat_tag_reminder(user_text: str | None) -> str:
    """
    When no active combat in DB, the model often obeys FORMAT CUE (Roll …) instead of [COMBAT_START].
    Append a high-salience block so Phase 8 combat can start from GM text.
    """
    lines = (
        "[MECHANIKA — WALKA W SYSTEMIE: NIEAKTYWNA]\n"
        "W tej kampanii nie ma jeszcze aktywnej walki w silniku. Gdy w TEJ odpowiedzi dochodzi do pierwszego starcia "
        "(wrogowie atakują, leci pocisk, bójka, gracz dobiera broń by uderzyć lub strzelić w cel), "
        "OSTATNIA linia całej odpowiedzi MUSI być wyłącznie tagiem w osobnej linii: [COMBAT_START:klucz] "
        "(patrz INICJOWANIE WALKI, PRZYPADEK 2, sekcja HIERARCHIA).\n"
        "Zabronione jako ostatnia linia w tej sytuacji: jakakolwiek linia «Roll … d20» ze słownika — w tym Initiative i Attack."
    )
    if user_text and _COMBAT_VERB_HINT.search(user_text):
        lines += (
            "\n\n[TREŚĆ TURY GRACZA — możliwy atak]\n"
            "Wiadomość gracza sugeruje przemoc lub atak. Jeśli przechodzisz do walki, w TEJ odpowiedzi zakończ "
            "[COMBAT_START:…], a nie linią Roll ze słownika."
        )
    return lines


import re as _re_skill
_SKILL_VERB_HINT = _re_skill.compile(
    r"\b(próbuj|próbować|spróbuj|staram|chcę|zamiarzam|usiłuj|"
    r"skrad|przekrad|przekonaj|perswad|oszuk|zastraszy|przeszuk|spost|zauważ|"
    r"wytrop|przetrwaj|wylecz|zidentyfik|zbadaj|ident|użyj|kradnę|włamuj|wyważam|"
    r"skaczę|wspinaj|bieg|uciekam|uchylam|unikam|"
    r"kuj|wykuj|wykuć|oceniam|oszacuj|napraw|naprawiam|konstruuj|tworzę|robię|"
    r"rzemiosł|kowalstwo|alchemi|leczę|badan|tropię|ukryj|ukrywam|szpieg)\b",
    _re_skill.IGNORECASE,
)


_ARCANE_SKILL_KEYS = {"arcana", "spell_attack", "arcane_save"}


def _skill_test_tag_instruction(conn, campaign_id: int, user_text: str | None, character=None) -> str | None:
    """
    Inject skill test instructions when player text hints at a skill use.
    Loads skills from DB with descriptions so LLM picks the right custom key.

    Archetype gate: if character is not a Scholar, hides arcana/spell_attack/arcane_save
    from the skill list and appends an explicit rule forbidding magic tests.
    """
    if not user_text:
        return None
    if not _SKILL_VERB_HINT.search(user_text):
        return None

    # Detect archetype for arcane gate
    archetype = ""
    if character is not None:
        try:
            sheet = parse_character_sheet(character["sheet_json"])
            archetype = str(sheet.get("archetype") or "").strip().lower()
        except Exception:
            archetype = ""
    is_scholar = (archetype == "scholar")

    # Load skills from DB with descriptions — crucial so LLM knows WHEN to use custom skills
    skill_lines = []
    try:
        if conn:
            rows = conn.execute(
                "SELECT key, label, linked_stat, description FROM game_config_skills "
                "ORDER BY sort_order"
            ).fetchall()
            for r in rows:
                key = str(r["key"]).lower()
                # Filter out arcane skills for non-Scholars
                if not is_scholar and key in _ARCANE_SKILL_KEYS:
                    continue
                desc = str(r["description"] or "").strip()
                desc_part = f" — {desc[:60]}" if desc else ""
                skill_lines.append(f"  {r['key']} ({r['label']}, {r['linked_stat']}){desc_part}")
    except Exception:
        fallback = ["stealth", "lockpick", "perception", "persuasion", "athletics", "medicine", "lore"]
        if is_scholar:
            fallback.append("arcana")
        skill_lines = [f"  {', '.join(fallback)}"]

    skills_block = "\n".join(skill_lines)

    archetype_rule = ""
    if not is_scholar:
        archetype_rule = (
            "\n[ARCHETYP — BLOKADA MAGII]\n"
            f"Bohater jest {archetype.upper() or 'NON-SCHOLAR'} — NIE ma archetypu Uczonego (Scholar). "
            "NIGDY nie oferuj testów arcana / spell_attack / arcane_save. "
            "Jeśli gracz próbuje rzucić zaklęcie, odpowiedz NARRACYJNIE bez rzutu — "
            "jego krew nie nosi w sobie arkanów, słowa zaklęcia rozpadają się w gardle. "
            "Brak roll_cue, brak [SKILL_TEST:arcana:...] — tylko opis nieudanej próby.\n"
        )

    return (
        "[MECHANIKA — TESTY UMIEJĘTNOŚCI — WAŻNE]\n"
        "Wiadomość gracza wymaga testu umiejętności. Użyj pola roll_cue w JSON:\n"
        "  \"roll_cue\": \"Roll <klucz_umiejętności> d20\"\n\n"
        "ZASADA: używaj DOKŁADNIE tych kluczy (key) z listy poniżej. "
        "NIE używaj angielskich odpowiedników z D&D (np. 'Investigation', 'Athletics' itp.) "
        "— użyj polskiego klucza z listy.\n\n"
        "DOSTĘPNE UMIEJĘTNOŚCI:\n"
        f"{skills_block}\n"
        f"{archetype_rule}\n"
        "Przykłady:\n"
        "  \"roll_cue\": \"Roll stealth d20\"       ← skradanie\n"
        "  \"roll_cue\": \"Roll kowalstwo d20\"     ← ocena/naprawa broni, wykuwanie\n"
        "  \"roll_cue\": \"Roll persuasion d20\"    ← przekonywanie NPC\n"
        "  \"roll_cue\": \"Roll perception d20\"    ← spostrzeżenie czegoś\n\n"
        "Nie opisuj wyniku rzutu w narracji — gracz sam rzuci kością."
    )


def _death_mechanica_system_append(
    character: sqlite3.Row | None, roll_result_data: dict | None
) -> str | None:
    """
    While the character has 1–2 death save failures, force the GM to end each non-roll
    narrative with 'Roll Death Save d20'. Skip when this turn is a death save resolution.
    """
    if not character:
        return None
    sheet = parse_character_sheet(character["sheet_json"])
    failures = int(sheet.get("death_save_failures") or 0)
    if failures < 1 or failures >= DEATH_SAVE_FAILURE_THRESHOLD:
        return None
    if roll_result_data and roll_result_data.get("test") == "death_save":
        return None
    return (
        "[MECHANIKA — STAN ŚMIERCI]\n"
        "Postać jest nieprzytomna i walczy o życie.\n"
        f"Liczba nieudanych rzutów śmierci: {failures} / {DEATH_SAVE_FAILURE_THRESHOLD}\n"
        "Zasada: na końcu KAŻDEJ tury (nie rzutu) musisz dodać dokładnie tę linię jako ostatnią:\n"
        "Roll Death Save d20\n"
        "Nie narruj wyzdrowienia. Nie kończ stanu śmierci fabularnie. Tylko rzut może zmienić ten stan."
    )


def _inject_hex_terrain_context(
    conn: sqlite3.Connection, campaign_id: int, messages: list[dict]
) -> None:
    """Append [HEX CONTEXT] to system prompt so GM knows current terrain type and atmosphere."""
    if not messages:
        return
    first = messages[0]
    if not isinstance(first, dict) or first.get("role") != "system":
        return
    try:
        gs = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not gs:
            return
        flags = json.loads(gs["session_flags"] or "{}")
        ch = flags.get("current_hex")
        if not ch:
            return
        q, r = int(ch["q"]), int(ch["r"])
        hex_row = conn.execute(
            "SELECT hex_type, label, atmosphere FROM world_hexes WHERE q = ? AND r = ? AND is_active = 1",
            (q, r),
        ).fetchone()
        if not hex_row:
            return
        hex_type = hex_row["hex_type"] or "plains"
        cfg_row = conn.execute(
            "SELECT label, map_icon FROM hex_type_config WHERE hex_type = ?",
            (hex_type,),
        ).fetchone()
        terrain_label = cfg_row["label"] if cfg_row else hex_type
        terrain_icon = (cfg_row["map_icon"] or "") if cfg_row else ""
        hex_label = hex_row["label"] or ""
        atmosphere = hex_row["atmosphere"] or ""

        parts = [
            f"[HEX CONTEXT]",
            f"terrain_type: {hex_type}  # {terrain_icon} {terrain_label}",
        ]
        if hex_label:
            parts.append(f"hex_label: {hex_label}")
        if atmosphere:
            parts.append(f"atmosphere: {atmosphere}")
        parts.append(
            "Narruj opisy otoczenia, pogodę, napotkane stworzenia i nastrój "
            "zgodnie z powyższym typem terenu."
        )
        block = "\n".join(parts)
        first["content"] = f"{first['content'].rstrip()}\n\n{block}"
    except Exception as exc:
        logger.warning("hex_terrain_context_injection_failed", error=str(exc))


def _inject_character_inventory_context(
    conn: sqlite3.Connection, character: sqlite3.Row | None, messages: list[dict]
) -> None:
    """Append [PLAYER INVENTORY] to system prompt — anti-hallucination for item/weapon ownership."""
    if not character or not messages:
        return
    first = messages[0]
    if not isinstance(first, dict) or first.get("role") != "system":
        return
    try:
        cid = int(character["id"])
        rows = conn.execute(
            """
            SELECT ci.item_key, ci.weapon_key, ci.consumable_key,
                   ci.label, ci.quantity, ci.equipped, ci.slot,
                   COALESCE(w.label, it.label, cons.label) AS catalog_label
            FROM character_inventory ci
            LEFT JOIN game_config_weapons   w    ON w.key    = ci.weapon_key
            LEFT JOIN game_config_items     it   ON it.key   = ci.item_key
            LEFT JOIN game_config_consumables cons ON cons.key = ci.consumable_key
            WHERE ci.character_id = ?
            ORDER BY ci.equipped DESC, ci.slot, catalog_label
            """,
            (cid,),
        ).fetchall()

        if not rows:
            return

        equipped_lines = []
        carried_lines = []
        for r in rows:
            name = r["label"] or r["catalog_label"] or r["weapon_key"] or r["item_key"] or r["consumable_key"] or "?"
            qty = int(r["quantity"] or 1)
            qty_str = f" ×{qty}" if qty > 1 else ""
            if r["equipped"]:
                slot = r["slot"] or "equipped"
                equipped_lines.append(f"  {slot}: {name}")
            else:
                carried_lines.append(f"  - {name}{qty_str}")

        parts = ["[PLAYER INVENTORY]"]
        if equipped_lines:
            parts.append("Equipped:")
            parts.extend(equipped_lines)
        if carried_lines:
            parts.append("Carried:")
            parts.extend(carried_lines)
        parts.append(
            "ZASADA: Nigdy nie opisuj gracza używającego broni ani przedmiotu "
            "który NIE jest na powyższej liście. Nie zakładaj posiadania miecza, "
            "tarczy, pochodni ani żadnego innego ekwipunku spoza tej listy."
        )
        block = "\n".join(parts)
        first["content"] = f"{first['content'].rstrip()}\n\n{block}"
    except Exception as exc:
        logger.warning("inventory_context_injection_failed", error=str(exc))


def _build_active_encounter_block(conn: sqlite3.Connection, campaign_id: int) -> str:
    """Return a formatted encounter block if admin injected one, else ''."""
    import json as _json
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not row:
            return ""
        flags = _json.loads(row[0] or "{}")
        enc = flags.get("active_encounter")
        if not enc or not isinstance(enc, dict):
            return ""
        enemies_lines = ""
        first_enemy_key = ""
        all_enemy_keys: list[str] = []
        for e in (enc.get("enemies") or []):
            enemy_key = e.get("enemy_key") or ""
            if enemy_key:
                if not first_enemy_key:
                    first_enemy_key = enemy_key
                all_enemy_keys.append(enemy_key)
            key_note = f" [DB: {enemy_key}]" if enemy_key else ""
            enemies_lines += f"  - {e.get('name','?')} ×{e.get('count',1)}{key_note}"
            if e.get("notes"):
                enemies_lines += f" — {e['notes']}"
            enemies_lines += "\n"
        objectives = "\n".join(f"  {i+1}. {o}" for i, o in enumerate(enc.get("objectives") or []))
        rew = enc.get("rewards") or {}
        combat_tag_keys = ",".join(all_enemy_keys) if all_enemy_keys else "unknown_attacker"
        return (
            "=== AKTYWNE SPOTKANIE (UŻYJ W TEJ TURZE) ===\n"
            f"Tytuł: {enc.get('title','')}\n"
            f"Wyzwalacz: {enc.get('trigger_condition','')}\n"
            f"Scena: {enc.get('scene_setup','')}\n"
            f"Wrogowie:\n{enemies_lines}"
            f"Cele:\n{objectives}\n"
            f"Nagrody: {rew.get('xp_estimate',0)} XP — {rew.get('loot_notes','')}\n"
            f"Uwagi GM: {enc.get('gm_notes','')}\n"
            "Poprowadź tę scenę naturalnie — włącz wyzwalacz do narracji i pozwól graczowi zareagować.\n"
            f"Gdy gracz zaatakuje lub wywoła walkę, zakończ narrację tagiem: [COMBAT_START:{combat_tag_keys}]"
        )
    except Exception as _exc:
        logger.warning("active_encounter_block_failed", error=str(_exc))
        return ""


def _clear_active_encounter(conn: sqlite3.Connection, campaign_id: int) -> None:
    """Remove active_encounter from session_flags after it fires."""
    import json as _json
    try:
        row = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not row:
            return
        flags = _json.loads(row[0] or "{}")
        if "active_encounter" not in flags:
            return
        flags.pop("active_encounter")
        conn.execute(
            "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
            (_json.dumps(flags, ensure_ascii=False), campaign_id),
        )
        conn.commit()
    except Exception as _exc:
        logger.warning("clear_active_encounter_failed", error=str(_exc))


def _inject_dungeon_tile_context(
    conn: sqlite3.Connection, campaign_id: int, messages: list[dict]
) -> bool:
    """Inject current tile + category context when player is in a tile dungeon.
    Returns True if injected (caller should skip location context)."""
    import json as _j
    try:
        gs = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,)
        ).fetchone()
        if not gs:
            return False
        flags = _j.loads(gs[0] or "{}")
        run = flags.get("dungeon_run")
        if not run or run.get("system") != "tiles":
            return False

        tiles = run.get("tiles", [])
        current_index = run.get("current_index", 0)
        if not tiles:
            return False
        current_tile = tiles[min(current_index, len(tiles) - 1)]
        category_key = run.get("category_key", "dungeon")

        cat = conn.execute(
            "SELECT label, system_prompt FROM dungeon_tile_categories WHERE key = ?",
            (category_key,)
        ).fetchone()
        category_label = cat[0] if cat else category_key
        category_prompt = (cat[1] if cat else "") or ""

        tile_label = current_tile.get("label", "Komnata")
        tile_desc = current_tile.get("room_description", "")
        tile_idx = current_index + 1
        tile_total = len(tiles)
        is_boss = current_tile.get("is_boss_tile", False)
        is_cleared = current_tile.get("cleared", False)
        enemies = current_tile.get("enemies", [])
        dungeon_label = run.get("dungeon_label", category_label)

        lines = [f"[DUNGEON TILE CONTEXT — {category_label.upper()}]"]
        if category_prompt:
            lines.append(f"\n{category_prompt.strip()}\n")
        lines.append(f"Loch: {dungeon_label}")
        lines.append(f"Komnata {tile_idx}/{tile_total}: {tile_label}{'  ⚠ BOSS' if is_boss else ''}")
        if tile_desc:
            lines.append(f"Opis: {tile_desc}")
        if enemies and not is_cleared:
            names = [e.get("label", e.get("key", "?")) for e in enemies[:3]]
            lines.append(f"Wrogowie w komnacie: {', '.join(names)}")
        if is_cleared:
            lines.append("Status: komnata oczyszczona.")
        lines.append(
            "\n[INSTRUKCJA NARRACJI] Gracz JEST TERAZ w tym lochu. "
            "Opisuj komnatę zgodnie z powyższym opisem. "
            "Nie odwołuj się do poprzedniej lokacji ani kampanii fabularnej. "
            "Narracja powinna odzwierciedlać atmosferę lochu."
        )

        if messages:
            messages.insert(1, {"role": "system", "content": "\n".join(lines)})
        logger.info("dungeon_tile_context_injected", campaign_id=campaign_id,
                    tile=tile_label, index=tile_idx)
        return True
    except Exception as exc:
        logger.warning("dungeon_tile_context_failed", error=str(exc))
        return False


def _inject_location_llm_context(
    conn: sqlite3.Connection, campaign_id: int, messages: list[dict]
) -> None:
    """8D-LOC-1: blok [LOCATION CONTEXT] jako druga wiadomość systemowa (po głównym system prompt)."""
    from app.services.location_config_service import get_bool_flag
    from app.services.location_context_injector import (
        build_location_context_block,
        get_session_id_for_campaign,
    )

    if not messages:
        return

    sid = get_session_id_for_campaign(conn, campaign_id)
    if sid is None:
        logger.info("location_context_skipped", session_id=None, reason="no_session")
        return
    if not get_bool_flag("location_integrity_enabled", sid, default=True):
        logger.info(
            "location_context_skipped", session_id=str(sid), reason="flag_disabled"
        )
        return

    try:
        loc_block = build_location_context_block(sid, conn)
        if loc_block:
            known_count = sum(
                1 for ln in loc_block.splitlines() if ln.startswith("  - { ")
            )
            messages.insert(1, {"role": "system", "content": loc_block})
            logger.info(
                "location_context_injected",
                session_id=str(sid),
                known_count=known_count,
            )
        else:
            logger.info(
                "location_context_skipped",
                session_id=str(sid),
                reason="no_current_location",
            )
    except Exception as exc:
        logger.warning(
            "location_context_injection_failed",
            session_id=str(sid),
            error=str(exc),
        )


def build_npc_context_block(conn: sqlite3.Connection, campaign_id: int) -> str | None:
    """
    Build [NPC CONTEXT] block for LLM:
    - location-assigned NPC for current location
    - global NPC (no rows in npc_locations)
    """
    from app.services.location_context_injector import get_session_id_for_campaign

    sid = get_session_id_for_campaign(conn, campaign_id)
    current_key: str | None = None
    if sid is not None:
        row = conn.execute(
            """
            SELECT gl.key
            FROM game_sessions gs
            LEFT JOIN game_locations gl ON gl.id = gs.current_location_id
            WHERE gs.id = ?
            """,
            (str(sid),),
        ).fetchone()
        if row and row["key"]:
            current_key = str(row["key"])

    if current_key:
        rows = conn.execute(
            """
            SELECT DISTINCT n.key, n.label, n.npc_type, n.description, n.personality_json
            FROM npcs n
            WHERE COALESCE(n.is_active, 1) = 1
              AND (
                EXISTS (
                    SELECT 1 FROM npc_locations nl
                    WHERE nl.npc_id = n.id AND nl.location_key = ?
                )
                OR NOT EXISTS (
                    SELECT 1 FROM npc_locations nl2 WHERE nl2.npc_id = n.id
                )
              )
            ORDER BY n.npc_type, n.label COLLATE NOCASE
            """,
            (current_key,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT n.key, n.label, n.npc_type, n.description, n.personality_json
            FROM npcs n
            WHERE COALESCE(n.is_active, 1) = 1
              AND NOT EXISTS (
                SELECT 1 FROM npc_locations nl WHERE nl.npc_id = n.id
              )
            ORDER BY n.npc_type, n.label COLLATE NOCASE
            """
        ).fetchall()

    if not rows:
        return None

    lines = ["[NPC CONTEXT]"]
    if current_key:
        lines.append(f'current_location_key: {json.dumps(current_key)}')
    else:
        lines.append("current_location_key: null")
    lines.append("npcs_in_scene:")

    for row in rows:
        personality = ""
        topics = ""
        secret = ""
        try:
            p = json.loads(row["personality_json"] or "{}")
            if isinstance(p, dict):
                personality = str(p.get("personality") or "").strip()
                tv = p.get("topics")
                if isinstance(tv, list):
                    topics = ", ".join(str(x).strip() for x in tv if str(x).strip())
                secret = str(p.get("secret") or "").strip()
        except Exception:
            personality = ""
            topics = ""
            secret = ""

        line = (
            f'- {row["label"]} ({row["npc_type"]})'
            f' [key={row["key"]}]'
        )
        if row["description"]:
            line += f": {row['description']}"
        if personality:
            line += f" | personality: {personality}"
        if topics:
            line += f" | topics: {topics}"
        if secret:
            line += f" | secret: {secret}"
        lines.append(line)
    return "\n".join(lines)


def _inject_npc_llm_context(
    conn: sqlite3.Connection, campaign_id: int, messages: list[dict]
) -> None:
    """9A-3: inject dynamic [NPC CONTEXT] as a system message."""
    if not messages:
        return
    try:
        npc_block = build_npc_context_block(conn, campaign_id)
        if not npc_block:
            logger.info("npc_context_skipped", campaign_id=campaign_id, reason="no_npcs")
            return
        insert_at = 2 if len(messages) > 1 and messages[1].get("role") == "system" else 1
        messages.insert(insert_at, {"role": "system", "content": npc_block})
        visible_count = sum(1 for ln in npc_block.splitlines() if ln.startswith("- "))
        logger.info("npc_context_injected", campaign_id=campaign_id, npc_count=visible_count)
    except sqlite3.OperationalError as exc:
        # 9A-3 should fail-open before 9A-1 migrations are applied.
        logger.info("npc_context_skipped", campaign_id=campaign_id, reason="schema_missing", error=str(exc))
    except Exception as exc:
        logger.warning("npc_context_injection_failed", campaign_id=campaign_id, error=str(exc))


def _inject_campaign_s11_context(
    conn: sqlite3.Connection,
    campaign: sqlite3.Row,
    messages: list[dict],
    *,
    current_user_text: str | None = None,
) -> None:
    """
    Append MG plan + latest AI summary to system prompt so LLM keeps arc beyond last N turns.
    """
    if not messages:
        return
    first = messages[0]
    if not isinstance(first, dict) or first.get("role") != "system":
        return

    cid = int(campaign["id"])
    keys = campaign.keys()
    raw_plan = campaign["gm_plan_json"] if "gm_plan_json" in keys else None

    block_parts: list[str] = []
    formatted = format_gm_plan_block(raw_plan)
    if formatted:
        block_parts.append(formatted)

    try:
        from app.services.history_summary_service import fetch_latest_saved_summary_for_narrative

        saved = fetch_latest_saved_summary_for_narrative(conn, cid)
    except sqlite3.OperationalError:
        saved = None

    if saved and (saved.get("summary_text") or "").strip():
        st = str(saved["summary_text"]).strip()
        tc = saved.get("included_turn_count")
        block_parts.append(
            f"## Dotychczasowa fabuła (skrót archiwalny, ~{tc} tur narracyjnych)\n{st}"
        )

    try:
        from app.services.gm_plan_divergence import (
            divergence_prompt_block,
            evaluate_campaign_plan_divergence,
        )

        divergence = evaluate_campaign_plan_divergence(
            conn,
            campaign_id=cid,
            raw_plan=raw_plan,
            current_user_text=current_user_text,
            limit=4,
        )
        divergence_block = divergence_prompt_block(divergence)
        if divergence_block:
            block_parts.append(divergence_block)
    except sqlite3.OperationalError:
        pass

    if not block_parts:
        return

    bundle = (
        "--- Kontekst kampanii (trzymaj spójność z planem i skrótem; improwizuj w ramach zasad silnika) ---\n\n"
        + "\n\n".join(block_parts)
    )
    first["content"] = f"{first.get('content', '').rstrip()}\n\n{bundle}"


def build_narrative_messages(
    conn: sqlite3.Connection | None,
    campaign: sqlite3.Row,
    character: sqlite3.Row | None,
    user_text: str,
    roll_result_message: str | None = None,
    roll_result_data: dict | None = None,
) -> list[dict]:
    from app.services import combat_service as combat_svc

    has_db_conn = isinstance(conn, sqlite3.Connection)
    recent_turns = loadrecentturns(conn, campaign["id"], limit=8)
    final_user_text = roll_result_message if roll_result_message else user_text
    combat_block = combat_svc.get_combat_context_for_prompt(int(campaign["id"]))
    messages = buildmessages(
        campaign=campaign,
        character=character,
        recentturns=recent_turns,
        usertext=final_user_text,
        runtime_config_block=build_runtime_config_block(),
        combat_context_block=combat_block,
    )

    if has_db_conn:
        _inject_campaign_s11_context(conn, campaign, messages, current_user_text=user_text)
        in_tile_dungeon = _inject_dungeon_tile_context(conn, int(campaign["id"]), messages)
        if not in_tile_dungeon:
            _inject_location_llm_context(conn, int(campaign["id"]), messages)
        _inject_npc_llm_context(conn, int(campaign["id"]), messages)
        _inject_hex_terrain_context(conn, int(campaign["id"]), messages)
        _inject_character_inventory_context(conn, character, messages)

    combat_log_block = combat_svc.get_combat_turns_context_for_prompt(int(campaign["id"]))
    if combat_log_block and messages:
        first = messages[0]
        if isinstance(first, dict) and first.get("role") == "system":
            first["content"] = f"{first.get('content', '').rstrip()}\n\n{combat_log_block}"

    death_append = _death_mechanica_system_append(character, roll_result_data)

    if (
        not combat_block
        and not roll_result_message
        and not death_append
        and messages
    ):
        first = messages[0]
        if isinstance(first, dict) and first.get("role") == "system":
            extra = _inactive_combat_tag_reminder(user_text)
            snap = combat_svc.load_combat_snapshot(int(campaign["id"]))
            if snap and str(snap.get("status") or "") == "ended":
                er = snap.get("ended_reason") or "ended"
                extra += (
                    "\n\n[STAN SILNIKA WALKI — POPRZEDNIA SESJA ZAKOŃCZONA]\n"
                    f"W bazie jest zapis zakończonej walki (powód: {er}). Gracz NIE ma teraz aktywnej walki "
                    "w mechanice — każda **nowa** potyczka wymaga na końcu Twojej odpowiedzi linii "
                    "[COMBAT_START:klucz_wroga] (wg słownika wrogów), chyba że gracz sam uruchomi walkę "
                    "komendą /atak w czacie (odczyt stanu walki).\n"
                    "Nie kontynuuj w myśleniu starej sesji (inicjatywa, HP z poprzedniej walki) — to osobna walka."
                )
            first["content"] = f"{first.get('content', '').rstrip()}\n\n{extra}"

    if has_db_conn and not combat_block and messages:
        first = messages[0]
        if isinstance(first, dict) and first.get("role") == "system":
            enemy_catalog = combat_svc.get_enemy_catalog_for_prompt(conn)
            if enemy_catalog:
                first["content"] = f"{first.get('content', '').rstrip()}\n\n{enemy_catalog}"

    # 8H-4: item catalog — także podczas aktywnej walki (Grant Item / nagrody z katalogu)
    if has_db_conn and messages:
        first = messages[0]
        if isinstance(first, dict) and first.get("role") == "system":
            item_catalog = combat_svc.get_item_catalog_for_prompt(conn)
            if item_catalog:
                first["content"] = f"{first.get('content', '').rstrip()}\n\n{item_catalog}"

    if death_append and messages:
        first = messages[0]
        if isinstance(first, dict) and first.get("role") == "system":
            first["content"] = f"{first.get('content', '').rstrip()}\n\n{death_append}"

    # active_encounter injection — GM-injected one-shot encounter scene
    if has_db_conn and not roll_result_message and messages:
        _enc_block = _build_active_encounter_block(conn, int(campaign["id"]))
        if _enc_block:
            first = messages[0]
            if isinstance(first, dict) and first.get("role") == "system":
                first["content"] = f"{first.get('content', '').rstrip()}\n\n{_enc_block}"

    # Skill test tag instruction — injected when player text hints at skill use
    if not combat_block and not roll_result_message and has_db_conn and messages:
        _st_block = _skill_test_tag_instruction(conn, int(campaign["id"]), user_text, character=character)
        if _st_block:
            messages.append({"role": "system", "content": _st_block})

    if not roll_result_data or not messages:
        return messages

    _rt = roll_result_data.get("roll_type") or infer_roll_type(
        str(roll_result_data.get("test") or "")
    )
    _atk = _rt == "attack"
    if roll_result_data.get("is_nat20") and _atk:
        roll_context = (
            "ROLL RESULT: CRITICAL SUCCESS (Natural 20). "
            "Narrate a dramatic, exceptional success. "
            "If combat: double damage dice."
        )
    elif roll_result_data.get("is_nat1") and _atk:
        roll_context = (
            "ROLL RESULT: CRITICAL FAILURE (Natural 1). "
            "Narrate a failure with an unexpected complication or twist. "
            "Do not just say the player failed — add a narrative consequence."
        )
    else:
        weapon_bonus = int(roll_result_data.get("weapon_bonus") or 0)
        bonus_part = ""
        if weapon_bonus:
            bonus_part = f" + weapon: {weapon_bonus}"
        roll_context = (
            "ROLL RESULT: "
            f"{roll_result_data.get('test')} check — rolled {roll_result_data.get('total')} "
            f"(d20: {roll_result_data.get('raw')} + stat: {roll_result_data.get('stat_mod')} + "
            f"skill: {roll_result_data.get('skill_rank')} + proficiency: {roll_result_data.get('proficiency')}"
            f"{bonus_part})"
        )

    if roll_result_data.get("test") == "death_save":
        total_ds = int(roll_result_data.get("total") or 0)
        if total_ds >= 10 or roll_result_data.get("is_nat20"):
            roll_context += (
                "\n\n[USTABILIZOWANIE] Postać ustabilizowała się. Stan śmierci zakończony (mechanicznie: "
                "death_save_failures = 0). Zakończ ten stan w narracji; nie dodawaj na końcu linii "
                "\"Roll Death Save d20\"."
            )

    first = messages[0]
    if isinstance(first, dict) and first.get("role") == "system":
        first["content"] = f"{first.get('content', '').rstrip()}\n\n{roll_context}"
    return messages


def run_narrative_turn(
    conn: sqlite3.Connection,
    campaign: sqlite3.Row,
    character: sqlite3.Row | None,
    user_text: str,
    model: str,
    ollama_base_url: str | None = None,
    llm_config: dict[str, str] | None = None,
    roll_result_message: str | None = None,
    roll_result_data: dict | None = None,
) -> dict:
    messages = build_narrative_messages(
        conn=conn,
        campaign=campaign,
        character=character,
        user_text=user_text,
        roll_result_message=roll_result_message,
        roll_result_data=roll_result_data,
    )
    reply = generate_chat(messages=messages, model=model, llm_config=llm_config)
    _clear_active_encounter(conn, int(campaign["id"]))
    return {"message": reply}
