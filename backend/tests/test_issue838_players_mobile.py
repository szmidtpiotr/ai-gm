"""TDD: Issue #838 — players.js mobile card-view @390px.

Weryfikuje że components.css zawiera reguły niezbędne do poprawnego
wyświetlania sekcji Gracze na telefonie (390px):
- .data-table--cards table { min-width: 0 } — karty wypełniają viewport
- .pdrawer-tabs { overflow-x } — 4 taby przewijają się w 351px szufladzie
- players.js używa data-table--cards (backward compat)
"""
import re
import urllib.request


FRONTEND = "http://frontend:80"


def _get(path):
    with urllib.request.urlopen(f"{FRONTEND}{path}", timeout=5) as r:
        return r.read().decode()


# ─── RED: reguły których jeszcze nie ma w CSS ────────────────────────────────

def test_datatable_cards_overrides_min_width():
    """Card-view table musi mieć min-width:0 — bez tego 560px tabela overflow na 390px."""
    css = _get("/admin/shared/components.css")
    # Selector samodzielny (nie lista multi-selector), z min-width: 0
    pattern = r'\.data-table--cards table\s*\{\s*[^}]*min-width:\s*0'
    assert re.search(pattern, css, re.DOTALL), (
        "Brak: .data-table--cards table { min-width: 0 } — "
        "tabela overflow 560px na 390px ekranie nawet w trybie card-view"
    )


def test_pdrawer_tabs_have_overflow_x():
    """pdrawer-tabs musi mieć overflow-x — 4 taby w 351px (90vw @ 390px) muszą się przewijać."""
    css = _get("/admin/shared/components.css")
    # Szukaj bloku pdrawer-tabs który zawiera overflow-x (nowy, w @media)
    pattern = r'\.pdrawer-tabs\s*\{\s*[^}]*overflow-x'
    assert re.search(pattern, css, re.DOTALL), (
        "Brak: overflow-x w .pdrawer-tabs — taby mogą się urwać na wąskich ekranach"
    )


# ─── GREEN od razu: backward compat ──────────────────────────────────────────

def test_players_js_uses_cards_wrapper():
    """Backward compat: players.js musi zachować data-table--cards na wrapper tabeli."""
    js = _get("/admin/sections/players.js")
    assert "data-table--cards" in js, (
        "players.js musi używać data-table--cards na wrapper tabeli graczy"
    )
