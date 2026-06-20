"""TDD: Issue #837 — bugreports.js mobile card-view + drawer usable on phone."""
import os

BUGREPORTS_JS = os.path.join(os.path.dirname(__file__), "bugreports.js")
COMPONENTS_CSS = os.path.join(os.path.dirname(__file__), "components.css")


def _read(path):
    with open(os.path.abspath(path), encoding="utf-8") as f:
        return f.read()


# ─── Test główny: bugreports.js ma klasę br-obs-td ─────────────────────────

def test_bugreports_obs_td_has_mobile_class():
    """Kolumna Obserwacja musi mieć class='br-obs-td' żeby CSS override na mobile działał."""
    src = _read(BUGREPORTS_JS)
    assert "br-obs-td" in src, (
        "bugreports.js: td Obserwacja musi zawierać class='br-obs-td' "
        "dla CSS override max-width/white-space na mobile"
    )


# ─── Test główny: components.css ma mobile override dla #br-drawer ─────────

def test_components_css_has_br_drawer_mobile_override():
    """CSS musi overrideować #br-drawer padding i resize na mobile."""
    css = _read(COMPONENTS_CSS)
    assert "#br-drawer" in css, (
        "components.css: brak reguły #br-drawer w sekcji mobile "
        "(padding/resize override dla drawer na 390px)"
    )


def test_components_css_has_br_obs_td_mobile_override():
    """CSS musi overrideować .br-obs-td (white-space/max-width) na mobile."""
    css = _read(COMPONENTS_CSS)
    assert ".br-obs-td" in css, (
        "components.css: brak reguły .br-obs-td — max-width:240px i white-space:nowrap "
        "blokują card-view na mobile"
    )


# ─── Backward compat: tabela nadal ma .data-table--cards ───────────────────

def test_bugreports_api_key_compat():
    """Frontend musi obsługiwać oba klucze: d.reports (aktualny) i d.items (przyszły/legacy)."""
    src = _read(BUGREPORTS_JS)
    assert "d.items || d.reports" in src or "d.reports || d.items" in src, (
        "bugreports.js: brak obsługi klucza 'd.reports' z API — "
        "API zwraca {reports:[...]} ale frontend szukał tylko d.items"
    )


def test_bugreports_table_still_has_cards_class():
    """Tabela musi nadal mieć wrapper .data-table--cards (istniejące card-view CSS)."""
    src = _read(BUGREPORTS_JS)
    assert "data-table--cards" in src, (
        "bugreports.js: wrapper tabeli utracił klasę .data-table--cards "
        "— card-view na mobile przestałoby działać"
    )


def test_bugreports_table_has_data_labels():
    """Wszystkie kolumny danych muszą mieć data-label (wymagane przez .data-table--cards CSS)."""
    src = _read(BUGREPORTS_JS)
    for label in ["Data", "Gracz", "Obserwacja", "GitHub", "Status"]:
        assert f'data-label="{label}"' in src, (
            f"bugreports.js: brak data-label='{label}' na <td> — "
            f"card-view nie wyświetli etykiety"
        )
