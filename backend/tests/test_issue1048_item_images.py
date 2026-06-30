"""TDD: Issue #1048 — generowanie obrazków przedmiotów (backend)."""
import sqlite3
import inspect
import pytest


# ── Test 1: migracja — kolumny image_url + image_gen_prompt istnieją ─────────

def test_game_config_items_has_image_url_column():
    conn = sqlite3.connect("/data/ai_gm.db")
    cols = [row[1] for row in conn.execute("PRAGMA table_info(game_config_items)").fetchall()]
    conn.close()
    assert "image_url" in cols, "game_config_items missing image_url column (#1048)"


def test_game_config_items_has_image_gen_prompt_column():
    conn = sqlite3.connect("/data/ai_gm.db")
    cols = [row[1] for row in conn.execute("PRAGMA table_info(game_config_items)").fetchall()]
    conn.close()
    assert "image_gen_prompt" in cols, "game_config_items missing image_gen_prompt column (#1048)"


# ── Test 2: ItemPatchReq akceptuje pola obrazka ──────────────────────────────

def test_item_patch_req_accepts_image_url():
    from app.routers.admin import ItemPatchReq
    req = ItemPatchReq(image_url="/images/tiles/test.png")
    assert req.image_url == "/images/tiles/test.png"


def test_item_patch_req_accepts_image_gen_prompt():
    from app.routers.admin import ItemPatchReq
    req = ItemPatchReq(image_gen_prompt="golden sword, fantasy item icon")
    assert req.image_gen_prompt == "golden sword, fantasy item icon"


# ── Test 3: update_item ma parametry image_url + image_gen_prompt ────────────

def test_update_item_has_image_url_param():
    from app.services.admin_config import update_item
    params = list(inspect.signature(update_item).parameters.keys())
    assert "image_url" in params, "update_item missing image_url param (#1048)"


def test_update_item_has_image_gen_prompt_param():
    from app.services.admin_config import update_item
    params = list(inspect.signature(update_item).parameters.keys())
    assert "image_gen_prompt" in params, "update_item missing image_gen_prompt param (#1048)"


# ── Test 4: backward compat — stare PATCH bez image nadal działa ─────────────

def test_item_patch_req_backward_compat_no_image():
    from app.routers.admin import ItemPatchReq
    req = ItemPatchReq(label="Miecz testowy")
    assert req.label == "Miecz testowy"
    assert req.image_url is None
    assert req.image_gen_prompt is None


# ── Test 5: endpoint generowania istnieje w routerze ─────────────────────────

def test_item_generate_endpoint_exists():
    from app.routers.admin_images import router
    paths = [r.path for r in router.routes]
    assert any("/item/{key}/generate" in p for p in paths), \
        f"missing /item/{{key}}/generate endpoint (#1048); have: {paths}"
