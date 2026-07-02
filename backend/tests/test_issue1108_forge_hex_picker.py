"""TDD: Issue #1108 — Kuźnia hex picker: fix scoringu auto-przydziału (teren dominuje
nad centrum) + endpoint dostępności hexów dla modala mapy.

Bug repro: szablon "Żar z Gasnącej Kuźni" wylądował na hexie snow (2,-1) bo scoring
`min_dist*10 + pref - center_dist*2` pozwalał snow blisko centrum wygrać z town daleko.
"""
import sys, os, sqlite3, pytest
sys.path.insert(0, "/app")

# ─── Helpers (reuse #1094 fixture shape) ─────────────────────────────────────

def _make_db(tmp_path):
    db = sqlite3.connect(str(tmp_path / "test.db"))
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE campaign_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'draft',
            start_hex_q INTEGER,
            start_hex_r INTEGER
        );
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q INTEGER NOT NULL,
            r INTEGER NOT NULL,
            hex_type TEXT DEFAULT 'plains',
            label TEXT DEFAULT '',
            map_level INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT,
            label TEXT,
            world_hex_q INTEGER,
            world_hex_r INTEGER,
            is_active INTEGER DEFAULT 1
        );
    """)
    return db


def _seed_world(db, hexes):
    for q, r, htype, label in hexes:
        db.execute(
            "INSERT INTO world_hexes (q, r, hex_type, label, map_level, is_active) VALUES (?,?,?,?,0,1)",
            (q, r, htype, label),
        )
    db.commit()


def _seed_location(db, q, r, label="Kopalnia"):
    db.execute(
        "INSERT INTO game_locations (key, label, world_hex_q, world_hex_r) VALUES (?,?,?,?)",
        (f"loc_{q}_{r}", label, q, r),
    )
    db.commit()


def _new_template(db, title="T"):
    db.execute("INSERT INTO campaign_templates (title, status) VALUES (?, 'review')", (title,))
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


# ─── Test 1 (GŁÓWNY / bug repro) — teren dominuje nad centrum ────────────────

def test_allocate_prefers_town_over_closer_snow(tmp_path):
    """#1108 core: snow blisko centrum NIE może wygrać z town/plains dalej od centrum.

    Dokładny scenariusz buga #1108: snow (2,-1) vs town (4,0). Stary scoring
    (min_dist*10 + pref - center_dist*2) dawał snow przewagę 1 pkt.
    """
    from app.routers.adventure_forge import _allocate_hex_for_template
    db = _make_db(tmp_path)
    _seed_world(db, [
        (2, -1, "snow", ""),   # blisko centrum (dist 2), pref 0
        (4, 0, "town", ""),    # daleko (dist 4), pref 3
    ])
    tpl_id = _new_template(db)

    result = _allocate_hex_for_template(db, tpl_id)
    assert result is not None
    assert result["hex_type"] == "town", \
        f"Preferencja terenu musi dominować nad centrum — spodziewano town, dostano {result}"
    assert (result["q"], result["r"]) == (4, 0)


def test_allocate_prefers_plains_over_swamp_and_ruins(tmp_path):
    """Wśród wolnych: plains bije swamp/ruins niezależnie od odległości od centrum."""
    from app.routers.adventure_forge import _allocate_hex_for_template
    db = _make_db(tmp_path)
    _seed_world(db, [
        (1, 0, "swamp", ""),
        (0, 1, "ruins", ""),
        (6, -3, "plains", ""),
    ])
    tpl_id = _new_template(db)

    result = _allocate_hex_for_template(db, tpl_id)
    assert result["hex_type"] == "plains", f"plains musi wygrać, dostano {result}"


# ─── Test 2 — fallback na nietypowy hex + flaga ostrzeżenia ──────────────────

def test_allocate_fallback_marks_warning_when_only_atypical(tmp_path):
    """Gdy brak town/plains — wybierz nietypowy (snow/swamp), ale oznacz is_fallback."""
    from app.routers.adventure_forge import _allocate_hex_for_template
    db = _make_db(tmp_path)
    _seed_world(db, [
        (2, -1, "snow", ""),
        (0, 1, "swamp", ""),
    ])
    tpl_id = _new_template(db)

    result = _allocate_hex_for_template(db, tpl_id)
    assert result is not None, "Musi zwrócić fallback hex, nie None (są wolne hexy)"
    assert result.get("is_fallback") is True, \
        f"Fallback na nietypowy teren musi być oznaczony is_fallback=True — {result}"


def test_allocate_preferred_not_marked_fallback(tmp_path):
    """Gdy wybrano town/plains — is_fallback nieustawione/False."""
    from app.routers.adventure_forge import _allocate_hex_for_template
    db = _make_db(tmp_path)
    _seed_world(db, [(1, 0, "town", ""), (2, -1, "snow", "")])
    tpl_id = _new_template(db)

    result = _allocate_hex_for_template(db, tpl_id)
    assert result["hex_type"] == "town"
    assert not result.get("is_fallback"), "town nie jest fallbackiem"


# ─── Test 3 (backward compat) — twarde wykluczenia nadal działają ────────────

def test_hard_exclusions_still_hold(tmp_path):
    """#1094 kontrakt: label POI / game_location / start innego szablonu — pomijane."""
    from app.routers.adventure_forge import _allocate_hex_for_template
    db = _make_db(tmp_path)
    _seed_world(db, [
        (0, 0, "town", "Vilnograd"),   # named POI → excluded
        (1, 0, "plains", ""),          # occupied by location → excluded
        (5, 5, "town", ""),            # free town → winner
    ])
    _seed_location(db, 1, 0)
    tpl_id = _new_template(db)

    result = _allocate_hex_for_template(db, tpl_id)
    assert (result["q"], result["r"]) == (5, 5), \
        f"Musi pominąć POI i lokację, wybrać (5,5) — dostano {result}"


def test_allocate_returns_none_when_no_free(tmp_path):
    """Brak wolnych hexów → None (caller robi 422)."""
    from app.routers.adventure_forge import _allocate_hex_for_template
    db = _make_db(tmp_path)
    _seed_world(db, [(0, 0, "town", "Vilnograd")])  # named → excluded
    tpl_id = _new_template(db)
    assert _allocate_hex_for_template(db, tpl_id) is None


# ─── Test 4 — endpoint dostępności hexów dla modala mapy ────────────────────

def test_hex_availability_classifies_hexes(tmp_path):
    """#1108 modal: _hex_availability zwraca status per hex (free_good/free_atypical/occupied)."""
    from app.routers.adventure_forge import _hex_availability
    db = _make_db(tmp_path)
    _seed_world(db, [
        (1, 0, "town", ""),            # free_good
        (2, 0, "snow", ""),            # free_atypical
        (3, 0, "plains", "Wachstein"), # occupied (label)
        (4, 0, "forest", ""),          # occupied (location)
    ])
    _seed_location(db, 4, 0)
    other_tpl = _new_template(db, "Inny")
    db.execute("UPDATE campaign_templates SET start_hex_q=5, start_hex_r=0 WHERE id=?", (other_tpl,))
    _seed_world(db, [(5, 0, "town", "")])  # occupied (start innego szablonu)
    db.commit()
    my_tpl = _new_template(db, "Mój")

    hexes = _hex_availability(db, my_tpl)
    by_qr = {(h["q"], h["r"]): h for h in hexes}

    assert by_qr[(1, 0)]["status"] == "free_good"
    assert by_qr[(2, 0)]["status"] == "free_atypical"
    assert by_qr[(3, 0)]["status"] == "occupied"
    assert by_qr[(4, 0)]["status"] == "occupied"
    assert by_qr[(5, 0)]["status"] == "occupied", "start innego szablonu = zajęty"
    # marker startów innych szablonów
    assert by_qr[(5, 0)].get("is_template_start") is True


def test_hex_availability_marks_own_current_start(tmp_path):
    """Aktualny start edytowanego szablonu oznaczony is_current."""
    from app.routers.adventure_forge import _hex_availability
    db = _make_db(tmp_path)
    _seed_world(db, [(1, 0, "town", ""), (2, 0, "plains", "")])
    tpl_id = _new_template(db)
    db.execute("UPDATE campaign_templates SET start_hex_q=1, start_hex_r=0 WHERE id=?", (tpl_id,))
    db.commit()

    hexes = _hex_availability(db, tpl_id)
    by_qr = {(h["q"], h["r"]): h for h in hexes}
    assert by_qr[(1, 0)].get("is_current") is True
    # własny aktualny start nie jest "occupied" dla samego siebie (klikalny do potwierdzenia)
    assert by_qr[(1, 0)]["status"] != "occupied"
