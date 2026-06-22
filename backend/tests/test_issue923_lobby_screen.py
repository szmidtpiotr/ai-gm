"""TDD: Issue #923 — lobby-screen HTML containers exist in index.html."""
import os

INDEX_HTML = os.path.join(
    os.path.dirname(__file__),
    "index923_snapshot.html",
)

REQUIRED_IDS = [
    "lobby-screen",
    "lobby-screen-title",
    "lobby-screen-subtitle",
    "lobby-members-list",
    "lobby-invite-section",
    "lobby-guest-section",
    "lobby-start-section",
    "lobby-join-link-section",
    "lobby-start-btn",
    "lobby-start-hint",
    "lobby-invite-username",
    "lobby-invite-msg",
    "lobby-invite-link-box",
    "lobby-invite-link-text",
    "lobby-join-token-input",
    "lobby-join-msg",
]


def _html() -> str:
    with open(INDEX_HTML, encoding="utf-8") as f:
        return f.read()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_lobby_screen_has_all_required_ids():
    """lobby-screen i wszystkie kontenery wymagane przez _renderLobby() muszą istnieć."""
    html = _html()
    missing = [id_ for id_ in REQUIRED_IDS if f'id="{id_}"' not in html]
    assert not missing, f"Brakujące id-y w index.html: {missing}"


def test_lobby_screen_is_screen_div():
    """#lobby-screen musi być divem z klasą 'screen'."""
    html = _html()
    assert 'id="lobby-screen" class="screen"' in html or \
           'id="lobby-screen"' in html and 'class="screen"' in html.split('id="lobby-screen"')[1][:60]


def test_lobby_start_btn_initially_disabled():
    """Przycisk Start musi być disabled by default (host musi zebrać ≥2 graczy)."""
    html = _html()
    idx = html.find('id="lobby-start-btn"')
    assert idx != -1, "#lobby-start-btn nie znaleziono"
    snippet = html[max(0, idx - 100):idx + 200]
    assert "disabled" in snippet, "lobby-start-btn musi mieć atrybut disabled"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_create_lobby_screen_still_exists():
    """create-lobby-screen (GF2) nadal musi istnieć po dodaniu lobby-screen."""
    html = _html()
    assert 'id="create-lobby-screen"' in html, "create-lobby-screen zniknął!"


def test_game_screen_still_exists():
    """game-screen nadal musi istnieć — lobby-screen musi być przed nim."""
    html = _html()
    assert 'id="game-screen"' in html, "game-screen zniknął!"
    # Kolejność: create-lobby → lobby → game
    pos_create = html.find('id="create-lobby-screen"')
    pos_lobby = html.find('id="lobby-screen"')
    pos_game = html.find('id="game-screen"')
    assert pos_create < pos_lobby < pos_game, \
        "Kolejność ekranów: create-lobby-screen → lobby-screen → game-screen"
