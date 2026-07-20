"""Encounter injection service — automated GM encounter triggering."""
import json
import random
import re
import sqlite3
import unicodedata

import structlog

from app.services.encounter_config_service import get_encounter_config

logger = structlog.get_logger()

# D7 (#382) — base chance the generic template fallback fires when it matches
# (so it isn't guaranteed every eligible turn). Scaled by the dwell multiplier.
TEMPLATE_FALLBACK_BASE_PROB = 0.5

# LB5 (#824) — enemy count scaling by party size. Starting values, tune in Sandbox.
MP_ENEMY_PER_PLAYER = 1.0   # multiplicative: count × party_size (capped)
MP_ENEMY_COUNT_CAP = 4      # max extra enemies per enemy type above solo baseline

# ── BL-A2 (#1328) — kompozycyjny generator spotkań ────────────────────────────
# Zamiast wyłącznie ręcznych szablonów: buduj spotkanie z puli wrogów pod budżet
# zagrożenia. Pula = world_scope='global' AND review_status='permanent' AND
# is_active=1 + dopasowanie terenu + pasmo poziomów. Wszystkie liczby to STARTING
# VALUES (Numbers Policy) — budżet i split strojlne z game_config_meta, wagi threat
# to stałe kodu strojone w Sandboxie. Power Score wejdzie w BL-A5 (#1332).
THREAT_W_HP = 1.0           # waga punktów życia w wartości zagrożenia wroga
THREAT_W_DPR = 2.0          # waga średnich obrażeń/turę (dpr)
THREAT_W_ATK = 1.0          # waga premii do trafienia
THREAT_W_AC = 0.5           # waga redukcji z pancerza (ac_base − 10)
THREAT_BUDGET_BASE = 30.0        # budżet zagrożenia dla power 1 (≈1 silny/2 słabych)
THREAT_BUDGET_PER_LEVEL = 25.0   # przyrost budżetu na każdy poziom bohatera powyżej 1
# BL-A5 (#1331) — budżet celuje teraz w Power Score, nie sam poziom. Domyślny
# przyrost/pkt power = przyrost/poziom (goły bohater: power≈level → parytet ze starym
# f(level); ekwipunek/rangi/czary podnoszą power → twardsze spotkanie bez skalowania
# statystyk wroga). Strojlne z game_config_meta (encounter_threat_budget_per_power).
THREAT_BUDGET_PER_POWER = 25.0
COMPOSITION_BASE_PROB = 0.5      # bazowa szansa odpalenia kompozycji (× dwell), parytet z szablonem
DEFAULT_COMPOSITION_SPLIT = 0.5  # szansa: kompozycja vs ręczny szablon (start 50/50)
# Wzorce kompozycji i ich wagi losowania (herszt wymaga ≥2 różnych tierów).
_COMPOSITION_PATTERNS = ("solo", "wataha", "herszt")
_COMPOSITION_PATTERN_WEIGHTS = (0.35, 0.40, 0.25)
_TIER_RANK = {"weak": 0, "standard": 1, "elite": 2, "boss": 3}

# ── #1345 (SMOKE-A P1) — fallback poszerzający pulę wrogów ─────────────────────
# Dane pasm poziomów mają dziury na górze skali (np. cap lvl 10 = same bossy z
# terenem → pusta / jednotierowa pula → spotkania niewygrywalne albo brak). Gdy pula
# po filtrze terenu < POOL_MIN_SIZE, poszerzaj OKNO POZIOMÓW o ±delta (do
# POOL_WIDEN_MAX_DELTA), trzymając scope='global'+permanent i teren. Dopiero gdy
# nadal za mało — LUZUJ teren (ostateczność, logowane), bo lepszy lekko nietrafiony
# teren niż pustka i zejście do legacy szablonów. STARTING VALUES (Numbers Policy),
# strojlne z game_config_meta. Content-fix (pełny bestiariusz lvl 6-10) osobno.
POOL_MIN_SIZE = 6
POOL_WIDEN_MAX_DELTA = 4

# ── BL-A3 (#1329) — pamięć spotkań anti-repeat ────────────────────────────────
# session_flags.recent_encounters = lista sygnatur ostatnich spotkań (index 0 =
# NAJNOWSZE). Sygnatura = posortowany, unikalny zestaw enemy_key ('a+b'). Kandydat
# obecny w historii → kara wagi ×penalty; sygnatura == OSTATNIA → twarda blokada
# (chyba że brak alternatyw). STARTING VALUES (Numbers Policy) — głębia i kara
# strojlne z game_config_meta (encounter_recent_depth / encounter_repeat_penalty).
RECENT_ENCOUNTER_DEPTH = 5
REPEAT_WEIGHT_PENALTY = 0.25


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFD", str(text).lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text[:48] or "enemy"


def _parse_stat(notes: str, pattern: str, default: int) -> int:
    m = re.search(pattern, notes, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except (ValueError, IndexError):
            pass
    return default


def ensure_encounter_enemies_in_db(conn: sqlite3.Connection, encounter: dict) -> dict:
    """
    For each enemy in encounter.enemies[], ensure a game_config_enemies row exists.
    Parses HP/AC/attack/damage from notes text if present.
    Creates a loot table stub if the enemy has none.
    Adds/updates enemy_key field in the enemy dict.
    Returns the (possibly mutated) encounter dict.
    """
    enemies = encounter.get("enemies") or []
    for enemy in enemies:
        name = str(enemy.get("name") or "").strip()
        if not name:
            continue
        notes = str(enemy.get("notes") or "")

        # Derive key
        existing_key = str(enemy.get("enemy_key") or "").strip()
        key = existing_key or _slugify(name)
        if not key:
            continue

        # Check if already in DB
        existing = conn.execute(
            "SELECT key FROM game_config_enemies WHERE key = ?", (key,)
        ).fetchone()

        if not existing:
            # Parse stats from notes (fallback to safe defaults)
            hp = _parse_stat(notes, r"HP\s*bazowe?\s*(\d+)", 15)
            ac = _parse_stat(notes, r"AC\s*bazowe?\s*(\d+)", 12)
            atk = _parse_stat(notes, r"atak\s*\+(\d+)", 2)
            dmg_m = re.search(r"obrażenia\s+(\d+d\d+)", notes, re.IGNORECASE)
            dmg_die = dmg_m.group(1) if dmg_m else "1d6"
            dmg_type_m = re.search(r"(\d+d\d+)\s+(fizyczne|ogień|lód|błyskawica|kwas|nekro|psycho|święte)", notes, re.IGNORECASE)
            dmg_type = dmg_type_m.group(2).lower() if dmg_type_m else "physical"
            # Map Polish damage type names
            _dmg_type_map = {
                "fizyczne": "physical", "ogień": "fire", "lód": "ice",
                "błyskawica": "lightning", "kwas": "acid",
                "nekro": "necrotic", "psycho": "psychic", "święte": "holy",
            }
            dmg_type = _dmg_type_map.get(dmg_type, dmg_type)

            count = int(enemy.get("count") or 1)
            tier = "standard"
            if hp >= 50 or count == 1:
                tier = "elite"

            loot_key = f"loot_{key}"
            conn.execute(
                """
                INSERT INTO game_config_enemies
                  (key, label, hp_base, ac_base, attack_bonus, damage_die,
                   damage_type, tier, xp_award, loot_table_key, drop_chance,
                   description, review_status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    key, name, hp, ac, atk, dmg_die, dmg_type, tier,
                    max(10, hp * 2),
                    loot_key, 1.0,
                    notes[:300] if notes else "",
                    "pending_review",
                ),
            )
            # Create a minimal loot table stub so combat engine finds it
            conn.execute(
                "INSERT OR IGNORE INTO game_config_loot_tables (key, label, gold_min, gold_max) VALUES (?,?,?,?)",
                (loot_key, f"Łupy: {name}", 1, 5),
            )
            # #1283 — auto-fill item/consumable/weapon entries (gold range above is
            # respected as-is; the populate helper only touches gold when it's 0/0).
            try:
                from app.services.world_service import _auto_populate_enemy_loot
                _auto_populate_enemy_loot(conn, key, tier, name)
            except Exception:
                pass

        enemy["enemy_key"] = key

    encounter["enemies"] = enemies
    return encounter


def maybe_inject_encounter(
    conn: sqlite3.Connection,
    campaign_id: int,
    trigger: str,
    q: int = None,
    r: int = None,
) -> bool:
    """
    Check if an encounter should fire for the given trigger event.
    Returns True if encounter was injected into session_flags.active_encounter.

    trigger values: 'hex_enter', 'n_turns', 'combat_end'
    q, r: hex coordinates of current hex (for biome/pool filtering)
    """
    try:
        # 1. Skip if active_encounter already set or in COMBAT/SKILL_TEST_PENDING state
        gs = conn.execute(
            "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not gs:
            return False
        sf = json.loads(gs["session_flags"] or "{}")
        if sf.get("active_encounter"):
            return False
        if sf.get("state") in ("COMBAT", "SKILL_TEST_PENDING"):
            return False

        # 1b. D7 (#382) — safety gate: no random encounters in safe locations
        #     (tavern/settlement marked safe_for_rest). Same hex, different
        #     narrative location — sitting in a room ≠ ambush.
        if is_encounter_blocked_by_location(conn, campaign_id):
            return False

        # 1c. Dwell decay: the longer the hero has settled in one location doing
        #     things, the lower the encounter chance (occupied, not exploring).
        try:
            _settle = int(get_encounter_config(conn=conn).get("dwell_settle_turns", 3))
        except Exception:
            _settle = 3
        dwell = dwell_chance_multiplier(sf.get("turns_at_location", 0), settle_turns=_settle)

        # 2. Get hex context for biome/pool filtering.
        #    BL-A2 (#1328): the live world_hexes column is `encounter_pool`; some
        #    test schemas use `forge_encounter_pool`. Read whichever exists so the
        #    whole injector (hex_type → composition/catalog) isn't dead when the
        #    forge column is absent (was: hard-coded forge_encounter_pool → always
        #    threw on the real DB → zero auto-encounters). forge_* still wins where
        #    present, preserving its priority.
        hex_type = None
        hex_pool = []
        if q is not None and r is not None:
            pool_col = _world_hex_pool_column(conn)
            select_cols = f"hex_type, {pool_col} AS pool_json" if pool_col else "hex_type"
            hex_row = conn.execute(
                f"SELECT {select_cols} FROM world_hexes WHERE q=? AND r=? AND is_active=1 LIMIT 1",
                (q, r),
            ).fetchone()
            if hex_row:
                hex_type = hex_row["hex_type"]
                if pool_col:
                    try:
                        hex_pool = json.loads(hex_row["pool_json"] or "[]")
                    except Exception:
                        hex_pool = []

        # 2b. PT-D4d (#1133) — kanoniczny katalog (game_config_encounters) jest
        #     nadrzędnym źródłem combatu dla danego biomu/poziomu. Gdy katalog ma
        #     pasujący rekord — rozstrzyga on ten dobór (trafi lub nie); pusty
        #     katalog → spadamy do legacy puli adventure_hooks (zero regresji).
        if hex_type:
            _cat_level = _hero_level_for_campaign(conn, campaign_id)
            # BL-A2 (#1328) — split ręczny szablon vs kompozycja (start 50/50,
            # game_config_meta). Gdy los wskaże kompozycję i pula global/permanent
            # dla terenu+pasma nie jest pusta — buduj spotkanie z wrogów; inaczej
            # (albo pusta pula) spadamy do katalogu szablonów (bez marnowania tury).
            # BL-A3 (#1329) — sygnatury ostatnich spotkań tej kampanii → anti-repeat
            # w OBU torach (kompozycja + katalog).
            recent_sigs = recent_signatures(sf)
            if random.random() < _composition_split(conn):
                try:
                    # BL-A5 (#1331) — budżet f(power); None → composer spada do f(level).
                    _hero_power = _hero_power_for_campaign(conn, campaign_id, _cat_level)
                    composed = encounter_composer(
                        conn, level=_cat_level, hex_type=hex_type,
                        recent_sigs=recent_sigs, power=_hero_power,
                    )
                except Exception:
                    composed = None
                if composed:
                    return _fire_composed_combat(
                        conn, campaign_id, sf, trigger, composed, dwell
                    )
            cat_row = None
            try:
                from app.services import encounter_catalog_service as _cat
                cat_row = _cat.draw_combat(conn, hex_type, _cat_level, recent_sigs=recent_sigs)
            except Exception:
                cat_row = None
            if cat_row is not None:
                return _fire_catalog_combat(
                    conn, campaign_id, sf, trigger, cat_row, dwell
                )

        # 3. Load candidate encounter hooks (restricted to hex pool if set, else all approved)
        if hex_pool:
            placeholders = ",".join("?" * len(hex_pool))
            rows = conn.execute(
                f"SELECT id, draft_data FROM adventure_hooks WHERE id IN ({placeholders}) AND status IN ('approved','promoted')",
                hex_pool,
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, draft_data FROM adventure_hooks WHERE draft_data LIKE '%\"encounter\"%' AND status IN ('approved','promoted') ORDER BY id",
            ).fetchall()

        # 4. Filter by trigger type, biome and player level (E13/E14 #428/#429)
        hero_level = _hero_level_for_campaign(conn, campaign_id)
        candidates = []
        for row in rows:
            try:
                dd = json.loads(row["draft_data"] or "{}")
                enc = dd.get("encounter")
                if not enc:
                    continue
                if not encounter_matches(enc, trigger=trigger, hex_type=hex_type, hero_level=hero_level):
                    continue
                prob = float(enc.get("trigger_probability") or 0.25)
                candidates.append((prob, enc, row["id"]))
            except Exception:
                continue

        # 5. Shuffle, roll each candidate (chance scaled by dwell decay), first
        #    that fires wins. No early return — fall through to the generic
        #    template fallback (step 6) when no hook candidate fires.
        random.shuffle(candidates)
        for prob, enc, hook_id in candidates:
            # U24 (#574) — gate robbery encounters: poverty threshold + 24h limit.
            # Napad nie pojawia się (nawet ostrzeżenie) gdy złoto < 50 gp lub
            # był już napad w tej kampanii w ciągu 24h realnych.
            if _is_robbery(enc) and not _robbery_allowed(conn, campaign_id, sf):
                continue
            if random.random() <= prob * dwell:
                enc = ensure_encounter_enemies_in_db(conn, enc)
                # LB5 #824 — scale enemy count by party size (tier unchanged)
                party_size = _party_size_for_campaign(conn, campaign_id)
                if enc.get("enemies"):
                    enc["enemies"] = _scale_enemy_counts(enc["enemies"], party_size)
                sf["active_encounter"] = enc
                record_encounter_signature(conn, sf, enc.get("enemies"))  # BL-A3 #1329
                conn.execute(
                    "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                    (json.dumps(sf, ensure_ascii=False), campaign_id),
                )
                conn.commit()
                logger.info(
                    "encounter_auto_injected",
                    trigger=trigger,
                    hook_id=hook_id,
                    campaign_id=campaign_id,
                    hex_type=hex_type,
                )
                return True

        return False

        # 6. D7 (#382) — fallback: no adventure_hook fired → try a GENERIC template
        #    from gameconfig_encounter_templates matched by hero level + terrain tag.
        level = _hero_level_for_campaign(conn, campaign_id)
        tmpl = select_encounter_template(conn, level=level, location_tag=hex_type)
        if tmpl:
            enc = {
                "label": tmpl.get("label"),
                "source": "template",
                "template_key": tmpl.get("key"),
                "difficulty": tmpl.get("difficulty"),
                "trigger": trigger,
                "enemies": [
                    {"enemy_key": e.get("key"), "name": e.get("key"),
                     "count": int(e.get("count") or 1)}
                    for e in tmpl.get("enemies", []) if e.get("key")
                ],
            }
            if enc["enemies"] and random.random() <= TEMPLATE_FALLBACK_BASE_PROB * dwell:
                sf["active_encounter"] = enc
                conn.execute(
                    "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
                    (json.dumps(sf, ensure_ascii=False), campaign_id),
                )
                conn.commit()
                logger.info(
                    "encounter_template_injected", trigger=trigger,
                    template_key=tmpl.get("key"), campaign_id=campaign_id,
                    level=level, hex_type=hex_type,
                )
                return True

        return False

    except Exception as exc:
        logger.warning("maybe_inject_encounter_error", error=str(exc), campaign_id=campaign_id)
        return False


def _fire_catalog_combat(
    conn: sqlite3.Connection,
    campaign_id: int,
    sf: dict,
    trigger: str,
    cat_row: dict,
    dwell: float,
) -> bool:
    """PT-D4d (#1133) — spróbuj wstrzyknąć encounter combat z katalogu.

    Waga rekordu (weight) traktowana jak dotychczasowe trigger_probability×100.
    Reguły bez zmian: gate napadu (robbery), skala dwell, skala party. Trafienie →
    active_encounter + times_used++. Zwraca True gdy encounter wstrzyknięty.
    """
    payload = cat_row.get("payload") or {}
    enc = {
        "label": payload.get("title") or cat_row.get("key"),
        "source": "catalog",
        "catalog_key": cat_row.get("key"),
        "trigger": trigger,
        "enemies": payload.get("enemies") or [],
    }
    for k in ("encounter_type", "defense_stat"):
        if payload.get(k):
            enc[k] = payload[k]
    if payload.get("scene_setup"):
        enc["description"] = payload["scene_setup"]

    # U24 (#574) — gate napadu (poverty threshold + 24h limit).
    if _is_robbery(enc) and not _robbery_allowed(conn, campaign_id, sf):
        return False

    prob = float(cat_row.get("weight") or 25.0) / 100.0
    if random.random() > prob * dwell:
        return False

    enc = ensure_encounter_enemies_in_db(conn, enc)
    party_size = _party_size_for_campaign(conn, campaign_id)
    if enc.get("enemies"):
        enc["enemies"] = _scale_enemy_counts(enc["enemies"], party_size)
    sf["active_encounter"] = enc
    record_encounter_signature(conn, sf, enc.get("enemies"))  # BL-A3 #1329
    conn.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
        (json.dumps(sf, ensure_ascii=False), campaign_id),
    )
    try:
        from app.services import encounter_catalog_service as _cat
        _cat.increment_times_used(conn, cat_row.get("key"))
    except Exception:
        pass
    conn.commit()
    logger.info(
        "encounter_catalog_injected",
        trigger=trigger,
        catalog_key=cat_row.get("key"),
        campaign_id=campaign_id,
    )
    return True


def _fire_composed_combat(
    conn: sqlite3.Connection,
    campaign_id: int,
    sf: dict,
    trigger: str,
    composed: dict,
    dwell: float,
) -> bool:
    """BL-A2 (#1328) — wstrzyknij skomponowane spotkanie (jak _fire_catalog_combat).

    Szansa odpalenia = COMPOSITION_BASE_PROB × dwell (parytet z fallbackiem szablonu).
    Wrogowie pochodzą z game_config_enemies (realne rekordy) — ensure_* jest bezpieczne
    (idempotentne). Skala liczebności #824 działa na wyniku. Zwraca True gdy wstrzyknięto.
    """
    if random.random() > COMPOSITION_BASE_PROB * dwell:
        return False
    enc = {
        "label": composed.get("label"),
        "source": "composed",
        "composition_pattern": composed.get("composition_pattern"),
        "trigger": trigger,
        "enemies": composed.get("enemies") or [],
        "threat_budget": composed.get("threat_budget"),
        "threat_spent": composed.get("threat_spent"),
    }
    enc = ensure_encounter_enemies_in_db(conn, enc)
    party_size = _party_size_for_campaign(conn, campaign_id)
    if enc.get("enemies"):
        enc["enemies"] = _scale_enemy_counts(enc["enemies"], party_size)
    sf["active_encounter"] = enc
    record_encounter_signature(conn, sf, enc.get("enemies"))  # BL-A3 #1329
    conn.execute(
        "UPDATE game_sessions SET session_flags = ? WHERE campaign_id = ?",
        (json.dumps(sf, ensure_ascii=False), campaign_id),
    )
    conn.commit()
    logger.info(
        "encounter_composed_injected",
        trigger=trigger,
        pattern=composed.get("composition_pattern"),
        campaign_id=campaign_id,
        threat_budget=composed.get("threat_budget"),
        threat_spent=composed.get("threat_spent"),
    )
    return True


def _is_robbery(enc: dict) -> bool:
    """U24 — czy kandydat to napad (robbery)."""
    try:
        from app.services.robbery_service import is_robbery_encounter
        return is_robbery_encounter(enc)
    except Exception:
        return False


def _active_char_id_for_campaign(conn: sqlite3.Connection, campaign_id: int) -> int | None:
    """ID aktywnego bohatera kampanii (do bramek napadu U24)."""
    try:
        row = conn.execute(
            "SELECT id FROM characters WHERE campaign_id = ? AND is_active = 1 "
            "ORDER BY id DESC LIMIT 1",
            (campaign_id,),
        ).fetchone()
        return int(row["id"]) if row else None
    except Exception:
        return None


def _robbery_allowed(conn: sqlite3.Connection, campaign_id: int, session_flags: dict) -> bool:
    """U24 (#574) — bramka iniekcji napadu: próg biedy + limit 24h."""
    try:
        from app.services.robbery_service import can_trigger_robbery
        char_id = _active_char_id_for_campaign(conn, campaign_id)
        if char_id is None:
            return False
        return bool(can_trigger_robbery(conn, campaign_id, char_id, session_flags).get("allowed"))
    except Exception:
        return True


def encounter_matches(enc: dict, *, trigger: str, hex_type: str | None, hero_level: int) -> bool:
    """E13/E14 (#428/#429) — does an encounter qualify for the current context?

    Gates: trigger type, biome (vs hex_type) and player level band
    (level_min/level_max). An encounter with no level bounds fits any level;
    one with no biomes fits any biome.
    """
    if not isinstance(enc, dict):
        return False
    triggers = enc.get("trigger_types") or ["hex_enter"]
    if trigger not in triggers:
        return False
    biomes = enc.get("biomes") or []
    if biomes and hex_type and hex_type not in biomes:
        return False
    # E14 — level scaling: skip too-hard (below min) and too-easy (above max).
    lvl = int(hero_level or 1)
    lmin = enc.get("level_min")
    if lmin is not None and lvl < int(lmin):
        return False
    lmax = enc.get("level_max")
    if lmax is not None and int(lmax) > 0 and lvl > int(lmax):
        return False
    return True


def is_encounter_blocked_by_location(conn: sqlite3.Connection, campaign_id: int) -> bool:
    """D7 (#382) — żadnych losowych encounterów w bezpiecznej lokacji (karczma,
    osada itp.). Gate po `safe_for_rest` bieżącej lokacji narracyjnej.

    PT-F7 #1141: safe_for_rest z lokacji wyprowadzonej z current_location_id
    (jedno źródło prawdy), nie ze starego session_flags.current_location_key.
    Minimalne zapytanie (tylko safe_for_rest), żeby było odporne na różne DB testów."""
    try:
        row = conn.execute(
            """
            SELECT gl.safe_for_rest
            FROM game_sessions gs
            JOIN game_locations gl ON gl.id = gs.current_location_id
            WHERE gs.campaign_id = ? AND gl.is_active = 1
            LIMIT 1
            """,
            (int(campaign_id),),
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    if not row:
        return False
    val = row["safe_for_rest"] if hasattr(row, "keys") else row[0]
    return bool(int(val or 0))


def dwell_chance_multiplier(turns_at_location, settle_turns: int = 3) -> float:
    """D7 (#382) — im dłużej bohater osiadł w tej samej lokacji robiąc rzeczy,
    tym niższa szansa losowego encountera (osiadł = zajęty, nie eksploruje).
    1.0 dopóki < settle_turns, potem maleje do podłogi 0.1."""
    t = int(turns_at_location or 0)
    if t < settle_turns:
        return 1.0
    extra = t - settle_turns
    return max(0.1, 1.0 - 0.18 * (extra + 1))


def _world_hex_pool_column(conn: sqlite3.Connection) -> str | None:
    """BL-A2 (#1328) — nazwa kolumny puli forge na world_hexes.

    Live DB ma `encounter_pool`; część schematów testowych ma `forge_encounter_pool`.
    Zwraca `forge_encounter_pool` gdy istnieje (zachowuje jej priorytet), inaczej
    `encounter_pool`, inaczej None (brak kolumny puli)."""
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(world_hexes)")}
    except sqlite3.OperationalError:
        return None
    if "forge_encounter_pool" in cols:
        return "forge_encounter_pool"
    if "encounter_pool" in cols:
        return "encounter_pool"
    return None


def _parse_tags(raw) -> list[str]:
    """location_tags może być JSON array albo CSV. Zwraca lowercase listę."""
    if not raw:
        return []
    try:
        v = json.loads(raw)
        if isinstance(v, list):
            return [str(x).strip().lower() for x in v if str(x).strip()]
    except Exception:
        pass
    return [t.strip().lower() for t in str(raw).split(",") if t.strip()]


def _party_levels_for_campaign(conn: sqlite3.Connection, campaign_id: int) -> list[int]:
    """G26 #807 — Levels of all active heroes in campaign."""
    try:
        rows = conn.execute(
            "SELECT sheet_json FROM characters WHERE campaign_id = ? AND is_active = 1",
            (campaign_id,),
        ).fetchall()
        levels = []
        for row in rows:
            try:
                sheet = json.loads(row["sheet_json"] or "{}")
                levels.append(max(1, int(sheet.get("level") or 1)))
            except Exception:
                levels.append(1)
        return levels or [1]
    except Exception:
        return [1]


def _party_scaling_level(levels: list[int]) -> int:
    """G26 #807 — Party scaling level: max-1 for MP (2+ heroes), solo level for solo."""
    if not levels:
        return 1
    if len(levels) >= 2:
        return max(1, max(levels) - 1)
    return levels[0]


def _hero_level_for_campaign(conn: sqlite3.Connection, campaign_id: int) -> int:
    """G26 #807 — Party scaling level: max-1 for MP (2+ heroes), solo level for solo."""
    return _party_scaling_level(_party_levels_for_campaign(conn, campaign_id))


def _party_size_for_campaign(conn: sqlite3.Connection, campaign_id: int) -> int:
    """LB5 #824 — count accepted campaign_members with an assigned hero."""
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM campaign_members "
            "WHERE campaign_id = ? AND status = 'accepted' AND character_id IS NOT NULL",
            (campaign_id,),
        ).fetchone()
        return max(1, int(row["cnt"] or 1))
    except Exception:
        return 1


def _scale_enemy_counts(enemies: list, party_size: int) -> list:
    """LB5 #824 — scale each enemy's count by party_size, capped at base + MP_ENEMY_COUNT_CAP.

    solo (party_size=1) → no change (backward compat).
    Tier/key/other fields untouched — only count scales.
    Formula: clamp(base × party_size, base, base + MP_ENEMY_COUNT_CAP).
    """
    if party_size <= 1:
        return enemies
    result = []
    for e in enemies:
        base = max(1, int(e.get("count") or 1))
        scaled = min(base * party_size, base + MP_ENEMY_COUNT_CAP)
        result.append({**e, "count": scaled})
    return result


# ── BL-A2 (#1328) — kompozycyjny generator spotkań ────────────────────────────

def _avg_die(die_str) -> float:
    """Średnia wartość rzutu kością zapisanego jako '1d6' / 'd8' / '2d4'."""
    m = re.match(r"\s*(\d*)\s*d\s*(\d+)", str(die_str or "").strip(), re.IGNORECASE)
    if not m:
        return 3.0
    n = int(m.group(1) or 1)
    faces = int(m.group(2) or 6)
    return n * (faces + 1) / 2.0


def enemy_threat_value(enemy: dict) -> float:
    """BL-A2 (#1328) — wartość zagrożenia wroga z jego statów bojowych.

    Spójna miara siły użyta przy budowaniu spotkania pod budżet: życie + średnie
    obrażenia/turę (uwzględnia damage_bonus i attacks_per_turn) + premia do trafienia
    + redukcja z pancerza. Wagi to STARTING VALUES (strojenie w Sandboxie). BL-A5
    (#1332) podmieni budżet na f(Power Score) — ta funkcja pozostaje.
    """
    hp = float(enemy.get("hp_base") or 1)
    atk = float(enemy.get("attack_bonus") or 0)
    dmg_bonus = float(enemy.get("damage_bonus") or 0)
    apt = max(1, int(enemy.get("attacks_per_turn") or 1))
    ac = float(enemy.get("ac_base") or 10)
    dpr = (_avg_die(enemy.get("damage_die")) + dmg_bonus) * apt
    armor = max(0.0, ac - 10.0)
    return round(
        hp * THREAT_W_HP + dpr * THREAT_W_DPR + atk * THREAT_W_ATK + armor * THREAT_W_AC,
        2,
    )


def _meta_float(conn: sqlite3.Connection, key: str, default: float) -> float:
    try:
        row = conn.execute(
            "SELECT value FROM game_config_meta WHERE key = ? LIMIT 1", (key,)
        ).fetchone()
    except sqlite3.OperationalError:
        return default
    if not row:
        return default
    try:
        return float(row[0])
    except (TypeError, ValueError):
        return default


def _difficulty_mult(conn: sqlite3.Connection) -> float:
    """BL-A7 (#1423) — mnożnik trudności spotkań z admina (encounter_difficulty_mult).

    Aplikowany na wynik budżetu zagrożenia (f(level)/f(power)) → jeden suwak
    steruje CAŁYM pipeline'em composera (podróż, ruch narracyjny, katalog). Clamp
    0.25–3.0 spójny z walidacją w encounter_config_service. Default 1.0 = bez zmian.
    """
    return min(3.0, max(0.25, _meta_float(conn, "encounter_difficulty_mult", 1.0)))


def threat_budget_for_level(conn: sqlite3.Connection, level: int) -> float:
    """BL-A2 (#1328) — budżet zagrożenia dla poziomu bohatera (solo baseline).

    f(level) = base + per_level × (level − 1). Skalowanie liczebności per drużyna
    (#824) działa NA wyniku kompozycji, więc budżet celuje w solo. base/per_level
    strojlne z game_config_meta. Fallback gdy Power Score niedostępny (BL-A5).
    BL-A7 (#1423): × mnożnik trudności z admina.
    """
    base = _meta_float(conn, "encounter_threat_budget_base", THREAT_BUDGET_BASE)
    per = _meta_float(conn, "encounter_threat_budget_per_level", THREAT_BUDGET_PER_LEVEL)
    return max(1.0, (base + per * (max(1, int(level or 1)) - 1)) * _difficulty_mult(conn))


def threat_budget_for_power(conn: sqlite3.Connection, power: float) -> float:
    """BL-A5 (#1331) — budżet zagrożenia dla Power Score bohatera (solo baseline).

    f(power) = base + per_power × (power − 1). Ta sama `base` co f(level), osobny
    przyrost/pkt power (encounter_threat_budget_per_power). Skalowanie liczebności
    per drużyna (#824) nadal działa NA wyniku kompozycji, więc budżet celuje w solo.
    BL-A7 (#1423): × mnożnik trudności z admina.
    """
    base = _meta_float(conn, "encounter_threat_budget_base", THREAT_BUDGET_BASE)
    per = _meta_float(conn, "encounter_threat_budget_per_power", THREAT_BUDGET_PER_POWER)
    return max(1.0, (base + per * (max(1.0, float(power or 1.0)) - 1.0)) * _difficulty_mult(conn))


def _hero_power_for_campaign(
    conn: sqlite3.Connection, campaign_id: int, fallback_level: int
) -> float | None:
    """BL-A5 (#1331) — Power Score aktywnego bohatera kampanii (solo baseline).

    Bierze bohatera o poziomie skalującym drużynę (#807: max-1 w MP, solo lvl w
    solo) — spójnie z f(level). None gdy brak bohatera / błąd → composer spada do
    f(level) (zero regresji względem BL-A2)."""
    try:
        row = conn.execute(
            "SELECT id, sheet_json FROM characters "
            "WHERE campaign_id = ? AND is_active = 1 "
            "ORDER BY CAST(COALESCE(json_extract(sheet_json,'$.level'),1) AS INTEGER) DESC, id "
            "LIMIT 1",
            (campaign_id,),
        ).fetchone()
        if not row:
            return None
        from app.services.power_service import compute_power_score
        sheet = json.loads(row["sheet_json"] or "{}")
        return compute_power_score(conn, int(row["id"]), sheet)["score"]
    except Exception:
        return None


def _composition_split(conn: sqlite3.Connection) -> float:
    """Szansa wyboru kompozycji zamiast ręcznego szablonu (start 50/50)."""
    v = _meta_float(conn, "encounter_composition_split", DEFAULT_COMPOSITION_SPLIT)
    return min(1.0, max(0.0, v))


# ── BL-A3 (#1329) — sygnatury i pamięć spotkań ───────────────────────────────

def encounter_signature(enemies) -> str:
    """Sygnatura spotkania = posortowany, unikalny zestaw enemy_key ('a+b').

    Fallback do `name` gdy brak enemy_key (spotkania szablonowe przed ensure_*).
    Pusta lista / brak kluczy → '' (nie zapisywana do historii)."""
    keys = sorted({
        str((e.get("enemy_key") or e.get("name") or "")).strip()
        for e in (enemies or [])
        if (e.get("enemy_key") or e.get("name"))
    })
    return "+".join(k for k in keys if k)


def _recent_depth(conn: sqlite3.Connection) -> int:
    return max(1, int(_meta_float(conn, "encounter_recent_depth", RECENT_ENCOUNTER_DEPTH)))


def _repeat_penalty(conn: sqlite3.Connection) -> float:
    return min(1.0, max(0.0, _meta_float(conn, "encounter_repeat_penalty", REPEAT_WEIGHT_PENALTY)))


def recent_signatures(sf: dict) -> list[str]:
    """Lista sygnatur ostatnich spotkań z session_flags (index 0 = najnowsze)."""
    v = (sf or {}).get("recent_encounters")
    return [str(x) for x in v if x] if isinstance(v, list) else []


def record_encounter_signature(conn: sqlite3.Connection, sf: dict, enemies) -> None:
    """Dopisz sygnaturę spotkania na początek historii, przytnij do głębi.

    Mutuje `sf` (bez zapisu do DB — robi to wywołujący w tym samym UPDATE, dzięki
    czemu pamięć nie wycieka między kampaniami: żyje w session_flags danej kampanii)."""
    sig = encounter_signature(enemies)
    if not sig:
        return
    hist = recent_signatures(sf)
    hist.insert(0, sig)
    sf["recent_encounters"] = hist[: _recent_depth(conn)]


def _build_penalty_map(recent_sigs: list[str], penalty: float) -> dict[str, float]:
    """BL #1369 — mapa key→mnożnik wagi z historii spotkań. Klucz w N kolejnych
    spotkaniach dostaje karę `penalty**N` (2 powtórki z rzędu → mocniejsza kara niż
    jedna). Puste sygnatury pomijane."""
    from collections import Counter

    counts: Counter = Counter()
    for s in recent_sigs or []:
        for k in str(s).split("+"):
            k = k.strip()
            if k:
                counts[k] += 1
    return {k: penalty ** c for k, c in counts.items()}


def _penalized_choice(items: list[dict], rng, penalty_map: dict[str, float]):
    """rng.choice z karą wagi z `penalty_map` (key→mnożnik; brak = 1.0)."""
    if not items:
        return None
    weights = [float(penalty_map.get(d.get("key"), 1.0)) for d in items]
    if sum(weights) <= 0:
        weights = [1.0] * len(items)
    return rng.choices(items, weights=weights, k=1)[0]


# ── BL #1369 — słownik terenów: hex_type (world_hexes) → tag wroga (terrain_tags) ──
# `world_hexes.hex_type` używa wartości spoza słownika `terrain_tags` wrogów
# (bridge/snow/tundra/heath/lake/sea/coast/village/town/przelecz/grania). Bez
# mapowania filtr terenu na takim hexie daje PUSTKĘ → relax-to-all (śmieci +
# off-theme). Most (bridge) = pierwsza walka Piotra. Wody → `river` (jedyny tag
# wodny w słowniku wrogów). Klucz spoza mapy przechodzi bez zmian (np. 'forest').
_HEX_TYPE_TO_TERRAIN = {
    "bridge": "road",
    "przelecz": "mountain",
    "grania": "mountain",
    "snow": "plains",
    "tundra": "plains",
    "heath": "plains",
    "river": "river",
    "lake": "river",
    "sea": "river",
    "coast": "river",
    "village": "city",
    "town": "city",
    # SG-1 #1481 — nowe tereny Siwych Grań. Słownik `terrain_tags` wrogów nie zna
    # lodu ani siarki, więc mapujemy na najbliższy istniejący tag; bez tego filtr
    # terenu dawałby PUSTKĘ → relax-to-all (off-theme śmieci).
    "lodowiec": "mountain",
    "siarka": "mountain",
    "las_iglasty": "forest",
}


def _normalize_hex_terrain(hex_type: str | None) -> str | None:
    """Sprowadź `hex_type` z world_hexes do słownika `terrain_tags` wrogów (#1369).

    Nieznany/pusty → None (brak filtra terenu); znany tag przechodzi bez zmian."""
    lt = (hex_type or "").strip().lower()
    if not lt:
        return None
    return _HEX_TYPE_TO_TERRAIN.get(lt, lt)


# ── BL #1369 — guard puli: wrogowie testowi/placeholdery NIGDY do puli spotkań ──
# Rekordy z testów/importów oznaczone permanent+global zaśmiecają pulę poz. 1-2
# (Starzec, „enemy", s2_pw_*, s4_pw_*, goblin_u31). Wzór #941 (test-location
# pollution): guard po kluczu przy budowaniu puli — działa niezależnie od tego,
# czy rekord został w DB przeklasyfikowany.
_TEST_ENEMY_KEYS = {"enemy", "unknown_attacker", "old_man"}
_TEST_ENEMY_PREFIXES = ("s1_pw_", "s2_pw_", "s3_pw_", "s4_pw_", "s5_pw_")
_TEST_ENEMY_SUFFIX_RE = re.compile(r"_u\d+$")


def _is_test_enemy_key(key: str | None) -> bool:
    """True dla kluczy testowych/placeholderów, których nie wolno losować w grze."""
    k = (key or "").strip().lower()
    if not k:
        return False
    if k in _TEST_ENEMY_KEYS:
        return True
    if k.startswith(_TEST_ENEMY_PREFIXES):
        return True
    return bool(_TEST_ENEMY_SUFFIX_RE.search(k))


def _query_scoped_enemies(conn: sqlite3.Connection, lo: int, hi: int) -> list[dict]:
    """Wrogowie world_scope='global'+permanent+active, których pasmo poziomów
    PRZECINA okno [lo, hi]. NULL min/max = brak ograniczenia z danej strony.
    #1369: rekordy testowe/placeholdery odsiane guardem po kluczu."""
    rows = conn.execute(
        """
        SELECT key, label, hp_base, ac_base, attack_bonus, damage_die,
               damage_bonus, attacks_per_turn, tier, min_level, max_level,
               terrain_tags
        FROM game_config_enemies
        WHERE world_scope = 'global'
          AND review_status = 'permanent'
          AND is_active = 1
          AND (min_level IS NULL OR min_level <= ?)
          AND (max_level IS NULL OR max_level >= ?)
        """,
        (int(hi), int(lo)),
    ).fetchall()
    return [dict(r) for r in rows if not _is_test_enemy_key(r["key"])]


def _filter_by_terrain(rows: list[dict], hex_type: str | None) -> list[dict]:
    """Zostaw wrogów pasujących do terenu (pusty terrain_tags = generyczny) i policz
    `threat`. Zwraca NOWĄ listę (bezpieczne do wielokrotnego wywołania).
    #1369: `hex_type` normalizowany słownikiem terenów przed porównaniem."""
    lt = _normalize_hex_terrain(hex_type)
    out: list[dict] = []
    for r in rows:
        d = dict(r)
        tags = _parse_tags(d.get("terrain_tags"))
        if tags and lt and lt not in tags:
            continue  # ma teren, ale nie pasuje do bieżącego hexa
        d["threat"] = enemy_threat_value(d)
        out.append(d)
    return out


def _apply_pool_keys(pool: list[dict], pool_keys: set[str] | None) -> list[dict]:
    """BL-A7 (#1423) — zawęź pulę do autorskiej listy kluczy hexa (przecięcie).

    Gdy przecięcie PUSTE, ignoruj listę (zwróć pulę bez zmian) — autorska pula
    hexa jest miękkim filtrem, nie może wyzerować spotkania (parytet z zasadą
    „teren ważniejszy niż pustka")."""
    if not pool_keys:
        return pool
    filtered = [d for d in pool if d["key"] in pool_keys]
    return filtered if filtered else pool


def eligible_enemy_pool(
    conn: sqlite3.Connection, *, level: int, hex_type: str | None,
    pool_keys: set[str] | None = None,
) -> list[dict]:
    """BL-A2 (#1328) — pula wrogów do kompozycji.

    TYLKO world_scope='global' AND review_status='permanent' AND is_active=1
    (nigdy template/campaign/pending) + dopasowanie terenu (hex_type∈terrain_tags,
    pusty terrain_tags = generyczny wróg) + pasmo poziomów (min_level/max_level;
    NULL = brak ograniczenia). Każdy rekord dostaje policzone `threat`.

    #1345 (SMOKE-A P1): gdy pula < POOL_MIN_SIZE (dziura pasm — np. cap lvl 10 =
    same bossy), poszerz OKNO POZIOMÓW o ±delta (do POOL_WIDEN_MAX_DELTA) trzymając
    scope i teren; przy delta=0 i wystarczającej puli zachowanie bez zmian. Gdy
    nadal za mało po max delta — LUZUJ teren (ostateczność, logowane).

    BL-A7 (#1423): `pool_keys` (autorska pula hexa) zawęża pulę PO każdym filtrze —
    miękko (przecięcie; puste = ignoruj), by autorskie hexy trzymały klimat, nie
    kasując skalowania."""
    try:
        min_size = max(1, int(_meta_float(conn, "encounter_pool_min_size", POOL_MIN_SIZE)))
        max_delta = max(0, int(_meta_float(conn, "encounter_pool_widen_max_delta", POOL_WIDEN_MAX_DELTA)))

        best: list[dict] = []
        for delta in range(0, max_delta + 1):
            rows = _query_scoped_enemies(conn, level - delta, level + delta)
            pool = _apply_pool_keys(_filter_by_terrain(rows, hex_type), pool_keys)
            if len(pool) > len(best):
                best = pool
            if len(best) >= min_size:
                return best  # dość wrogów — teren uszanowany

        # Ostateczność: ŻADEN wróg w paśmie nie pasuje do terenu (pusto) — luzuj
        # teren, byle nie pustka (inaczej composer spada do legacy szablonów). Małą,
        # ale niepustą pulę terenową zostawiamy — teren ważniejszy niż dobicie do min.
        if not best:
            relaxed = _apply_pool_keys(
                _filter_by_terrain(
                    _query_scoped_enemies(conn, level - max_delta, level + max_delta), None
                ),
                pool_keys,
            )
            if len(relaxed) > len(best):
                logger.info(
                    "encounter_pool_terrain_relaxed",
                    level=level, hex_type=hex_type, size=len(relaxed),
                )
                best = relaxed
        return best
    except sqlite3.OperationalError:
        return []


def _enc_enemy(d: dict, count: int, rank: str | None = None) -> dict:
    e = {
        "enemy_key": d["key"],
        "name": d.get("label") or d["key"],
        "count": max(1, int(count)),
        "tier": d.get("tier") or "standard",
    }
    if rank:
        e["rank"] = rank
    return e


# ── BL-A6 (#1332) — rangi wariantów wroga w composerze ────────────────────────
# Gdy budżet zagrożenia przewyższa NAJMOCNIEJSZEGO wroga puli (pasmo/teren), composer
# podnosi RANGĘ pojedynczego wroga zamiast sięgać po wyższy tier — „najpierw ranga,
# potem wyższy tier". Progi = krotność budżet/threat najmocniejszego. STARTING VALUES
# (Numbers Policy), strojlne z game_config_meta.
RANK_VETERAN_RATIO = 1.5   # budżet ≥ 1.5× threat najmocniejszego → weteran
RANK_ELITE_RATIO = 2.0     # budżet ≥ 2.0× → elitarny


def _rank_for_budget(conn: sqlite3.Connection, budget: float, threat: float, is_pool_top: bool) -> str | None:
    """Ranga dla pojedynczego wroga, gdy jego threat mocno nie domyka budżetu.

    Tylko dla NAJMOCNIEJSZEGO wroga puli (`is_pool_top`) — inaczej composer wybrałby
    silniejszego wroga zamiast rangi. Zwraca 'elitarny'/'weteran'/None."""
    if not is_pool_top or threat <= 0:
        return None
    ratio = float(budget) / float(threat)
    elite = _meta_float(conn, "encounter_rank_elite_ratio", RANK_ELITE_RATIO)
    vet = _meta_float(conn, "encounter_rank_veteran_ratio", RANK_VETERAN_RATIO)
    if ratio >= elite:
        return "elitarny"
    if ratio >= vet:
        return "weteran"
    return None


def _pick_pattern(pool: list[dict], rng) -> str:
    """Wybierz wzorzec kompozycji; herszt wymaga ≥2 różnych tierów."""
    tiers = {d.get("tier") for d in pool}
    patterns = list(_COMPOSITION_PATTERNS)
    weights = list(_COMPOSITION_PATTERN_WEIGHTS)
    if len(tiers) < 2:
        idx = patterns.index("herszt")
        patterns.pop(idx)
        weights.pop(idx)
    return rng.choices(patterns, weights=weights, k=1)[0]


def _compose_enemies(
    conn: sqlite3.Connection, pool: list[dict], budget: float, rng, penalty_map: dict[str, float]
) -> tuple[str, list[dict]]:
    """Jedno złożenie spotkania: wybór wzorca + wrogów. Kara wagi z `penalty_map`
    (BL-A3 #1329, eskalacja #1369) dla wrogów obecnych w historii przy losowanych
    wyborach. Zwraca (pattern, enemies)."""
    pattern = _pick_pattern(pool, rng)
    pool_top_threat = max((d["threat"] for d in pool), default=0.0)  # BL-A6

    if pattern == "solo":
        # wróg najbliższy budżetowi (górny pułap 1.25×), preferuj mocniejszych
        fits = [d for d in pool if d["threat"] <= budget * 1.25]
        base_pool = fits or pool
        top = sorted(base_pool, key=lambda d: d["threat"], reverse=True)[:4]
        chosen = _penalized_choice(top, rng, penalty_map) or max(
            base_pool, key=lambda d: d["threat"]
        )
        # BL-A6 (#1332): budżet mocno przewyższa najmocniejszego → ranga zamiast tieru.
        rank = _rank_for_budget(
            conn, budget, float(chosen["threat"]),
            is_pool_top=float(chosen["threat"]) >= pool_top_threat,
        )
        enemies = [_enc_enemy(chosen, 1, rank)]

    elif pattern == "wataha":
        # słabsza połowa puli → gromada 2–4 tego samego wroga pod budżet
        weaker = sorted(pool, key=lambda d: d["threat"])[: max(1, len(pool) // 2)]
        base = _penalized_choice(weaker, rng, penalty_map) or weaker[0]
        n = int(round(budget / max(1.0, base["threat"])))
        n = min(4, max(2, n))
        enemies = [_enc_enemy(base, n)]

    else:  # herszt + poplecznicy
        by_tier = sorted(pool, key=lambda d: (_TIER_RANK.get(d.get("tier"), 1), d["threat"]))
        leader = by_tier[-1]  # najwyższy tier/threat
        minion_pool = [
            d for d in pool
            if _TIER_RANK.get(d.get("tier"), 1) < _TIER_RANK.get(leader.get("tier"), 1)
        ] or [d for d in pool if d["key"] != leader["key"]]
        if not minion_pool:
            leader_rank = _rank_for_budget(
                conn, budget, float(leader["threat"]),
                is_pool_top=float(leader["threat"]) >= pool_top_threat,
            )
            enemies = [_enc_enemy(leader, 1, leader_rank)]
        else:
            minion = _penalized_choice(minion_pool, rng, penalty_map) or minion_pool[0]
            remaining = max(0.0, budget - leader["threat"])
            # #1377 (residuum #1346): ilu poplecznikow MIEŚCI się w budżecie. Floor,
            # nie round — nigdy nie przekraczaj budżetu (dawne max(2,·) dokładało 2
            # poplecznikow nawet gdy boss-lider sam zżarł cały budżet → spotkanie nie
            # do wygrania dla squishy bohatera).
            affordable = int(remaining // max(1.0, minion["threat"]))
            # BL-A6: herszt (najmocniejszy) dostaje rangę, gdy sam budżet lidera go nie domyka.
            leader_rank = _rank_for_budget(
                conn, budget, float(leader["threat"]),
                is_pool_top=float(leader["threat"]) >= pool_top_threat,
            )
            if affordable < 2:
                # lider (często boss) zżera budżet → herszt degeneruje do samotnego
                # lidera zamiast dokładać poplecznika ponad budżet.
                enemies = [_enc_enemy(leader, 1, leader_rank)]
            else:
                n = min(3, affordable)
                enemies = [_enc_enemy(leader, 1, leader_rank), _enc_enemy(minion, n)]

    return pattern, enemies


def encounter_composer(
    conn: sqlite3.Connection,
    *,
    level: int,
    hex_type: str | None,
    rng=random,
    recent_sigs: list[str] | None = None,
    power: float | None = None,
    pool_keys: set[str] | None = None,
) -> dict | None:
    """BL-A2 (#1328) — złóż spotkanie z puli wrogów pod budżet zagrożenia.

    Wzorce: `solo` (1 wróg ~budżet), `wataha` (2–4 × ten sam), `herszt+poplecznicy`
    (1 wyższy tier + 2–3 niżsi). Zwraca dict `active_encounter` albo None gdy pula
    pusta. Liczebność jeszcze BEZ skalowania #824 — to robi się na wyniku.

    BL-A3 (#1329): `recent_sigs` (sygnatury ostatnich spotkań, index 0 = ostatnie)
    → kara wagi ×penalty dla wrogów z historii + twarda blokada sygnatury identycznej
    z OSTATNIM spotkaniem (chyba że brak alternatyw po kilku próbach).

    BL-A5 (#1331): `power` (Power Score bohatera) steruje budżetem — f(power) zamiast
    f(level). Pula wrogów nadal filtrowana pasmem POZIOMÓW (min/max_level), bo pasma
    to dane wroga; f(power) skaluje tylko ILE budżetu wydać. None → fallback f(level).
    """
    pool = eligible_enemy_pool(conn, level=level, hex_type=hex_type, pool_keys=pool_keys)
    if not pool:
        return None
    if power is not None:
        budget = threat_budget_for_power(conn, power)
    else:
        budget = threat_budget_for_level(conn, level)
    recent_sigs = recent_sigs or []
    last_sig = recent_sigs[0] if recent_sigs else None
    penalty = _repeat_penalty(conn)
    penalty_map = _build_penalty_map(recent_sigs, penalty)

    # BL #1369 — twardy blok po ENEMY_KEY (nie tylko sygnaturze). Przy puli ≥3
    # RÓŻNYCH kluczy odrzuć spotkanie dzielące którykolwiek klucz z OSTATNIM (blokada
    # „bandyta za bandytą", której blok sygnatury nie łapał: bandit×1 vs bandit×2 to
    # różne sygnatury). Przy puli <3 blok wyłączony — brak alternatyw.
    distinct_keys = {d["key"] for d in pool}
    last_keys = set(last_sig.split("+")) if last_sig else set()
    hard_block_keys = last_keys if len(distinct_keys) >= 3 else set()

    pattern: str | None = None
    enemies: list[dict] | None = None
    fallback: tuple[str, list[dict]] | None = None
    for _ in range(8):  # twarda blokada powtórki (sygnatura + klucz), o ile są alternatywy
        p, e = _compose_enemies(conn, pool, budget, rng, penalty_map)
        if not e:
            continue
        if fallback is None:
            fallback = (p, e)
        e_keys = {x["enemy_key"] for x in e}
        if encounter_signature(e) != last_sig and not (hard_block_keys & e_keys):
            pattern, enemies = p, e
            break
    if enemies is None:
        if not fallback:
            return None
        pattern, enemies = fallback

    # BL-A6 (#1332): ranga podnosi realny threat (hp) — uwzględnij w bookkeepingu budżetu.
    _RANK_THREAT_FACTOR = {"weteran": 1.3, "elitarny": 1.6}
    threat_spent = round(
        sum(next((d["threat"] for d in pool if d["key"] == e["enemy_key"]), 0.0)
            * e["count"] * _RANK_THREAT_FACTOR.get(e.get("rank"), 1.0)
            for e in enemies),
        2,
    )
    _lead = enemies[0]
    _lead_label = _lead["name"]
    if _lead.get("rank"):
        _lead_label = f"{_lead['rank'].capitalize()}: {_lead_label}"
    label = _lead_label if len(enemies) == 1 and _lead["count"] == 1 else "Grupa wrogów"
    logger.info(
        "encounter_composed",
        pattern=pattern,
        budget_basis="power" if power is not None else "level",
        power=round(float(power), 1) if power is not None else None,
        level=level,
        threat_budget=round(budget, 2),
        threat_spent=threat_spent,
        enemies=[f"{e['enemy_key']}×{e['count']}" for e in enemies],
    )
    return {
        "label": label,
        "source": "composed",
        "composition_pattern": pattern,
        "enemies": enemies,
        "threat_budget": round(budget, 2),
        "threat_spent": threat_spent,
        "power_score": round(float(power), 1) if power is not None else None,
    }


def match_encounter_templates(
    conn: sqlite3.Connection, *, level: int, location_tag: str | None = None
) -> list[dict]:
    """D7 (#382) — ALL generic templates matching hero level + terrain (deterministic).

    From gameconfig_encounter_templates (is_active=1) where min_level <= level <=
    max_level. Tagged templates require a matching `location_tag`; tagless templates
    are generic (eligible anywhere). Sorted by threat_total. Each result carries a
    parsed `enemies` list.
    """
    try:
        rows = conn.execute(
            "SELECT * FROM gameconfig_encounter_templates "
            "WHERE is_active = 1 AND min_level <= ? AND max_level >= ? "
            "ORDER BY COALESCE(threat_total, 0), key",
            (int(level), int(level)),
        ).fetchall()
    except sqlite3.OperationalError:
        return []

    lt = (location_tag or "").strip().lower()
    out: list[dict] = []
    for r in rows:
        tags = _parse_tags(r["location_tags"] if "location_tags" in r.keys() else None)
        if tags and (not lt or lt not in tags):
            continue  # tagged template needs a matching location
        d = dict(r)
        try:
            d["enemies"] = json.loads(r["enemies_json"] or "[]")
        except Exception:
            d["enemies"] = []
        out.append(d)
    return out


def select_encounter_template(
    conn: sqlite3.Connection, *, level: int, location_tag: str | None = None
) -> dict | None:
    """D7 (#382) — pick ONE matching template at random (for actual injection)."""
    candidates = match_encounter_templates(conn, level=level, location_tag=location_tag)
    return random.choice(candidates) if candidates else None


def _authored_pool_keys(hex_data: dict) -> set[str] | None:
    """BL-A7 (#1423) — autorska pula wrogów hexa (world_hexes.encounter_pool) jako
    zbiór kluczy, albo None gdy pusta. Akceptuje listę JSON lub CSV."""
    raw = (hex_data or {}).get("encounter_pool")
    keys: list[str] = []
    if isinstance(raw, list):
        keys = [str(k).strip() for k in raw if str(k).strip()]
    elif isinstance(raw, str) and raw.strip():
        try:
            v = json.loads(raw)
            if isinstance(v, list):
                keys = [str(k).strip() for k in v if str(k).strip()]
        except Exception:
            keys = [k.strip() for k in raw.split(",") if k.strip()]
    return set(keys) or None


def compose_travel_encounter(
    conn: sqlite3.Connection,
    campaign_id: int,
    hex_data: dict,
    *,
    rng=random,
) -> dict | None:
    """BL-A7 (#1423) — złóż SKALOWANE spotkanie dla zasadzki w podróży.

    Zamiast losować pojedynczy klucz z zaszytej puli terenowej (stary
    `hex_travel_service._pick_encounter_enemy`), używa composera BL: budżet
    zagrożenia f(Power Score) bohatera → wzorzec solo / wataha / herszt+poplecznicy.
    Teren z `hex_data.hex_type`; anty-powtórki z session_flags.recent_encounters;
    autorska pula hexa (`encounter_pool`) zawęża pulę miękko.

    Zwraca dict spotkania (`enemies` z `count`/`rank`, `label`, budżet) albo None,
    gdy pula pusta / błąd — wtedy caller zostaje przy legacy single-pick (zero
    regresji). Skalowanie liczebności per drużyna (#824) aplikowane na wyniku.

    GOTCHA (#1390): działa na PRZEKAZANYM `conn` (transakcja podróży) — żadnego
    zagnieżdżonego connect, inaczej „database is locked"."""
    try:
        level = _hero_level_for_campaign(conn, campaign_id)
        power = _hero_power_for_campaign(conn, campaign_id, level)
        hex_type = str(hex_data.get("hex_type") or "plains")
        try:
            row = conn.execute(
                "SELECT session_flags FROM game_sessions WHERE campaign_id = ? LIMIT 1",
                (campaign_id,),
            ).fetchone()
            sf = json.loads(row["session_flags"] or "{}") if row else {}
        except Exception:
            sf = {}
        recent = recent_signatures(sf)
        pool_keys = _authored_pool_keys(hex_data)
        enc = encounter_composer(
            conn, level=level, hex_type=hex_type, rng=rng,
            recent_sigs=recent, power=power, pool_keys=pool_keys,
        )
        if not enc or not enc.get("enemies"):
            return None
        # #824 — skalowanie liczebności per rozmiar drużyny (parytet z katalogiem)
        party_size = _party_size_for_campaign(conn, campaign_id)
        if party_size > 1:
            enc["enemies"] = _scale_enemy_counts(enc["enemies"], party_size)
        enc = ensure_encounter_enemies_in_db(conn, enc)
        return enc
    except Exception as exc:  # nigdy nie wysadzaj podróży — legacy fallback
        logger.warning("compose_travel_encounter_error", error=str(exc), campaign_id=campaign_id)
        return None
