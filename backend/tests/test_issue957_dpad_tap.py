"""TDD: Issue #957 — D-pad lochu: tap przycisku nie reaguje, bo setPointerCapture
na kontenerze .dungeon-nav__dirs tłumi click dzieci (kierunki + środkowy ⊕).

Bug-fix jest czysto frontendowy (DOM pointer events w frontend/front/js/app.js).
Gate deterministyczny: pobieramy SERWOWANY app.js z kontenera frontend i sprawdzamy
inwariant root-cause — setPointerCapture NIE może być wołany w pointerdown (przy tapie),
tylko po przekroczeniu progu dragu (_DPAD_DRAG_THRESHOLD), wewnątrz obsługi ruchu.

Frontend jest bind-mountowany (./frontend:/usr/share/nginx/html:ro) → edycja pliku na
hoście jest serwowana live, więc ten test przechodzi z RED na GREEN bez rebuildu.
"""
import re
import urllib.request

import pytest

APP_JS_URL = "http://frontend:80/front/js/app.js"


def _fetch_app_js():
    try:
        return urllib.request.urlopen(APP_JS_URL, timeout=10).read().decode("utf-8")
    except Exception as e:  # pragma: no cover - środowiskowe
        pytest.skip(f"nie mogę pobrać app.js z {APP_JS_URL}: {e}")


def _extract_initdpaddrag(src: str) -> str:
    """Wytnij ciało funkcji initDpadDrag() (do następnej deklaracji function na poziomie 0)."""
    start = src.index("function initDpadDrag()")
    nxt = src.find("\nfunction ", start + 1)
    return src[start: nxt if nxt != -1 else len(src)]


# ─── Test główny ─────────────────────────────────────────────────────────────

def test_setpointercapture_not_called_on_tap():
    """setPointerCapture musi być gated za progiem dragu, nie wołany przy każdym pointerdown.

    Inwariant: w ciele initDpadDrag pierwsze wystąpienie setPointerCapture pojawia się
    PO odwołaniu do _DPAD_DRAG_THRESHOLD (czyli wewnątrz logiki ruchu/dragu), a nie przed
    nim (w handlerze pointerdown). Przy bugu capture jest w pointerdown → przed progiem.
    """
    body = _extract_initdpaddrag(_fetch_app_js())

    cap = body.find("setPointerCapture")
    assert cap != -1, "setPointerCapture musi istnieć w initDpadDrag (przeciąganie D-pada)"

    thr = body.find("_DPAD_DRAG_THRESHOLD")
    assert thr != -1, "_DPAD_DRAG_THRESHOLD (próg drag vs tap) musi istnieć"

    assert cap > thr, (
        "setPointerCapture jest wołany PRZED progiem dragu — czyli przy zwykłym tapie "
        "(pointerdown). To tłumi click przycisków-dzieci. Musi być wołany dopiero po "
        "przekroczeniu _DPAD_DRAG_THRESHOLD (w obsłudze ruchu)."
    )


def test_pointerdown_handler_has_no_capture():
    """Sam handler pointerdown (do definicji onMove) nie może chwytać wskaźnika."""
    body = _extract_initdpaddrag(_fetch_app_js())
    pd = body.find("addEventListener('pointerdown'")
    if pd == -1:
        pd = body.find('addEventListener("pointerdown"')
    assert pd != -1, "handler pointerdown musi istnieć"

    onmove = body.find("onMove", pd)
    assert onmove != -1, "onMove musi być zdefiniowane wewnątrz handlera pointerdown"

    head = body[pd:onmove]
    assert "setPointerCapture" not in head, (
        "setPointerCapture nadal jest w nagłówku pointerdown (przed onMove) — tap zostanie "
        "przechwycony i click dziecka się nie odpali."
    )


# ─── Backward compatibility ──────────────────────────────────────────────────

def test_drag_still_supported():
    """Przeciąganie nadal działa: próg, capture i suppressClick (drag != tap) zachowane."""
    body = _extract_initdpaddrag(_fetch_app_js())
    assert "_DPAD_DRAG_THRESHOLD" in body, "próg dragu musi pozostać"
    assert "setPointerCapture" in body, "capture przy realnym dragu musi pozostać"
    assert "suppressClick" in body, "blokada click po realnym dragu musi pozostać"
    assert "releasePointerCapture" in body, "zwolnienie capture po dragu musi pozostać"
