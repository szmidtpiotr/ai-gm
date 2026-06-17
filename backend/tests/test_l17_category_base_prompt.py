"""L17 (#723): per-category image base prompt overrides global furniture BASE_PROMPT."""
from app.routers.dungeon_tiles import _build_prompt, BASE_PROMPT


def test_empty_base_falls_back_to_global():
    tile = {"image_gen_prompt": "spooky scene"}
    out = _build_prompt(tile, "cat style", "")
    assert out.startswith(BASE_PROMPT)
    assert "cat style" in out
    assert "spooky scene" in out


def test_category_base_replaces_global():
    tile = {"image_gen_prompt": "stalactite chamber"}
    cave_base = "natural rocky cave floor, NO forced furniture"
    out = _build_prompt(tile, "cave style", cave_base)
    assert out.startswith(cave_base)
    assert BASE_PROMPT not in out          # global furniture base must be gone
    assert "elaborate furniture" not in out
    assert "cave style" in out
    assert "stalactite chamber" in out


def test_whitespace_only_base_falls_back():
    out = _build_prompt({"image_gen_prompt": "x"}, "", "   ")
    assert out.startswith(BASE_PROMPT)
