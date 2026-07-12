"""#1336 BL-C1 — rzemiosło core (light).

Bohater dostarcza komponenty, rzemieślnik NPC (kowal/zielarz) wykonuje przepis
za opłatą. Zero drzewek rozwoju — celowo płytkie (#1199).

Publiczne API:
  • get_location_crafting(loc_ref) -> dict   — przepisy dostępne u lokalnych rzemieślników
  • craft(character_id, recipe_key, ...) -> dict — walidacja → konsumpcja → wynik

Wynik (output_type):
  • consumable     → mikstura/przedmiot do character_inventory
  • weapon_upgrade → afiks 'craft_hone' (+1 dmg) na egzemplarzu broni, NIE kumuluje się
  • armor_repair   → odnowienie durability wyposażonego pancerza (fallback: tag meta)

Zniżka rasowa krasnoluda ("kowalskie oko" #969/#973) obniża koszt USŁUGI craftu,
reużywa stałej DWARF_SHOP_DISCOUNT z shop_service.
"""

from __future__ import annotations

import json
import random
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.migrations_admin import DB_PATH
from app.services.shop_service import DWARF_SHOP_DISCOUNT

# Afiks nadawany przez ulepszenie broni (musi istnieć w game_config_affixes; seedowany
# w migracji _ensure_recipes_schema). Silnik walki sumuje jego damage_bonus.
WEAPON_HONE_AFFIX = "craft_hone"

# ── #1341 BL-D2 — eksperymenty: liczby startowe (Numbers Policy, sandbox-tunable) ──
# Opłata za jedną próbę eksperymentu (materiały tygla + czas rzemieślnika).
EXPERIMENT_COST_GOLD = 10
# DC testu trade_craft wg tieru ukrytej receptury (locked skala DC gry).
EXPERIMENT_TIER_DC = {"easy": 8, "medium": 12, "hard": 16}
# Ile komponentów (distinct) wolno wskazać w jednej próbie.
EXPERIMENT_MIN_COMPONENTS = 2
EXPERIMENT_MAX_COMPONENTS = 4
# Tabela fuszerek (pudło = kombinacja spoza puli ukrytych receptur, lub Nat 1 na
# trafionej recepturze). Wagi = szansa (%). Wynik NIGDY nie daje itemu z receptury.
FUMBLE_TABLE = [
    ("loss", 40),     # komponenty przepadają — nic w zamian
    ("slag", 30),     # bezwartościowy stop — komponenty przepadają
    ("damage", 25),   # wybuch tygla: 1d4 obrażeń + strata komponentów
    ("cursed", 5),    # (rzadko) przeklęty stop z wadą trafia do ekwipunku fabularnego
]


class CraftError(Exception):
    """Błąd craftu z kodem HTTP (400/403/404) — mapowany na HTTPException w routerze."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _load_recipe(conn: sqlite3.Connection, recipe_key: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM game_config_recipes WHERE key = ? AND is_active = 1 LIMIT 1",
        (str(recipe_key).strip(),),
    ).fetchone()
    if not row:
        raise CraftError(404, f"Przepis '{recipe_key}' nie istnieje.")
    # is_hidden — przepisy legendarne (BL-D2), niedostępne do craftu w tej fazie.
    if int(row["is_hidden"] or 0) == 1:
        raise CraftError(404, f"Przepis '{recipe_key}' nie jest dostępny.")
    return row


def _parse_inputs(recipe: sqlite3.Row) -> list[dict]:
    try:
        raw = json.loads(recipe["inputs_json"] or "[]")
    except (json.JSONDecodeError, TypeError):
        raw = []
    out = []
    for e in raw if isinstance(raw, list) else []:
        if not isinstance(e, dict):
            continue
        key = str(e.get("item_key") or "").strip()
        qty = int(e.get("qty") or e.get("quantity") or 1)
        if key and qty > 0:
            out.append({"item_key": key, "qty": qty})
    return out


def _owned_component_qty(conn: sqlite3.Connection, character_id: int, item_key: str) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(quantity), 0) AS n
        FROM character_inventory
        WHERE character_id = ? AND item_key = ?
        """,
        (int(character_id), item_key),
    ).fetchone()
    return int(row["n"] or 0)


def _consume_component(conn: sqlite3.Connection, character_id: int, item_key: str, qty: int) -> None:
    """Zdejmij `qty` sztuk komponentu z ekwipunku (po wierszach FIFO, kasując puste)."""
    need = int(qty)
    rows = conn.execute(
        """
        SELECT id, quantity FROM character_inventory
        WHERE character_id = ? AND item_key = ?
        ORDER BY id ASC
        """,
        (int(character_id), item_key),
    ).fetchall()
    for r in rows:
        if need <= 0:
            break
        have = int(r["quantity"] or 0)
        take = min(have, need)
        remaining = have - take
        if remaining > 0:
            conn.execute(
                "UPDATE character_inventory SET quantity = ? WHERE id = ?",
                (remaining, r["id"]),
            )
        else:
            conn.execute("DELETE FROM character_inventory WHERE id = ?", (r["id"],))
        need -= take
    if need > 0:
        # Nie powinno się zdarzyć — walidacja idzie przed konsumpcją.
        raise CraftError(400, f"Brak komponentu '{item_key}'.")


def _get_character(conn: sqlite3.Connection, character_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT id, race, gold_gp FROM characters WHERE id = ? LIMIT 1",
        (int(character_id),),
    ).fetchone()
    if not row:
        raise CraftError(404, "Nie znaleziono bohatera.")
    return row


def _service_cost(recipe: sqlite3.Row, race: str) -> int:
    """Koszt usługi po zniżce rasowej krasnoluda (kowalskie oko)."""
    base = int(recipe["service_cost_gold"] or 0)
    if base <= 0:
        return 0
    if str(race or "").strip().lower() == "dwarf":
        base = int(round(base * (1.0 - DWARF_SHOP_DISCOUNT)))
    return max(0, base)


def _pick_upgrade_weapon(
    conn: sqlite3.Connection, character_id: int, target_inventory_id: int | None
) -> sqlite3.Row:
    """Wybierz egzemplarz broni do ulepszenia: jawny target → wyposażona główna ręka → pierwsza."""
    if target_inventory_id is not None:
        row = conn.execute(
            """
            SELECT id, weapon_key, affixes_json FROM character_inventory
            WHERE id = ? AND character_id = ? AND weapon_key IS NOT NULL LIMIT 1
            """,
            (int(target_inventory_id), int(character_id)),
        ).fetchone()
        if not row:
            raise CraftError(400, "Wskazany przedmiot nie jest bronią tego bohatera.")
        return row
    row = conn.execute(
        """
        SELECT id, weapon_key, affixes_json FROM character_inventory
        WHERE character_id = ? AND weapon_key IS NOT NULL
        ORDER BY (COALESCE(equipped,0) = 1
                  AND LOWER(TRIM(COALESCE(slot,''))) = 'main_hand') DESC, id ASC
        LIMIT 1
        """,
        (int(character_id),),
    ).fetchone()
    if not row:
        raise CraftError(400, "Brak broni do ulepszenia w ekwipunku.")
    return row


def _affix_keys(row: sqlite3.Row) -> list[str]:
    raw = row["affixes_json"] if "affixes_json" in row.keys() else None
    try:
        keys = json.loads(raw) if isinstance(raw, str) and raw.strip() else (raw or [])
    except (json.JSONDecodeError, TypeError):
        keys = []
    return [str(k).strip() for k in keys if str(k or "").strip()]


# ── Publiczne API ────────────────────────────────────────────────────────────

def get_location_crafting(loc_ref: str | int) -> dict:
    """Przepisy dostępne u rzemieślników w danej lokacji.

    loc_ref: klucz LUB numeryczne id lokacji. Zbiera crafter_type wszystkich
    NPC-rzemieślników przypisanych do lokacji (npc_keys + npc_locations +
    location_npc_assignments), zwraca przepisy pasujących typów (is_hidden=0).
    """
    conn = _conn()
    try:
        ref = str(loc_ref).strip()
        loc = conn.execute(
            "SELECT id, key, label, npc_keys FROM game_locations WHERE key = ? LIMIT 1",
            (ref,),
        ).fetchone()
        if not loc and ref.isdigit():
            loc = conn.execute(
                "SELECT id, key, label, npc_keys FROM game_locations WHERE id = ? LIMIT 1",
                (int(ref),),
            ).fetchone()
        if not loc:
            raise CraftError(404, f"Lokalizacja '{loc_ref}' nie istnieje.")

        loc_key = loc["key"]
        # Klucze NPC z trzech źródeł przypisania.
        npc_keys: set[str] = set()
        try:
            for k in json.loads(loc["npc_keys"] or "[]"):
                if str(k or "").strip():
                    npc_keys.add(str(k).strip())
        except (json.JSONDecodeError, TypeError):
            pass
        for tbl, col in (("location_npc_assignments", "npc_key"),):
            try:
                for r in conn.execute(
                    f"SELECT {col} AS k FROM {tbl} WHERE location_key = ? AND is_active = 1",
                    (loc_key,),
                ).fetchall():
                    if str(r["k"] or "").strip():
                        npc_keys.add(str(r["k"]).strip())
            except sqlite3.OperationalError:
                pass
        try:
            for r in conn.execute(
                """
                SELECT n.key AS k FROM npc_locations nl
                JOIN npcs n ON n.id = nl.npc_id
                WHERE nl.location_key = ?
                """,
                (loc_key,),
            ).fetchall():
                if str(r["k"] or "").strip():
                    npc_keys.add(str(r["k"]).strip())
        except sqlite3.OperationalError:
            pass

        # crafter_type z tych NPC.
        crafter_types: set[str] = set()
        if npc_keys:
            ph = ",".join("?" for _ in npc_keys)
            try:
                for r in conn.execute(
                    f"SELECT DISTINCT crafter_type FROM npcs "
                    f"WHERE key IN ({ph}) AND crafter_type IS NOT NULL AND is_active = 1",
                    tuple(npc_keys),
                ).fetchall():
                    if str(r["crafter_type"] or "").strip():
                        crafter_types.add(str(r["crafter_type"]).strip())
            except sqlite3.OperationalError:
                pass

        recipes: list[dict] = []
        if crafter_types:
            ph = ",".join("?" for _ in crafter_types)
            for r in conn.execute(
                f"""
                SELECT key, label, inputs_json, output_type, output_key, output_qty,
                       service_cost_gold, crafter_type
                FROM game_config_recipes
                WHERE is_active = 1 AND is_hidden = 0 AND crafter_type IN ({ph})
                ORDER BY crafter_type, key
                """,
                tuple(crafter_types),
            ).fetchall():
                d = dict(r)
                try:
                    d["inputs"] = json.loads(d.pop("inputs_json") or "[]")
                except (json.JSONDecodeError, TypeError):
                    d["inputs"] = []
                recipes.append(d)

        return {
            "location_key": loc_key,
            "location_label": loc["label"],
            "crafters": sorted(crafter_types),
            "recipes": recipes,
        }
    finally:
        conn.close()


def location_has_crafting(loc_ref: str | int) -> bool:
    """True gdy w lokacji jest rzemieślnik z ≥1 dostępnym (jawnym) przepisem.

    Używane przez suggested_actions do wystawienia chipu „Rzemiosło" (#1338 BL-C3),
    analogicznie do „Usługi". Nieistniejąca lokacja / brak crafterów → False.
    """
    try:
        data = get_location_crafting(loc_ref)
    except CraftError:
        return False
    return bool(data.get("recipes"))


def craft(
    character_id: int,
    recipe_key: str,
    target_inventory_id: int | None = None,
) -> dict:
    """Wykonaj przepis: waliduj komponenty+złoto → konsumuj → wytwórz wynik.

    Rzuca CraftError(400) przy braku komponentów/złota lub gdy ulepszenie broni
    już nałożone (nie kumuluje się).
    """
    conn = _conn()
    try:
        recipe = _load_recipe(conn, recipe_key)
        char = _get_character(conn, character_id)
        race = str(char["race"] or "human").strip().lower()
        inputs = _parse_inputs(recipe)

        # 1) Walidacja komponentów (przed jakąkolwiek mutacją).
        missing: list[str] = []
        for inp in inputs:
            have = _owned_component_qty(conn, character_id, inp["item_key"])
            if have < inp["qty"]:
                missing.append(f"{inp['item_key']} ({have}/{inp['qty']})")
        if missing:
            raise CraftError(400, "Brak komponentów: " + ", ".join(missing))

        # 2) Walidacja specyficzna dla wyniku (przed konsumpcją).
        output_type = str(recipe["output_type"] or "consumable").strip()
        upgrade_target: sqlite3.Row | None = None
        if output_type == "weapon_upgrade":
            upgrade_target = _pick_upgrade_weapon(conn, character_id, target_inventory_id)
            if WEAPON_HONE_AFFIX in _affix_keys(upgrade_target):
                raise CraftError(400, "Ta broń jest już naostrzona — ulepszenie nie kumuluje się.")

        # 3) Koszt usługi (po zniżce krasnoluda) i walidacja złota.
        cost = _service_cost(recipe, race)
        cur_gold = int(char["gold_gp"] or 0)
        if cur_gold < cost:
            raise CraftError(400, f"Niewystarczające złoto: potrzeba {cost} gp, masz {cur_gold} gp.")

        # 4) Konsumpcja komponentów.
        for inp in inputs:
            _consume_component(conn, character_id, inp["item_key"], inp["qty"])

        # 5) Opłata za usługę (chokepoint U26 — journaluje do character_gold_log).
        if cost > 0:
            from app.services.economy_service import change_gold
            change_gold(conn, int(character_id), -cost, "craft_service")

        # 6) Wytworzenie wyniku.
        result: dict[str, Any] = {"output_type": output_type}
        if output_type == "consumable":
            out_key = str(recipe["output_key"] or "").strip()
            out_qty = max(1, int(recipe["output_qty"] or 1))
            if not out_key:
                raise CraftError(400, "Przepis nie ma zdefiniowanego wyniku.")
            conn.commit()  # utrwal konsumpcję+złoto przed grantem (osobne połączenie)
            from app.services.loot_service import grant_loot_to_character
            granted = grant_loot_to_character(
                int(character_id),
                [{"consumable_key": out_key, "quantity": out_qty}],
                source="craft",
            )
            result["granted"] = granted
            result["output_key"] = out_key
            result["output_qty"] = out_qty
        elif output_type == "weapon_upgrade":
            assert upgrade_target is not None
            keys = _affix_keys(upgrade_target)
            keys.append(WEAPON_HONE_AFFIX)
            conn.execute(
                "UPDATE character_inventory SET affixes_json = ? WHERE id = ?",
                (json.dumps(keys, ensure_ascii=False), upgrade_target["id"]),
            )
            conn.commit()
            result["weapon_key"] = upgrade_target["weapon_key"]
            result["inventory_id"] = upgrade_target["id"]
            result["damage_bonus"] = 1
        elif output_type == "armor_repair":
            armor = conn.execute(
                """
                SELECT id, meta_json, durability_max FROM character_inventory
                WHERE character_id = ? AND item_key IS NOT NULL
                  AND COALESCE(equipped,0) = 1
                  AND LOWER(TRIM(COALESCE(slot,''))) IN ('torso','armor')
                ORDER BY id ASC LIMIT 1
                """,
                (int(character_id),),
            ).fetchone()
            repaired = None
            if armor:
                dmax = armor["durability_max"]
                if dmax is not None:
                    conn.execute(
                        "UPDATE character_inventory SET durability_current = ? WHERE id = ?",
                        (int(dmax), armor["id"]),
                    )
                else:
                    try:
                        meta = json.loads(armor["meta_json"] or "{}")
                    except (json.JSONDecodeError, TypeError):
                        meta = {}
                    meta["mended"] = True
                    conn.execute(
                        "UPDATE character_inventory SET meta_json = ? WHERE id = ?",
                        (json.dumps(meta, ensure_ascii=False), armor["id"]),
                    )
                repaired = armor["id"]
            conn.commit()
            result["armor_inventory_id"] = repaired
        else:
            conn.commit()

        # Świeże złoto po opłacie.
        g = conn.execute(
            "SELECT gold_gp FROM characters WHERE id = ?", (int(character_id),)
        ).fetchone()
        result.update({
            "ok": True,
            "recipe_key": recipe["key"],
            "recipe_label": recipe["label"],
            "service_cost_gold": cost,
            "dwarf_discount": race == "dwarf" and int(recipe["service_cost_gold"] or 0) > 0,
            "gold_after": int(g["gold_gp"] or 0) if g else None,
            "consumed": inputs,
        })
        return result
    except CraftError:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── #1341 BL-D2 — eksperymenty gracza: ukryte receptury + fuszerki ─────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _signature(components: list[dict]) -> tuple[tuple[str, int], ...]:
    """Kanoniczna sygnatura kombinacji: posortowane (item_key, qty). Deterministyczna
    — ta sama kombinacja zawsze daje tę samą sygnaturę, niezależnie od kolejności."""
    agg: dict[str, int] = {}
    for c in components:
        key = str(c.get("item_key") or "").strip()
        qty = int(c.get("qty") or c.get("quantity") or 0)
        if key and qty > 0:
            agg[key] = agg.get(key, 0) + qty
    return tuple(sorted(agg.items()))


def _match_hidden_recipe(conn: sqlite3.Connection, sig: tuple) -> sqlite3.Row | None:
    """Dopasuj sygnaturę do PULI UKRYTYCH receptur (is_hidden=1, aktywne). Zwraca
    wiersz receptury albo None. Jawne receptury NIGDY nie biorą udziału — eksperyment
    odkrywa wyłącznie to, co admin ukrył."""
    rows = conn.execute(
        "SELECT * FROM game_config_recipes WHERE is_active = 1 AND is_hidden = 1"
    ).fetchall()
    for r in rows:
        if _signature(_parse_inputs(r)) == sig:
            return r
    return None


def _load_sheet(conn: sqlite3.Connection, character_id: int) -> dict:
    row = conn.execute(
        "SELECT sheet_json FROM characters WHERE id = ? LIMIT 1", (int(character_id),)
    ).fetchone()
    if not row:
        raise CraftError(404, "Nie znaleziono bohatera.")
    try:
        return json.loads(row["sheet_json"] or "{}") or {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _consume_half(conn: sqlite3.Connection, character_id: int, components: list[dict]) -> list[dict]:
    """Strata połowy komponentów (zaokrąglenie w górę liczby jednostek per stos).
    Zwraca listę faktycznie zabranych {item_key, qty}."""
    taken: list[dict] = []
    for c in components:
        key = c["item_key"]
        half = (int(c["qty"]) + 1) // 2  # ceil — połowa zawsze coś zabiera
        if half > 0:
            _consume_component(conn, character_id, key, half)
            taken.append({"item_key": key, "qty": half})
    return taken


def _consume_all(conn: sqlite3.Connection, character_id: int, components: list[dict]) -> list[dict]:
    for c in components:
        _consume_component(conn, character_id, c["item_key"], int(c["qty"]))
    return [{"item_key": c["item_key"], "qty": int(c["qty"])} for c in components]


def _roll_fumble(conn: sqlite3.Connection, character_id: int, sheet: dict, tag: str) -> dict:
    """Rozstrzygnij fuszerkę wg FUMBLE_TABLE. `tag` = kontekst ('miss'|'nat1').
    Komponenty są już skonsumowane przez wywołującego. Zwraca opis wyniku."""
    total = sum(w for _, w in FUMBLE_TABLE)
    pick = random.randint(1, total)
    acc = 0
    outcome = "loss"
    for name, w in FUMBLE_TABLE:
        acc += w
        if pick <= acc:
            outcome = name
            break

    result: dict[str, Any] = {"fumble": outcome, "fumble_context": tag}
    if outcome == "loss":
        result["message"] = "Mikstura zwietrzała w tyglu — składniki przepadły bez śladu."
    elif outcome == "slag":
        result["message"] = "Z tygla wyszedł tylko bezwartościowy, zeszklony stop. Strata."
    elif outcome == "damage":
        dmg = random.randint(1, 4)
        cur = int(sheet.get("current_hp") or 0)
        new_hp = max(0, cur - dmg)
        sheet["current_hp"] = new_hp
        conn.execute(
            "UPDATE characters SET sheet_json = ? WHERE id = ?",
            (json.dumps(sheet, ensure_ascii=False), int(character_id)),
        )
        result["self_damage"] = dmg
        result["hp_after"] = new_hp
        result["message"] = f"Tygiel wybucha w rękach — {dmg} obrażeń. Składniki przepadły."
    elif outcome == "cursed":
        curse = {
            "name": "Przeklęty stop",
            "cursed": True,
            "flaw": "Wypacza tygiel: kolejny eksperyment ma utrudnienie (fabularne).",
            "source": "craft_fumble",
        }
        items = sheet.get("narrative_items")
        if not isinstance(items, list):
            items = []
        items.append(curse)
        sheet["narrative_items"] = items
        conn.execute(
            "UPDATE characters SET sheet_json = ? WHERE id = ?",
            (json.dumps(sheet, ensure_ascii=False), int(character_id)),
        )
        result["cursed_item"] = curse
        result["message"] = ("Ze stygnącej mazi wyłania się przeklęty stop — "
                             "trzyma się rąk i szepcze. Lepiej było nie próbować.")
    return result


def list_character_recipes(character_id: int) -> dict:
    """Trwale odkryte receptury bohatera (BL-D2). Zwraca listę z etykietą przepisu."""
    conn = _conn()
    try:
        rows = conn.execute(
            """
            SELECT cr.recipe_key, cr.discovered_at,
                   r.label, r.craft_tier, r.output_type, r.output_key
            FROM character_recipes cr
            LEFT JOIN game_config_recipes r ON r.key = cr.recipe_key
            WHERE cr.character_id = ?
            ORDER BY cr.discovered_at DESC
            """,
            (int(character_id),),
        ).fetchall()
        out = [dict(r) for r in rows]
        return {"character_id": int(character_id), "discovered": out}
    finally:
        conn.close()


def experiment(
    character_id: int,
    components: list[dict],
    campaign_id: int | None = None,
) -> dict:
    """Eksperyment przy tyglu (#1341 BL-D2).

    Gracz wskazuje 2–4 komponenty + opłatę. Silnik liczy sygnaturę → dopasowuje do
    UKRYTYCH receptur admina:
      • trafienie → test `trade_craft` DC wg tieru:
          - sukces → przedmiot z receptury + trwałe ODKRYCIE (character_recipes)
          - porażka → strata połowy komponentów, receptura NIE ujawniona
          - Nat 1 → fuszerka (tabela)
          - Nat 20 → auto-sukces
      • pudło (brak dopasowania) → tabela fuszerek.

    Wynik ZAWSZE pochodzi z receptury autorowanej przez admina — kombinacja spoza
    puli NIGDY nie tworzy przedmiotu (test negatywny akceptacji).
    """
    # Normalizacja + walidacja wejścia.
    norm: list[dict] = []
    seen: set[str] = set()
    for c in components or []:
        key = str((c or {}).get("item_key") or "").strip()
        qty = int((c or {}).get("qty") or (c or {}).get("quantity") or 0)
        if not key or qty <= 0:
            continue
        if key in seen:
            raise CraftError(400, f"Komponent '{key}' wskazany dwukrotnie — scal ilość.")
        seen.add(key)
        norm.append({"item_key": key, "qty": qty})
    n = len(norm)
    if n < EXPERIMENT_MIN_COMPONENTS or n > EXPERIMENT_MAX_COMPONENTS:
        raise CraftError(
            400,
            f"Eksperyment wymaga {EXPERIMENT_MIN_COMPONENTS}–{EXPERIMENT_MAX_COMPONENTS} "
            f"komponentów (podano {n}).",
        )

    conn = _conn()
    try:
        char = _get_character(conn, character_id)

        # 1) Walidacja posiadania komponentów (przed mutacją).
        missing: list[str] = []
        for c in norm:
            have = _owned_component_qty(conn, character_id, c["item_key"])
            if have < c["qty"]:
                missing.append(f"{c['item_key']} ({have}/{c['qty']})")
        if missing:
            raise CraftError(400, "Brak komponentów: " + ", ".join(missing))

        # 2) Opłata za próbę (zawsze — eksperyment kosztuje niezależnie od wyniku).
        cost = EXPERIMENT_COST_GOLD
        cur_gold = int(char["gold_gp"] or 0)
        if cur_gold < cost:
            raise CraftError(400, f"Niewystarczające złoto: potrzeba {cost} gp, masz {cur_gold} gp.")
        if cost > 0:
            from app.services.economy_service import change_gold
            change_gold(conn, int(character_id), -cost, "craft_experiment")

        sig = _signature(norm)
        recipe = _match_hidden_recipe(conn, sig)
        sheet = _load_sheet(conn, character_id)

        result: dict[str, Any] = {
            "ok": True,
            "experiment_cost_gold": cost,
            "components": norm,
        }

        if recipe is None:
            # ── Pudło: kombinacja spoza puli ukrytych receptur → tabela fuszerek. ──
            consumed = _consume_all(conn, character_id, norm)
            fum = _roll_fumble(conn, character_id, sheet, tag="miss")
            conn.commit()
            result.update({
                "outcome": "fumble",
                "matched": False,
                "consumed": consumed,
                **fum,
            })
        else:
            # ── Trafienie: test trade_craft DC wg tieru. ──
            tier = str(recipe["craft_tier"] or "medium").strip().lower()
            dc = EXPERIMENT_TIER_DC.get(tier, EXPERIMENT_TIER_DC["medium"])
            from app.services.skill_service import calc_skill_modifier_info
            from app.services import dice
            info = calc_skill_modifier_info(
                sheet, "trade_craft", conn=conn, character_id=int(character_id)
            )
            modifier = int(info["total"])
            raw = int(dice.roll_d20())
            total = raw + modifier
            is_nat20 = raw == 20
            is_nat1 = raw == 1
            success = is_nat20 or (not is_nat1 and total >= dc)

            roll = {
                "skill": "trade_craft", "dc": dc, "tier": tier,
                "raw": raw, "modifier": modifier, "total": total,
                "is_nat20": is_nat20, "is_nat1": is_nat1,
            }
            result["roll"] = roll
            result["matched"] = True

            if success:
                consumed = _consume_all(conn, character_id, norm)
                # Trwałe odkrycie receptury (idempotentne).
                conn.execute(
                    "INSERT OR IGNORE INTO character_recipes "
                    "(character_id, recipe_key, discovered_at) VALUES (?, ?, ?)",
                    (int(character_id), recipe["key"], _now_iso()),
                )
                out_key = str(recipe["output_key"] or "").strip()
                out_qty = max(1, int(recipe["output_qty"] or 1))
                conn.commit()  # utrwal przed grantem (osobne połączenie w loot_service)
                granted = None
                if out_key:
                    from app.services.loot_service import grant_loot_to_character
                    granted = grant_loot_to_character(
                        int(character_id),
                        [{"consumable_key": out_key, "quantity": out_qty}],
                        source="craft_experiment",
                    )
                result.update({
                    "outcome": "discovery",
                    "consumed": consumed,
                    "recipe_key": recipe["key"],
                    "recipe_label": recipe["label"],
                    "output_key": out_key,
                    "output_qty": out_qty,
                    "granted": granted,
                    "discovered": True,
                    "message": f"Udało się! Odkrywasz przepis: {recipe['label']}.",
                })
            elif is_nat1:
                # Krytyczna porażka — fuszerka (gorsza niż zwykła porażka).
                consumed = _consume_all(conn, character_id, norm)
                fum = _roll_fumble(conn, character_id, sheet, tag="nat1")
                conn.commit()
                result.update({
                    "outcome": "fumble",
                    "consumed": consumed,
                    "discovered": False,
                    **fum,
                })
            else:
                # Zwykła porażka — strata połowy komponentów, receptura NIE ujawniona.
                consumed = _consume_half(conn, character_id, norm)
                conn.commit()
                result.update({
                    "outcome": "failure",
                    "consumed": consumed,
                    "discovered": False,
                    "message": ("Coś tu drzemie, ale receptura wymyka się z rąk. "
                               "Połowa składników przepadła."),
                })

        # Świeże złoto po opłacie.
        g = conn.execute(
            "SELECT gold_gp FROM characters WHERE id = ?", (int(character_id),)
        ).fetchone()
        result["gold_after"] = int(g["gold_gp"] or 0) if g else None
        return result
    except CraftError:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
