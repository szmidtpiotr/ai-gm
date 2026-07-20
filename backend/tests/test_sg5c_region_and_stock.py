"""SG-5c (#1481) — dwie naprawy silnika ekonomii/świata:

1. `reputation_service.resolve_region` gubił region w sub-lokacjach (brak własnego
   hexu → fallback 'kresy'), przez co reputacja regionalna, plotki (#1190),
   wydarzenia (#1193), choroby i modyfikatory łupu trafiały w złą krainę.
2. `shop_service._default_stock_for_npc` dobierał NAJTAŃSZE pozycje z katalogu,
   więc każdy kowal w grze sprzedawał kij, laskę, drewnianą tarczę i sztylet.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import reputation_service, shop_service


# ── 1. Region ────────────────────────────────────────────────────────────────

def _world_conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE game_locations (id INTEGER PRIMARY KEY, key TEXT, region TEXT, "
        "parent_key TEXT, world_hex_q INTEGER, world_hex_r INTEGER, tier INTEGER)"
    )
    c.execute("CREATE TABLE game_sessions (campaign_id INTEGER, current_location_id INTEGER)")
    c.execute("CREATE TABLE world_hexes (q INTEGER, r INTEGER, region TEXT, map_level INTEGER)")
    # Hub z hexem + sub bez hexu (wzorzec #1212: wnętrza osady nie mają własnego hexu).
    c.execute("INSERT INTO game_locations VALUES (1,'kamienny_grod','siwe_granie',NULL,16,-17,2)")
    c.execute("INSERT INTO game_locations VALUES (2,'grod_wielka_kuznia','siwe_granie','kamienny_grod',NULL,NULL,2)")
    # Sub zaseedowany BEZ regionu — musi go odziedziczyć po rodzicu.
    c.execute("INSERT INTO game_locations VALUES (3,'grod_targ_solny',NULL,'kamienny_grod',NULL,NULL,1)")
    c.execute("INSERT INTO world_hexes VALUES (16,-17,'siwe_granie',0)")
    c.commit()
    return c


def _at(c: sqlite3.Connection, loc_id: int, campaign_id: int = 500) -> int:
    c.execute("DELETE FROM game_sessions")
    c.execute("INSERT INTO game_sessions VALUES (?,?)", (campaign_id, loc_id))
    c.commit()
    return campaign_id


def test_region_from_hub_with_hex():
    c = _world_conn()
    assert reputation_service.resolve_region(c, _at(c, 1)) == "siwe_granie"


def test_region_from_sublocation_without_hex():
    """Sedno buga: stojąc w Wielkiej Kuźni gra widziała 'kresy'."""
    c = _world_conn()
    assert reputation_service.resolve_region(c, _at(c, 2)) == "siwe_granie"


def test_region_inherited_from_parent_when_sub_has_none():
    c = _world_conn()
    assert reputation_service.resolve_region(c, _at(c, 3)) == "siwe_granie"


def test_region_falls_back_to_default_without_any_data():
    c = _world_conn()
    c.execute("DELETE FROM game_sessions")
    c.commit()
    assert reputation_service.resolve_region(c, 500) == reputation_service.REGION_DEFAULT


def test_region_legacy_db_without_region_column_still_uses_hex():
    """Stara/minimalna baza bez kolumny `region` — ścieżka hexowa musi przeżyć."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE game_locations (id INTEGER PRIMARY KEY, key TEXT, "
              "world_hex_q INTEGER, world_hex_r INTEGER)")
    c.execute("CREATE TABLE game_sessions (campaign_id INTEGER, current_location_id INTEGER)")
    c.execute("CREATE TABLE world_hexes (q INTEGER, r INTEGER, region TEXT)")
    c.execute("INSERT INTO game_locations VALUES (1,'stary_hex',3,4)")
    c.execute("INSERT INTO world_hexes VALUES (3,4,'czarnobor')")
    c.execute("INSERT INTO game_sessions VALUES (7,1)")
    c.commit()
    assert reputation_service.resolve_region(c, 7) == "czarnobor"


# ── 2. Domyślny asortyment ───────────────────────────────────────────────────

def _shop_conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE npcs (id INTEGER PRIMARY KEY, key TEXT, label TEXT, npc_type TEXT, "
        "is_crafter INTEGER, crafter_type TEXT, shop_inventory_json TEXT)"
    )
    c.execute("CREATE TABLE game_items (key TEXT PRIMARY KEY, kind TEXT, price_gp INTEGER, is_active INTEGER)")
    c.execute("CREATE TABLE game_locations (id INTEGER PRIMARY KEY, key TEXT, tier INTEGER)")
    c.execute("CREATE TABLE location_npc_assignments (npc_key TEXT, location_key TEXT, is_active INTEGER)")
    c.execute("INSERT INTO game_locations VALUES (1,'wioska',1),(2,'miasto',3)")
    # Katalog z realnym rozrzutem cen: tanie graty i drogi sprzęt.
    for kind, prices in (
        ("weapon", [6, 7, 8, 10, 15, 25, 40, 60, 120, 200]),
        ("armor", [2, 3, 5, 10, 20, 50, 90, 150, 400, 1500]),
        ("item", [1, 1, 2, 3, 5, 15, 25, 60, 250, 1000]),
        ("consumable", [1, 2, 8, 15, 20, 25, 40, 90]),
    ):
        for i, p in enumerate(prices):
            c.execute("INSERT INTO game_items VALUES (?,?,?,1)", (f"{kind}_{i}", kind, p))
    c.execute("INSERT INTO game_items VALUES ('test_junk','item',5,1)")
    c.commit()
    return c


def _shop_conn_with_item_data() -> sqlite3.Connection:
    """Katalog z `item_data` — tam mieszkają przedmioty questowe i relikty."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE npcs (id INTEGER PRIMARY KEY, key TEXT, label TEXT, npc_type TEXT, "
        "is_crafter INTEGER, crafter_type TEXT, shop_inventory_json TEXT)"
    )
    c.execute("CREATE TABLE game_items (key TEXT PRIMARY KEY, kind TEXT, price_gp INTEGER, "
              "is_active INTEGER, item_data TEXT)")
    c.execute("CREATE TABLE game_locations (id INTEGER PRIMARY KEY, key TEXT, tier INTEGER)")
    c.execute("CREATE TABLE location_npc_assignments (npc_key TEXT, location_key TEXT, is_active INTEGER)")
    c.execute("INSERT INTO game_locations VALUES (1,'miasto',3)")
    for key, price, itype in (
        ("lina", 2, "gear"), ("latarnia", 7, "tool"), ("ruda", 3, "material"),
        ("plecak", 5, "gear"), ("luneta", 200, "gear"),
        ("zloty_bozek", 300, "quest"), ("czaszka_demona", 180, "quest"),
        ("magiczny_wytrych", 120, "relic"),
    ):
        c.execute("INSERT INTO game_items VALUES (?,?,?,1,?)",
                  (key, "item", price, '{"item_type": "%s"}' % itype))
    for i, p in enumerate([1, 5, 20, 40]):
        c.execute("INSERT INTO game_items VALUES (?,?,?,1,'{}')", (f"c_{i}", "consumable", p))
    for i, p in enumerate([10, 30, 90]):
        c.execute("INSERT INTO game_items VALUES (?,?,?,1,'{}')", (f"w_{i}", "weapon", p))
    for i, p in enumerate([10, 30, 90]):
        c.execute("INSERT INTO game_items VALUES (?,?,?,1,'{}')", (f"a_{i}", "armor", p))
    c.commit()
    return c


def test_quest_items_and_relics_never_land_on_a_shelf():
    c = _shop_conn_with_item_data()
    c.execute("INSERT INTO npcs (key,label,npc_type,is_crafter,shop_inventory_json) "
              "VALUES ('kupiec_q','Kupiec','merchant',0,'[]')")
    c.execute("INSERT INTO location_npc_assignments VALUES ('kupiec_q','miasto',1)")
    c.commit()
    npc = c.execute("SELECT * FROM npcs WHERE key='kupiec_q'").fetchone()
    keys = {e["key"] for e in shop_service._default_stock_for_npc(c, npc)}
    assert not ({"zloty_bozek", "czaszka_demona", "magiczny_wytrych"} & keys), keys
    assert keys, "sklep nie może zostać pusty po odfiltrowaniu questów"


def _npc(c, key, label="Kupiec", npc_type="merchant", is_crafter=0, crafter_type=None,
         stock="[]", location="wioska"):
    c.execute(
        "INSERT INTO npcs (key,label,npc_type,is_crafter,crafter_type,shop_inventory_json) "
        "VALUES (?,?,?,?,?,?)",
        (key, label, npc_type, is_crafter, crafter_type, stock),
    )
    if location:
        c.execute("INSERT INTO location_npc_assignments VALUES (?,?,1)", (key, location))
    c.commit()
    return c.execute("SELECT * FROM npcs WHERE key=?", (key,)).fetchone()


def _prices(c, entries):
    return [
        c.execute("SELECT price_gp FROM game_items WHERE key=?", (e["key"],)).fetchone()[0]
        for e in entries
    ]


def test_smith_stock_is_not_just_the_cheapest_junk():
    c = _shop_conn()
    npc = _npc(c, "kowal_miejski", "Kowal", is_crafter=1, location="miasto")
    entries = shop_service._default_stock_for_npc(c, npc)
    weapons = [e for e in entries if e["type"] == "weapon"]
    assert len(weapons) >= 5
    prices = _prices(c, weapons)
    # Stary kod brał 4 najtańsze bronie z katalogu; nowy ma pokryć zakres.
    assert max(prices) >= 40, f"kowal w mieście oferuje tylko tanie graty: {prices}"


def test_tier_caps_what_a_hamlet_can_stock():
    c = _shop_conn()
    wies = shop_service._default_stock_for_npc(c, _npc(c, "kowal_wiejski", "Kowal", is_crafter=1))
    miasto = shop_service._default_stock_for_npc(
        c, _npc(c, "kowal_stoleczny", "Kowal", is_crafter=1, location="miasto")
    )
    assert max(_prices(c, wies)) <= shop_service._TIER_PRICE_CAP[1]
    assert max(_prices(c, miasto)) > shop_service._TIER_PRICE_CAP[1]


def test_stock_is_stable_across_calls():
    """Ten sam sklep musi dać tę samą listę — inaczej kupno rozjedzie się
    z podglądem i sypnie 'item_not_in_shop'."""
    c = _shop_conn()
    npc = _npc(c, "kupiec_x", "Kupiec")
    assert shop_service._default_stock_for_npc(c, npc) == shop_service._default_stock_for_npc(c, npc)


def test_two_shops_in_one_town_are_not_identical():
    c = _shop_conn()
    a = shop_service._default_stock_for_npc(c, _npc(c, "kowal_a", "Kowal", is_crafter=1, location="miasto"))
    b = shop_service._default_stock_for_npc(c, _npc(c, "kowal_b", "Kowal", is_crafter=1, location="miasto"))
    assert a != b


def test_healer_still_sells_only_consumables():
    """Kontrakt z #579 zostaje: zielarka nie handluje żelastwem."""
    c = _shop_conn()
    entries = shop_service._default_stock_for_npc(c, _npc(c, "zielarka_agata", "Zielarka Agata"))
    assert entries and all(e["type"] == "consumable" for e in entries)


def test_innkeeper_sells_supplies_not_swords():
    c = _shop_conn()
    entries = shop_service._default_stock_for_npc(c, _npc(c, "karczmarz_bolek", "Karczmarz Bolek"))
    assert entries and not any(e["type"] in ("weapon", "armor") for e in entries)


def test_general_merchant_covers_all_kinds():
    c = _shop_conn()
    entries = shop_service._default_stock_for_npc(c, _npc(c, "kupiec_ogolny", "Kupiec", location="miasto"))
    assert {"item", "consumable", "weapon", "armor"} <= {e["type"] for e in entries}


def test_test_fixtures_never_reach_a_shop_window():
    c = _shop_conn()
    for key, label, crafter in (("kupiec_y", "Kupiec", 0), ("kowal_y", "Kowal", 1)):
        entries = shop_service._default_stock_for_npc(
            c, _npc(c, key, label, is_crafter=crafter, location="miasto")
        )
        assert not any(e["key"].startswith("test_") for e in entries)


def test_healer_and_innkeeper_do_not_sell_ammunition():
    """Amunicja jest w katalogu „konsumowalna" — zielarka nie handluje strzałami."""
    c = _shop_conn()
    c.execute("INSERT INTO game_items VALUES ('arrows','consumable',1,1)")
    c.execute("INSERT INTO game_items VALUES ('bolts','consumable',1,1)")
    c.commit()
    for key, label in (("zielarka_b", "Zielarka Basia"), ("karczmarz_c", "Karczmarz Czesiek")):
        entries = shop_service._default_stock_for_npc(c, _npc(c, key, label))
        assert not ({"arrows", "bolts"} & {e["key"] for e in entries}), (key, entries)


def test_explicit_stock_still_wins():
    c = _shop_conn()
    npc = _npc(c, "kupiec_z", "Kupiec", stock='[{"type":"item","key":"item_0"}]')
    assert shop_service._effective_shop_entries(c, npc) == [{"type": "item", "key": "item_0"}]
