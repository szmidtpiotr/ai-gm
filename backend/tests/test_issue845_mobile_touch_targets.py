"""TDD: Issue #845 — M4 Polish: touch targets (hamburger/stab/nav-item/btn-sm) ≥44px on mobile."""
import re
import urllib.request

# CSS served by frontend container (internal Docker network name)
CSS_URL = 'http://frontend/admin/shared/components.css'


def _read_css():
    with urllib.request.urlopen(CSS_URL, timeout=5) as r:
        return r.read().decode('utf-8')


def _mobile_blocks(css):
    """Return concatenated contents of all @media (max-width: 768px) blocks."""
    # Extract text inside each 768px media query (non-nested, best-effort)
    results = []
    for m in re.finditer(r'@media\s*\(max-width:\s*768px\)\s*\{', css):
        start = m.end()
        depth = 1
        i = start
        while i < len(css) and depth:
            if css[i] == '{':
                depth += 1
            elif css[i] == '}':
                depth -= 1
            i += 1
        results.append(css[start:i - 1])
    return '\n'.join(results)


def test_hamburger_min_44px_in_mobile():
    """Hamburger button must reach ≥44px touch target inside mobile media query."""
    css = _read_css()
    blocks = _mobile_blocks(css)
    assert '.hamburger' in blocks, (
        ".hamburger has no rule in @media(max-width:768px) — 26px touch target too small"
    )
    # Must declare min-height or padding that reaches 44px
    chunk = blocks[blocks.rfind('.hamburger'):]
    chunk = chunk[:chunk.find('}') + 1]
    has_target = 'min-height' in chunk or 'min-width' in chunk or 'padding' in chunk
    assert has_target, (
        ".hamburger found in mobile CSS but no sizing property (min-height/padding)"
    )


def test_stab_min_44px_in_mobile():
    """Stab sub-tabs must be ≥44px on mobile (currently 34px)."""
    css = _read_css()
    blocks = _mobile_blocks(css)
    # Must have a standalone .stab rule (not compound selector like .foo .stab) with min-height
    has_rule = False
    for m in re.finditer(r'(?<![a-z-])\.stab\s*\{([^}]*)\}', blocks):
        body = m.group(1)
        if 'min-height' in body or 'padding' in body:
            has_rule = True
            break
    assert has_rule, (
        ".stab rule with min-height/padding not found in @media(max-width:768px)"
    )


def test_nav_item_min_44px_in_mobile():
    """Drawer nav-item buttons must be ≥44px on mobile (currently 30px)."""
    css = _read_css()
    blocks = _mobile_blocks(css)
    # nav-item rules must exist in mobile context
    assert '.nav-item' in blocks, (
        ".nav-item not adjusted to 44px in @media(max-width:768px)"
    )


def test_btn_sm_min_44px_in_mobile():
    """btn-sm secondary buttons must be ≥44px on mobile (currently 22px)."""
    css = _read_css()
    blocks = _mobile_blocks(css)
    assert '.btn-sm' in blocks, (
        ".btn-sm not adjusted to 44px in @media(max-width:768px)"
    )


def test_no_horizontal_page_overflow_meta():
    """CSS must set overflow-x:hidden on html/body (M0-1 guard)."""
    css = _read_css()
    assert 'overflow-x' in css and 'hidden' in css, (
        "overflow-x:hidden not found in CSS — page may allow horizontal scroll"
    )


def test_section_tabs_scroll_indicator():
    """section-tabs overflow-x must be scroll or auto for swipe navigation."""
    css = _read_css()
    blocks = _mobile_blocks(css)
    # Either section-tabs itself or a parent must allow horizontal scroll
    has_scroll = (
        'section-tabs' in blocks and ('overflow-x' in blocks or 'overflow' in blocks)
    ) or (
        'section-tabs' in css and 'overflow-x: auto' in css
    )
    assert has_scroll, (
        ".section-tabs must have overflow-x:auto for mobile tab scrolling"
    )
