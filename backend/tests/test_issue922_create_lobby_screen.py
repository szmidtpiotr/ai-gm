"""TDD: Issue #922 — GF2 create-lobby-screen HTML structure verification.

Sprawdza że frontend serwuje index.html z pełnym ekranem create-lobby-screen
i wszystkimi wymaganymi IDs odczytywanymi przez multiplayer_ui.js.
"""
import re
import requests
import pytest

FRONTEND_URL = "http://frontend:80"
REQUIRED_IDS = [
    "create-lobby-screen",
    "lobby-mode-ai",
    "lobby-mode-prebuilt",
    "lobby-name-section",
    "lobby-title",
    "lobby-template-section",
    "lobby-template-list",
    "lobby-tpl-summary",
    "lobby-timer",
    "lobby-timer-hint",
    "lobby-max-players",
    "create-lobby-error",
    "create-lobby-back",
]

REQUIRED_CLASSES_IN_SCREEN = [
    "lf-create-btn",
    "lf-tile",
    "lf-chip",
]

REQUIRED_DATA_ATTRS = [
    'data-minutes="60"',
    'data-minutes="1440"',
    'data-players="2"',
    'data-players="4"',
]


@pytest.fixture(scope="module")
def index_html():
    resp = requests.get(f"{FRONTEND_URL}/", timeout=5)
    assert resp.status_code == 200, f"Frontend returned {resp.status_code}"
    return resp.text


def test_create_lobby_screen_is_screen_div(index_html):
    """create-lobby-screen must exist as a proper .screen div."""
    assert 'id="create-lobby-screen"' in index_html
    assert "create-lobby-screen" in index_html


def test_all_required_ids_present(index_html):
    """All IDs read by multiplayer_ui.js must be present."""
    missing = [id_ for id_ in REQUIRED_IDS if f'id="{id_}"' not in index_html]
    assert not missing, f"Missing IDs: {missing}"


def test_timer_chip_data_attrs_present(index_html):
    """Timer chips with data-minutes must exist."""
    missing = [attr for attr in REQUIRED_DATA_ATTRS if attr not in index_html]
    assert not missing, f"Missing data-attrs: {missing}"


def test_create_lobby_calls_createLobby(index_html):
    """Create button must call createLobby()."""
    assert "createLobby()" in index_html


def test_setLobbyMode_onclick_present(index_html):
    """Mode tiles must call setLobbyMode()."""
    assert "setLobbyMode('ai')" in index_html
    assert "setLobbyMode('prebuilt')" in index_html


def test_template_section_hidden_by_default(index_html):
    """lobby-template-section hidden by default — shows only in prebuilt mode."""
    pattern = r'id="lobby-template-section"[^>]*display:none'
    assert re.search(pattern, index_html), "#lobby-template-section must start hidden"


def test_lobby_timer_default_value_1440(index_html):
    """Timer default = 1440 min (24h)."""
    assert 'id="lobby-timer"' in index_html
    assert 'value="1440"' in index_html


def test_lf_create_btn_present(index_html):
    """lf-create-btn class must be present for JS query selector."""
    assert "lf-create-btn" in index_html
