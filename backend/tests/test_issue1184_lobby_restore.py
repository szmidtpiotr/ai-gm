"""TDD: Issue #1184 — podpiąć tryRestoreLobbySession (restore lobby MP po F5).

Frontend-only fix. Testujemy statycznie źródło JS/HTML:
- app.js MUSI wołać tryRestoreLobbySession() na ścieżce init (0 callerów = bug).
- multiplayer_ui.js nadal definiuje funkcję i persystuje aigm_lobby_id (backward compat).
- ?v= na multiplayer_ui.js musi być podbity (cache-bust).
"""
import os
import re

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# Host repo: <root>/frontend/front. W kontenerze backendu frontend nie jest baked —
# skill docker-cp'uje pliki do /app/frontend/front, więc próbujemy obu ścieżek.
_CANDIDATES = [
    os.path.join(_ROOT, "frontend", "front"),
    "/app/frontend/front",
]
_FRONT = next((c for c in _CANDIDATES if os.path.isdir(c)), _CANDIDATES[0])
APP_JS = os.path.join(_FRONT, "js", "app.js")
MP_JS = os.path.join(_FRONT, "js", "multiplayer_ui.js")
INDEX_HTML = os.path.join(_FRONT, "index.html")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_app_init_calls_try_restore_lobby_session():
    """app.js musi wołać tryRestoreLobbySession() (przed fixem: 0 callerów)."""
    src = _read(APP_JS)
    assert "tryRestoreLobbySession(" in src, (
        "app.js nie woła tryRestoreLobbySession() — restore lobby po F5 nie zadziała"
    )


def test_restore_guarded_by_lobby_id_key():
    """Wywołanie musi być gejtowane obecnością aigm_lobby_id w localStorage."""
    src = _read(APP_JS)
    # W tym samym rejonie kodu co wywołanie ma pojawić się odczyt klucza lobby.
    idx = src.find("tryRestoreLobbySession(")
    assert idx != -1
    window = src[max(0, idx - 400): idx + 200]
    assert "aigm_lobby_id" in window, (
        "brak gejta na aigm_lobby_id wokół wywołania tryRestoreLobbySession()"
    )


def test_multiplayer_ui_version_bumped():
    """index.html musi ładować multiplayer_ui.js z nową wersją ?v= (nie stara 1173)."""
    html = _read(INDEX_HTML)
    m = re.search(r"multiplayer_ui\.js\?v=([^\"'> ]+)", html)
    assert m, "brak zawersjonowanego importu multiplayer_ui.js w index.html"
    ver = m.group(1)
    assert "1184" in ver, f"?v= nie podbite dla #1184 (jest: {ver})"


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_try_restore_function_still_defined():
    """multiplayer_ui.js nadal definiuje tryRestoreLobbySession (nie usunięta)."""
    src = _read(MP_JS)
    assert "async function tryRestoreLobbySession(" in src


def test_lobby_id_still_persisted():
    """_showLobbyScreen nadal zapisuje aigm_lobby_id (:930 w issue) — bez tego nie ma co restore'ować."""
    src = _read(MP_JS)
    assert "localStorage.setItem('aigm_lobby_id'" in src


def test_restore_clears_key_on_closed_lobby():
    """Walidacja edge: zamknięte/nieistniejące lobby → _clearLobbySession (czysty powrót do listy)."""
    src = _read(MP_JS)
    # funkcja restore musi czyścić klucz gdy lobby nie 'open' oraz w catch
    fn_start = src.find("async function tryRestoreLobbySession(")
    fn_body = src[fn_start: fn_start + 800]
    assert fn_body.count("_clearLobbySession()") >= 2, (
        "tryRestoreLobbySession musi czyścić klucz i przy zamkniętym lobby, i w catch"
    )
