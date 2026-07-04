"""TDD: Issue #1185 — podgląd obrazu pokoju lochu: przycisk #dungeon-room-view-btn w index.html.

Logika (showCurrentTileImageModal + updateDungeonHUD toggle roomViewBtn.hidden + click wiring)
jest gotowa w app.js. Brakuje samego elementu <button id="dungeon-room-view-btn"> w HUD lochu,
przez co toggle to permanentny no-op. Test sprawdza obecność elementu w HUD + nienaruszone
podpięcie w JS.

Pliki frontendu wskazywane env-varami (docker cp do kontenera backendu, bo frontend nie jest
zbakowany w tym obrazie):
  FRONT_INDEX  — ścieżka do index.html (domyślnie /app/_front_index.html)
  FRONT_APP_JS — ścieżka do js/app.js  (domyślnie /app/_front_app.js)
"""
import os
import re

FRONT_INDEX = os.environ.get("FRONT_INDEX", "/app/_front_index.html")
FRONT_APP_JS = os.environ.get("FRONT_APP_JS", "/app/_front_app.js")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_room_view_btn_present_in_dungeon_hud():
    """Przycisk #dungeon-room-view-btn istnieje i leży wewnątrz klastra HUD lochu."""
    html = _read(FRONT_INDEX)

    assert re.search(r'id=["\']dungeon-room-view-btn["\']', html), \
        "brak elementu #dungeon-room-view-btn w index.html — toggle w updateDungeonHUD to no-op"

    idx_hud = html.find('id="dungeon-hud"')
    idx_hud_close = html.find('</span>', idx_hud)
    # zamknięcie całego klastra: ostatni </span> pary — szukamy przycisku w obrębie bloku dungeon-hud
    idx_btn = html.find('id="dungeon-room-view-btn"')
    assert idx_hud != -1, "brak kontenera #dungeon-hud"
    assert idx_btn > idx_hud, "przycisk musi być zdefiniowany wewnątrz/za otwarciem #dungeon-hud"

    # przycisk domyślnie ukryty (pokazywany dopiero gdy pokój ma obraz)
    btn_tag = html[idx_btn - 200:idx_btn + 200]
    assert "hidden" in btn_tag, "przycisk musi startować jako hidden (updateDungeonHUD go odsłania)"


# ─── Backward compatibility / wiring ─────────────────────────────────────────

def test_js_wiring_still_intact():
    """Istniejąca logika JS (toggle + click handler + modal) pozostaje nienaruszona."""
    js = _read(FRONT_APP_JS)

    # updateDungeonHUD nadal toggluje hidden na tym id
    assert "getElementById('dungeon-room-view-btn')" in js, \
        "updateDungeonHUD musi nadal odwoływać się do #dungeon-room-view-btn"
    # click handler nadal podpięty do showCurrentTileImageModal
    assert "showCurrentTileImageModal" in js, \
        "handler kliknięcia (showCurrentTileImageModal) musi istnieć"
    assert re.search(
        r"dungeon-room-view-btn['\"]\)\?\.addEventListener\(\s*['\"]click['\"]\s*,\s*showCurrentTileImageModal",
        js,
    ), "przycisk musi być podpięty pod showCurrentTileImageModal"
