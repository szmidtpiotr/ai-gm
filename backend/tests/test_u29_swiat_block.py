"""TDD: Issue #541 U29 — Blok [ŚWIAT] dla LLM: kandydaci z bazy zamiast zgadywania.

build_swiat_block(conn, session_flags, player_message) → str | None
"""
import json
import pytest
import sqlite3


# ---------------------------------------------------------------------------
# Helpers: minimal in-memory DB for testing
# ---------------------------------------------------------------------------

def _make_db() -> sqlite3.Connection:
    """Minimal SQLite in-memory DB with tables needed by build_swiat_block."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE world_hexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q INTEGER NOT NULL,
            r INTEGER NOT NULL,
            hex_type TEXT NOT NULL DEFAULT 'plains',
            label TEXT,
            atmosphere TEXT,
            encounter_chance REAL NOT NULL DEFAULT 0.15,
            encounter_pool TEXT NOT NULL DEFAULT '[]',
            location_key TEXT,
            is_active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL,
            description TEXT,
            parent_id INTEGER,
            location_type TEXT DEFAULT 'macro',
            rules TEXT,
            is_active INTEGER DEFAULT 1,
            approved INTEGER DEFAULT 1,
            world_hex_q INTEGER,
            world_hex_r INTEGER,
            terrain_tags TEXT NOT NULL DEFAULT '[]',
            location_subtype TEXT,
            biome TEXT
        );

        CREATE TABLE location_npc_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_key TEXT NOT NULL,
            npc_key TEXT NOT NULL,
            assignment_type TEXT NOT NULL DEFAULT 'resident',
            notes TEXT,
            is_active INTEGER NOT NULL DEFAULT 1
        );
    """)
    return conn


def _insert_hex(conn, q, r, hex_type="plains", label=None, location_key=None):
    conn.execute(
        "INSERT INTO world_hexes (q, r, hex_type, label, location_key) VALUES (?,?,?,?,?)",
        (q, r, hex_type, label or f"Hex {q},{r}", location_key),
    )
    conn.commit()


def _insert_location(conn, key, label, q=None, r=None, placement="floating",
                     location_subtype=None, biome=None, description=None):
    """#1525: „osadzona" wynika z kotwicy q/r (lustro kanonu), nie z kolumny."""
    conn.execute(
        """INSERT INTO game_locations
           (key, label, description, world_hex_q, world_hex_r, location_subtype, biome)
           VALUES (?,?,?,?,?,?,?)""",
        (key, label, description, q, r, location_subtype, biome),
    )
    conn.commit()


def _insert_npc_assignment(conn, location_key, npc_key, assignment_type="resident"):
    conn.execute(
        "INSERT INTO location_npc_assignments (location_key, npc_key, assignment_type) VALUES (?,?,?)",
        (location_key, npc_key, assignment_type),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Import helper — expected to FAIL before implementation
# ---------------------------------------------------------------------------

def _import_build_swiat_block():
    from app.services.location_context_injector import build_swiat_block
    return build_swiat_block


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBuildSwiatBlock:

    def test_swiat_block_no_hex(self):
        """Brak current_hex w session_flags → funkcja zwraca None."""
        build_swiat_block = _import_build_swiat_block()
        conn = _make_db()
        result = build_swiat_block(conn, session_flags={}, player_message="")
        assert result is None, "Brak current_hex → powinno zwrócić None"

    def test_swiat_block_with_hex_no_location(self):
        """Hex bez lokacji → blok zawiera hex coords i typ terenu, brak sekcji LOKACJE."""
        build_swiat_block = _import_build_swiat_block()
        conn = _make_db()
        _insert_hex(conn, 3, 5, hex_type="forest", label="Gęsty Las")
        flags = {"current_hex": {"q": 3, "r": 5}}

        result = build_swiat_block(conn, session_flags=flags, player_message="")

        assert result is not None, "Hex w DB → blok nie powinien być None"
        assert "3" in result and "5" in result, "Blok musi zawierać współrzędne q=3, r=5"
        assert "forest" in result or "las" in result.lower() or "Gęsty Las" in result, \
            "Blok musi zawierać typ terenu lub etykietę hexa"
        assert "LOKACJE" not in result or "brak lokacji" in result.lower() or \
               "lokacje" not in result.lower(), \
            "Brak lokacji na hexie — sekcja LOKACJE nie powinna wymieniać żadnej lokacji"

    def test_swiat_block_with_location(self):
        """Hex z osadzoną lokacją → blok zawiera key i label lokacji."""
        build_swiat_block = _import_build_swiat_block()
        conn = _make_db()
        _insert_hex(conn, 1, 2, hex_type="plains", label="Równiny")
        _insert_location(conn, "karczma_varen", "Karczma Pod Wisielcem",
                         q=1, r=2, placement="placed",
                         location_subtype="tavern", biome="urban",
                         description="Stara karczma przy trakcie.")
        flags = {"current_hex": {"q": 1, "r": 2}}

        result = build_swiat_block(conn, session_flags=flags, player_message="")

        assert result is not None
        assert "karczma_varen" in result, "Blok musi zawierać key lokacji"
        assert "Karczma Pod Wisielcem" in result, "Blok musi zawierać label lokacji"

    def test_swiat_block_with_npc(self):
        """Lokacja z NPC w location_npc_assignments → NPC widoczny w bloku z rolą."""
        build_swiat_block = _import_build_swiat_block()
        conn = _make_db()
        _insert_hex(conn, 0, 0, hex_type="plains")
        _insert_location(conn, "tavern_a", "Tawerna Złoty Kielich",
                         q=0, r=0, placement="placed", location_subtype="tavern")
        _insert_npc_assignment(conn, "tavern_a", "karczmarz_jan", assignment_type="merchant")

        flags = {"current_hex": {"q": 0, "r": 0}}
        result = build_swiat_block(conn, session_flags=flags, player_message="")

        assert result is not None
        assert "karczmarz_jan" in result, "NPC key musi być widoczny w bloku ŚWIAT"

    def test_swiat_block_candidates(self):
        """Gracz szuka karczmy → blok zawiera kandydata z bazy z kluczem."""
        build_swiat_block = _import_build_swiat_block()
        conn = _make_db()
        _insert_hex(conn, 5, 5, hex_type="plains", label="Skrzyżowanie")
        # Karczma floating (nie na bieżącym hexie) — kandydat
        _insert_location(conn, "karczma_pod_dębem", "Karczma Pod Dębem",
                         q=5, r=6, placement="placed",
                         location_subtype="tavern", biome="urban")
        flags = {"current_hex": {"q": 5, "r": 5}}

        result = build_swiat_block(conn, session_flags=flags,
                                   player_message="Szukam karczmy gdzie mógłbym się zatrzymać")

        assert result is not None
        assert "karczma_pod_dębem" in result, \
            "Kandydat z bazy (karczma) musi pojawić się w bloku gdy gracz szuka karczmy"

    def test_swiat_block_brak_dopasowania(self):
        """Gracz szuka karczmy, brak karczm w bazie → brak_dopasowania: true w bloku."""
        build_swiat_block = _import_build_swiat_block()
        conn = _make_db()
        _insert_hex(conn, 2, 3, hex_type="forest", label="Las Mroczny")
        # Tylko kowalnia, bez karczmy
        _insert_location(conn, "kowalnia_x", "Kowalnia Zagubiona",
                         q=2, r=3, placement="placed",
                         location_subtype="smithy", biome="urban")
        flags = {"current_hex": {"q": 2, "r": 3}}

        result = build_swiat_block(conn, session_flags=flags,
                                   player_message="Szukam karczmy")

        assert result is not None
        assert "brak_dopasowania" in result, \
            "Gdy brak kandydatów pasujących do intencji → musi być 'brak_dopasowania' w bloku"

    def test_swiat_block_floating_candidate(self):
        """Gracz szuka karczmy, karczma jest floating (niezakotwiczona) → Wariant 2:
        floating liczy się jako kandydat, brak_dopasowania NIE pojawia się."""
        build_swiat_block = _import_build_swiat_block()
        conn = _make_db()
        _insert_hex(conn, 10, 10, hex_type="plains", label="Otwarta równina")
        # Karczma floating — niezakotwiczona (brak world_hex_q/r)
        _insert_location(conn, "karczma_floating", "Karczma Wędrowna",
                         placement="floating", location_subtype="tavern")
        flags = {"current_hex": {"q": 10, "r": 10}}

        result = build_swiat_block(conn, session_flags=flags,
                                   player_message="Szukam karczmy")

        assert result is not None
        assert "karczma_floating" in result, \
            "Floating karczma musi pojawić się jako kandydat (Wariant 2)"
        assert "brak_dopasowania" not in result, \
            "Gdy floating kandydat istnieje, brak_dopasowania NIE powinno się pojawić"
        assert "nieosadzona" in result or "pula" in result, \
            "Floating kandydat musi być oznaczony jako nieosadzony (nie mylić z placed)"

    def test_swiat_block_token_cap(self):
        """Bogaty kontekst → blok nie przekracza ~400 tokenów (≈1600 znaków)."""
        build_swiat_block = _import_build_swiat_block()
        conn = _make_db()
        _insert_hex(conn, 0, 0, hex_type="urban", label="Miasto")
        # Dużo lokacji na hexie
        for i in range(20):
            _insert_location(conn, f"loc_{i}", f"Lokacja numer {i} w mieście z bardzo długim opisem",
                             q=0, r=0, placement="placed", location_subtype="tavern",
                             description="Opis " * 30)
            _insert_npc_assignment(conn, f"loc_{i}", f"npc_{i}_a")
            _insert_npc_assignment(conn, f"loc_{i}", f"npc_{i}_b")
        flags = {"current_hex": {"q": 0, "r": 0}}

        result = build_swiat_block(conn, session_flags=flags, player_message="")

        assert result is not None
        # ~400 tokenów ≈ 1600 znaków (1 token ≈ 4 znaki)
        assert len(result) <= 2000, \
            f"Blok jest za długi: {len(result)} znaków (maks ~2000). Cap tokenów nie działa."


class TestContextInjectorPlayerMessage:
    """Testy że ContextInjector.build() przyjmuje player_message i przekazuje go dalej."""

    def test_build_accepts_player_message_kwarg(self):
        """ContextInjector.build() musi akceptować player_message jako keyword argument."""
        from app.services.context_injector import ContextInjector
        import inspect
        sig = inspect.signature(ContextInjector.build)
        assert "player_message" in sig.parameters, \
            "ContextInjector.build() musi mieć parametr 'player_message'"

    def test_build_world_block_uses_session_flags(self):
        """_build_world_block musi przyjmować session_flags zamiast location dict."""
        from app.services.context_injector import ContextInjector
        import inspect
        sig = inspect.signature(ContextInjector._build_world_block)
        params = list(sig.parameters.keys())
        # Must have session_flags, NOT location as first meaningful param
        assert "session_flags" in params, \
            "_build_world_block musi mieć parametr 'session_flags' dla danych hex z U29"
