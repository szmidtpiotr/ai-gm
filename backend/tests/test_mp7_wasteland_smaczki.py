"""MP-7 (#1494) — smaczki Martwych Pustkowi: sól premium + kościany kompas + bezwodne hexy.

Źródło prawdy: docs/world/regions/martwe_pustkowia.md §5-6 (ZATWIERDZONE).

Trzy mechaniki, trzy bloki testów:
  * sól premium Piętnowanych = te same kondycje co sól z Grań (SG-7), ale TAŃSZA;
    u Helgi w Graniach drożej (narzut per-wpis),
  * kościany kompas — o połowę mniejsza szansa zasadzki na obozie + 2 do percepcji
    w ruinach (0 poza ruinami / bez kompasu),
  * bezwodne hexy (sol/martwa_ziemia) — pełny odpoczynek wymaga bukłaka; enklawa i
    Misja mają wodę; bukłak zużywa się przy użyciu.
"""
import importlib.util
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import wasteland_service


def _load_seed():
    """Wczytaj skrypt seeda niezależnie od tego, gdzie leży (kontener /app/, repo scripts/)."""
    here = os.path.dirname(__file__)
    for cand in (
        "/app/seed_mp7_wasteland_smaczki.py",
        os.path.join(here, "..", "..", "scripts", "seed_mp7_wasteland_smaczki.py"),
        os.path.join(here, "..", "scripts", "seed_mp7_wasteland_smaczki.py"),
    ):
        if os.path.exists(cand):
            spec = importlib.util.spec_from_file_location("seed_mp7_wasteland_smaczki", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise ImportError("seed_mp7_wasteland_smaczki.py not found")


seed = _load_seed()


# ── fikstury ─────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE character_inventory (id INTEGER PRIMARY KEY, character_id INTEGER, "
        "item_key TEXT, weapon_key TEXT, consumable_key TEXT, quantity INTEGER DEFAULT 1)"
    )
    c.execute(
        "CREATE TABLE game_sessions (campaign_id INTEGER, session_flags TEXT, "
        "current_location_id INTEGER)"
    )
    c.execute(
        "CREATE TABLE world_hexes (q INTEGER, r INTEGER, hex_type TEXT, is_active INTEGER DEFAULT 1)"
    )
    c.execute("CREATE TABLE game_locations (id INTEGER PRIMARY KEY, key TEXT)")
    return c


def _stand(c: sqlite3.Connection, *, campaign_id=7, q=64, r=37, hex_type="sol",
           location_id=None, location_key=None) -> None:
    """Ustaw drużynę na heksie (q,r) o danym terenie i opcjonalnie w lokacji."""
    c.execute("DELETE FROM world_hexes")
    c.execute("INSERT INTO world_hexes (q, r, hex_type, is_active) VALUES (?, ?, ?, 1)",
              (q, r, hex_type))
    if location_key is not None:
        c.execute("INSERT INTO game_locations (id, key) VALUES (?, ?)",
                  (location_id or 1, location_key))
        loc_id = location_id or 1
    else:
        loc_id = None
    c.execute("DELETE FROM game_sessions")
    c.execute(
        "INSERT INTO game_sessions (campaign_id, session_flags, current_location_id) VALUES (?, ?, ?)",
        (campaign_id, json.dumps({"current_hex": {"q": q, "r": r}}), loc_id),
    )
    c.commit()


def _give(c: sqlite3.Connection, character_id: int, *, item=None, qty=1) -> None:
    c.execute(
        "INSERT INTO character_inventory (character_id, item_key, quantity) VALUES (?, ?, ?)",
        (character_id, item, qty),
    )
    c.commit()


# ═══ 1. SÓL PREMIUM ═══════════════════════════════════════════════════════════

def _seed_conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE game_config_weapons (key TEXT PRIMARY KEY, label TEXT)")
    c.execute("CREATE TABLE game_config_items (key TEXT PRIMARY KEY, label TEXT, value_gp INTEGER)")
    c.execute(
        "CREATE TABLE game_config_consumables (key TEXT PRIMARY KEY, label TEXT, description TEXT, "
        "effect_type TEXT, effect_dice TEXT, effect_bonus INTEGER, effect_target TEXT, "
        "weight_kg REAL, charges INTEGER, base_price INTEGER, price_gp INTEGER, note TEXT, "
        "rarity INTEGER, is_active INTEGER, approved INTEGER, ai_generated INTEGER, "
        "min_level INTEGER, location_tags TEXT, hidden INTEGER, effect_json TEXT, "
        "created_at TEXT, updated_at TEXT)"
    )
    c.execute("CREATE TABLE npcs (key TEXT PRIMARY KEY, shop_inventory_json TEXT, updated_at TEXT)")
    # stuby z MP-5 (broń + item), które MP-7 zastępuje consumable
    c.execute("INSERT INTO game_config_weapons (key, label) VALUES ('solona_klinga', 'Solona klinga')")
    c.execute("INSERT INTO game_config_items (key, label, value_gp) VALUES ('krag_soli', 'Krąg soli', 18)")
    c.execute("INSERT INTO game_config_items (key, label, value_gp) VALUES ('kosciany_kompas', 'Kościany kompas', 30)")
    c.execute("INSERT INTO game_config_items (key, label, value_gp) VALUES ('waterskin', 'Bukłak', 1)")
    c.execute(
        "INSERT INTO npcs (key, shop_inventory_json) VALUES ('nadira_zniwiarka', ?)",
        (json.dumps([{"type": "item", "key": "krag_soli"},
                     {"type": "weapon", "key": "solona_klinga"},
                     {"type": "item", "key": "waterskin"}]),),
    )
    c.execute(
        "INSERT INTO npcs (key, shop_inventory_json) VALUES ('helga_solnobroda', ?)",
        (json.dumps([{"type": "consumable", "key": "salt_circle_pouch"}]),),
    )
    c.commit()
    return c


def test_premium_salt_maps_to_sg7_conditions_and_is_cheaper():
    c = _seed_conn()
    seed.seed_premium_consumables(c)
    rows = {r["key"]: r for r in c.execute("SELECT * FROM game_config_consumables").fetchall()}
    # (klucz consumable → kondycja SG-7, cena premium, cena wariantu z Grań)
    expect = {"krag_soli": ("salt_circle", 18, 35),
              "solona_klinga": ("salted_blade", 24, 45),
              "szczypta_soli": ("salt_pinch", 8, 30)}
    for key, (cond, price, grania_price) in expect.items():
        row = rows[key]
        assert row["effect_type"] == "add_condition"
        ej = json.loads(row["effect_json"])
        applied = ej["effects"][0]
        assert applied["type"] == "apply_condition"
        assert applied["condition_key"] == cond   # ta sama mechanika co sól z Grań
        assert row["price_gp"] == price
        assert price < grania_price, f"{key} ma być tańsza od wariantu z Grań"


def test_stub_weapon_and_item_removed_shops_repointed():
    c = _seed_conn()
    seed.seed_premium_consumables(c)
    seed.seed_nadira(c)
    seed.seed_helga(c)
    # stub-broń i stub-item zniknęły
    assert c.execute("SELECT 1 FROM game_config_weapons WHERE key='solona_klinga'").fetchone() is None
    assert c.execute("SELECT 1 FROM game_config_items WHERE key='krag_soli'").fetchone() is None
    # Nadira: cała trójka soli jako consumable
    nadira = json.loads(c.execute(
        "SELECT shop_inventory_json FROM npcs WHERE key='nadira_zniwiarka'").fetchone()[0])
    salt = {e["key"]: e["type"] for e in nadira if e["key"] in
            ("krag_soli", "solona_klinga", "szczypta_soli")}
    assert salt == {"krag_soli": "consumable", "solona_klinga": "consumable",
                    "szczypta_soli": "consumable"}


def test_helga_sells_wasteland_salt_at_a_markup():
    c = _seed_conn()
    seed.seed_premium_consumables(c)
    seed.seed_helga(c)
    helga = json.loads(c.execute(
        "SELECT shop_inventory_json FROM npcs WHERE key='helga_solnobroda'").fetchone()[0])
    priced = {e["key"]: e.get("price") for e in helga if e["key"] in seed.HELGA_SALT_MARKUP}
    assert priced == {"krag_soli": 36, "solona_klinga": 48, "szczypta_soli": 16}
    # narzut Helgi > cena u źródła (Nadira / katalog)
    for it in seed.PREMIUM_SALT:
        assert seed.HELGA_SALT_MARKUP[it["key"]] > it["price"]


# ═══ 2. KOŚCIANY KOMPAS ═══════════════════════════════════════════════════════

def test_compass_halves_camp_ambush_chance():
    c = _conn()
    _give(c, 3, item="kosciany_kompas")
    assert wasteland_service.camp_ambush_multiplier(c, 3) == 0.5


def test_no_compass_no_ambush_reduction():
    c = _conn()
    assert wasteland_service.camp_ambush_multiplier(c, 3) == 1.0


def test_compass_gives_perception_bonus_in_ruins():
    c = _conn()
    _give(c, 3, item="kosciany_kompas")
    _stand(c, hex_type="ruins")
    assert wasteland_service.ruins_perception_bonus(c, 3, 7, "perception") == 2


def test_compass_perception_bonus_only_in_ruins():
    c = _conn()
    _give(c, 3, item="kosciany_kompas")
    _stand(c, hex_type="sol")  # nie ruiny
    assert wasteland_service.ruins_perception_bonus(c, 3, 7, "perception") == 0


def test_compass_perception_bonus_only_for_perception_skills():
    c = _conn()
    _give(c, 3, item="kosciany_kompas")
    _stand(c, hex_type="ruins")
    assert wasteland_service.ruins_perception_bonus(c, 3, 7, "athletics") == 0


def test_no_compass_no_perception_bonus():
    c = _conn()
    _stand(c, hex_type="ruins")
    assert wasteland_service.ruins_perception_bonus(c, 3, 7, "perception") == 0


# ═══ 3. BEZWODNE HEXY (bukłak) ════════════════════════════════════════════════

def test_waterless_hex_needs_waterskin():
    c = _conn()
    _stand(c, hex_type="sol")
    st = wasteland_service.rest_water_status(c, 3, 7)
    assert st["needs_waterskin"] is True
    assert st["has_waterskin"] is False  # nie dano bukłaka


def test_martwa_ziemia_also_waterless():
    c = _conn()
    _stand(c, hex_type="martwa_ziemia")
    assert wasteland_service.rest_water_status(c, 3, 7)["needs_waterskin"] is True


def test_normal_terrain_needs_no_waterskin():
    c = _conn()
    _stand(c, hex_type="heath")
    assert wasteland_service.rest_water_status(c, 3, 7)["needs_waterskin"] is False


def test_enclave_has_water_even_on_salt():
    c = _conn()
    _stand(c, hex_type="sol", location_key="solny_prog")
    assert wasteland_service.rest_water_status(c, 3, 7)["needs_waterskin"] is False


def test_enclave_sublocation_has_water():
    c = _conn()
    _stand(c, hex_type="sol", location_key="solny_prog_gospoda")
    assert wasteland_service.rest_water_status(c, 3, 7)["needs_waterskin"] is False


def test_mission_has_water_on_dead_ground():
    c = _conn()
    _stand(c, hex_type="martwa_ziemia", location_key="misja_swiatla")
    assert wasteland_service.rest_water_status(c, 3, 7)["needs_waterskin"] is False


def test_waterskin_detected_and_consumed():
    c = _conn()
    _stand(c, hex_type="sol")
    _give(c, 3, item="waterskin", qty=2)
    st = wasteland_service.rest_water_status(c, 3, 7)
    assert st["needs_waterskin"] is True and st["has_waterskin"] is True
    assert wasteland_service.consume_waterskin(c, 3) is True
    # było 2 → zostaje 1
    left = c.execute(
        "SELECT quantity FROM character_inventory WHERE character_id=3 AND item_key='waterskin'"
    ).fetchone()[0]
    assert left == 1
    # zużyj ostatni → wiersz znika
    assert wasteland_service.consume_waterskin(c, 3) is True
    assert c.execute(
        "SELECT 1 FROM character_inventory WHERE character_id=3 AND item_key='waterskin'"
    ).fetchone() is None
    assert wasteland_service.consume_waterskin(c, 3) is False


def test_partial_rest_math_is_half():
    # dokumentuje wartość startową: bez bukłaka na bezwodnym hexie leczysz o połowę
    assert wasteland_service.WATERLESS_PARTIAL_MULT == 0.5
    heal = 20
    assert int(heal * wasteland_service.WATERLESS_PARTIAL_MULT) == 10
