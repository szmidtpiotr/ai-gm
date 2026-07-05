"""TDD: Issue #1211 — Sandbox scenariuszy: deterministyczny setup sesji pod
testowany element + boczny log mechaniki.

prepare_scenario(setup) tworzy izolowaną, jednorazową sesję: klon bohatera
('[SCN] ' + __scenario_clone__), dispozycyjna kampania '[SBX-SCN]', scena
(wrogowie/NPC/flagi/godzina/lokacja) ustawiona tak, by testowany element
odpalił od pierwszej tury. get_scenario_state(campaign_id) zwraca log
mechaniki (rzuty, decyzje, zmiany stanu) pogrupowany po turach.

Izolacja: oryginalny bohater NIGDY nie jest modyfikowany; klony Combat
Sandboxa ('[SBX] ') nie są ruszane.
"""
import json
import sqlite3
import sys

sys.path.insert(0, "/app")


# ─── Hermetic in-memory DB ───────────────────────────────────────────────────

def _make_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, system_id TEXT NOT NULL, model_id TEXT NOT NULL,
            owner_user_id INTEGER NOT NULL, language TEXT DEFAULT 'pl',
            mode TEXT DEFAULT 'solo', status TEXT DEFAULT 'active',
            gm_plan_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER, user_id INTEGER, name TEXT, system_id TEXT,
            sheet_json TEXT DEFAULT '{}', location TEXT, is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            backstory TEXT, appearance TEXT, personality TEXT, motivation TEXT,
            note TEXT, gold INTEGER DEFAULT 0, gold_gp INTEGER DEFAULT 0,
            hero_status TEXT, visited_location_keys TEXT, status TEXT DEFAULT 'idle'
        );
        CREATE TABLE character_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER, item_key TEXT, weapon_key TEXT, consumable_key TEXT,
            quantity INTEGER DEFAULT 1, equipped INTEGER DEFAULT 0, slot TEXT,
            acquired_at TEXT, source TEXT, meta_json TEXT, label TEXT
        );
        CREATE TABLE character_spells (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER, spell_key TEXT, rank INTEGER DEFAULT 1,
            use_count INTEGER DEFAULT 0
        );
        CREATE TABLE game_sessions (
            id TEXT PRIMARY KEY, campaign_id INTEGER, test_run_id TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            current_location_id INTEGER, session_flags TEXT DEFAULT '{}',
            scene_enemies TEXT DEFAULT '[]', scene_npcs TEXT DEFAULT '[]',
            scene_cleared INTEGER DEFAULT 0, active_quests TEXT DEFAULT '[]',
            player_conditions TEXT DEFAULT '[]', ingame_hours INTEGER DEFAULT 9
        );
        CREATE TABLE campaign_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL, character_id INTEGER,
            user_text TEXT NOT NULL, route TEXT DEFAULT 'narrative',
            assistant_text TEXT, turn_number INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE game_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT, label TEXT, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE active_combat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER, character_id INTEGER, combat_id TEXT,
            combatants TEXT, current_turn TEXT, status TEXT DEFAULT 'active'
        );
        CREATE TABLE combat_loot (
            id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER, character_id INTEGER
        );
        CREATE TABLE dice_rolls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER, character_id INTEGER, turn_number INTEGER,
            combat_id TEXT, roll_type TEXT, actor TEXT, notation TEXT,
            raw_rolls TEXT, modifiers TEXT, total INTEGER, dc INTEGER,
            outcome TEXT, meta TEXT, created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE state_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER, character_id INTEGER, turn_number INTEGER,
            combat_id TEXT, resource TEXT, before_val TEXT, after_val TEXT,
            delta TEXT, cause TEXT, meta TEXT, created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE turn_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER, character_id INTEGER, turn_number INTEGER,
            user_text TEXT, action_type TEXT, confidence REAL, route TEXT,
            gate_blocked INTEGER, gate_reason TEXT, handler TEXT,
            correction_applied INTEGER, raw_intent TEXT, meta TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    return db


def _mk_hero(db, user_id=7, name="Tester", hp=20, gold=50):
    sheet = {
        "archetype": "warrior", "level": 2,
        "current_hp": hp, "max_hp": hp,
        "stats": {"STR": 14, "DEX": 12},
        "conditions": [],
    }
    cur = db.execute(
        "INSERT INTO characters (user_id, name, system_id, sheet_json, gold_gp, status)"
        " VALUES (?,?,?,?,?, 'idle')",
        (user_id, name, "fantasy", json.dumps(sheet), gold),
    )
    hero_id = int(cur.lastrowid)
    db.execute(
        "INSERT INTO character_inventory (character_id, weapon_key, quantity, equipped)"
        " VALUES (?, 'sword_short', 1, 1)",
        (hero_id,),
    )
    db.execute(
        "INSERT INTO character_spells (character_id, spell_key, rank) VALUES (?, 'magic_bolt', 1)",
        (hero_id,),
    )
    db.commit()
    return hero_id


# ─── prepare_scenario — test główny ──────────────────────────────────────────

def test_prepare_creates_isolated_scenario():
    """Pełny setup: klon + kampania [SBX-SCN] + scena + narracja otwierająca."""
    from app.services.scenario_service import prepare_scenario

    db = _make_db()
    hero_id = _mk_hero(db)

    res = prepare_scenario({
        "hero_id": hero_id,
        "issue_number": 1183,
        "title": "Encounter w zaułku",
        "location_name": "Zaułek w Błotsteinie",
        "scene_enemies": ["bandit", "bandit"],
        "scene_npcs": ["informator"],
        "session_flags": {"test_flag_x": True},
        "ingame_hours": 22,
        "gm_plan": {"scene_goal": "zasadzka w zaułku"},
        "opening_narration": "Stoisz w ciemnym zaułku. Dwie sylwetki odcinają wyjście.",
        "agent_notes": "issue nie precyzuje pory dnia — przyjęto noc",
    }, conn=db)

    # zwrotka
    assert res["campaign_id"] and res["character_id"]
    assert res["character_id"] != hero_id

    # kampania dispozycyjna
    camp = db.execute("SELECT * FROM campaigns WHERE id = ?", (res["campaign_id"],)).fetchone()
    assert camp["title"].startswith("[SBX-SCN]")
    assert "#1183" in camp["title"]
    assert camp["status"] == "active"
    assert json.loads(camp["gm_plan_json"])["scene_goal"] == "zasadzka w zaułku"

    # klon otagowany, przypięty do kampanii, z lokacją; inwentarz+czary skopiowane
    clone = db.execute("SELECT * FROM characters WHERE id = ?", (res["character_id"],)).fetchone()
    assert clone["name"].startswith("[SCN] ")
    assert clone["campaign_id"] == res["campaign_id"]
    assert clone["location"] == "Zaułek w Błotsteinie"
    csheet = json.loads(clone["sheet_json"])
    assert csheet["__scenario_clone__"] is True
    assert csheet["__scenario_source_id__"] == hero_id
    inv = db.execute("SELECT COUNT(*) c FROM character_inventory WHERE character_id=?",
                     (res["character_id"],)).fetchone()["c"]
    spl = db.execute("SELECT COUNT(*) c FROM character_spells WHERE character_id=?",
                     (res["character_id"],)).fetchone()["c"]
    assert inv == 1 and spl == 1

    # oryginał NIETKNIĘTY
    orig = db.execute("SELECT * FROM characters WHERE id = ?", (hero_id,)).fetchone()
    assert orig["campaign_id"] is None
    assert orig["status"] == "idle"
    assert json.loads(orig["sheet_json"]).get("__scenario_clone__") is None

    # sesja: scena + flagi + godzina + metadane scenariusza
    gs = db.execute("SELECT * FROM game_sessions WHERE campaign_id = ?",
                    (res["campaign_id"],)).fetchone()
    assert json.loads(gs["scene_enemies"]) == ["bandit", "bandit"]
    assert json.loads(gs["scene_npcs"]) == ["informator"]
    assert gs["ingame_hours"] == 22
    flags = json.loads(gs["session_flags"])
    assert flags["state"] == "NARRATIVE"
    assert flags["test_flag_x"] is True
    assert flags["__scenario__"]["issue_number"] == 1183
    assert flags["__scenario__"]["agent_notes"].startswith("issue nie precyzuje")

    # narracja otwierająca = pierwsza tura GM (grywalna rozmowa od wejścia)
    turn = db.execute("SELECT * FROM campaign_turns WHERE campaign_id = ?",
                      (res["campaign_id"],)).fetchone()
    assert turn is not None
    assert turn["turn_number"] == 1
    assert "ciemnym zaułku" in turn["assistant_text"]
    assert turn["character_id"] == res["character_id"]


def test_prepare_applies_hero_overrides():
    """hero_overrides zmieniają KLONA (hp/mana/gold/level/conditions), nie oryginał."""
    from app.services.scenario_service import prepare_scenario

    db = _make_db()
    hero_id = _mk_hero(db, hp=20, gold=50)

    res = prepare_scenario({
        "hero_id": hero_id,
        "hero_overrides": {
            "current_hp": 3,
            "level": 5,
            "gold_gp": 999,
            "conditions": ["poisoned"],
        },
    }, conn=db)

    clone = db.execute("SELECT * FROM characters WHERE id = ?", (res["character_id"],)).fetchone()
    csheet = json.loads(clone["sheet_json"])
    assert csheet["current_hp"] == 3
    assert csheet["level"] == 5
    assert csheet["conditions"] == ["poisoned"]
    assert clone["gold_gp"] == 999

    orig = db.execute("SELECT * FROM characters WHERE id = ?", (hero_id,)).fetchone()
    osheet = json.loads(orig["sheet_json"])
    assert osheet["current_hp"] == 20
    assert osheet["level"] == 2
    assert orig["gold_gp"] == 50


def test_prepare_minimal_setup_works():
    """Backward compat / minimalny kontrakt: samo hero_id wystarcza."""
    from app.services.scenario_service import prepare_scenario

    db = _make_db()
    hero_id = _mk_hero(db)

    res = prepare_scenario({"hero_id": hero_id}, conn=db)

    camp = db.execute("SELECT * FROM campaigns WHERE id = ?", (res["campaign_id"],)).fetchone()
    assert camp["title"].startswith("[SBX-SCN]")
    gs = db.execute("SELECT * FROM game_sessions WHERE campaign_id = ?",
                    (res["campaign_id"],)).fetchone()
    assert gs is not None
    assert json.loads(gs["scene_enemies"]) == []
    assert gs["ingame_hours"] == 9


def test_prepare_purges_prior_scenarios_same_user():
    """Drugi prepare sprząta poprzedni scenariusz usera (kampania + klon)."""
    from app.services.scenario_service import prepare_scenario

    db = _make_db()
    hero_id = _mk_hero(db)

    first = prepare_scenario({"hero_id": hero_id}, conn=db)
    second = prepare_scenario({"hero_id": hero_id}, conn=db)

    old_camp = db.execute("SELECT id FROM campaigns WHERE id = ?",
                          (first["campaign_id"],)).fetchone()
    old_clone = db.execute("SELECT id FROM characters WHERE id = ?",
                           (first["character_id"],)).fetchone()
    assert old_camp is None
    assert old_clone is None
    assert db.execute("SELECT id FROM campaigns WHERE id = ?",
                      (second["campaign_id"],)).fetchone() is not None


def test_prepare_leaves_combat_sandbox_clones_alone():
    """Klony Combat Sandboxa ('[SBX] ') NIE są ruszane przez scenario purge."""
    from app.services.scenario_service import prepare_scenario

    db = _make_db()
    hero_id = _mk_hero(db)
    db.execute(
        "INSERT INTO characters (user_id, name, sheet_json) VALUES (?, '[SBX] Tester', '{}')",
        (7,),
    )
    db.commit()

    prepare_scenario({"hero_id": hero_id}, conn=db)

    sbx = db.execute("SELECT id FROM characters WHERE name = '[SBX] Tester'").fetchone()
    assert sbx is not None


def test_prepare_rejects_missing_hero():
    from app.services.scenario_service import prepare_scenario, ScenarioError

    db = _make_db()
    try:
        prepare_scenario({"hero_id": 424242}, conn=db)
        assert False, "expected ScenarioError"
    except ScenarioError:
        pass


# ─── get_scenario_state — boczny log mechaniki ───────────────────────────────

def test_state_groups_mechanics_by_turn():
    """Log mechaniki: decyzje + rzuty + zmiany stanu pogrupowane po turach."""
    from app.services.scenario_service import prepare_scenario, get_scenario_state

    db = _make_db()
    hero_id = _mk_hero(db)
    res = prepare_scenario({"hero_id": hero_id, "scene_enemies": ["bandit"]}, conn=db)
    cid, char_id = res["campaign_id"], res["character_id"]

    db.execute(
        "INSERT INTO turn_decisions (campaign_id, character_id, turn_number, user_text,"
        " action_type, route, gate_blocked, handler) VALUES (?,?,2,'atakuję','attack','combat',0,'combat')",
        (cid, char_id),
    )
    db.execute(
        "INSERT INTO dice_rolls (campaign_id, character_id, turn_number, roll_type, actor,"
        " notation, total, dc, outcome) VALUES (?,?,2,'attack','player','d20+4',17,12,'success')",
        (cid, char_id),
    )
    db.execute(
        "INSERT INTO state_changes (campaign_id, character_id, turn_number, resource,"
        " before_val, after_val, delta, cause) VALUES (?,?,2,'hp','8','5','-3','enemy_hit')",
        (cid, char_id),
    )
    db.execute(
        "INSERT INTO dice_rolls (campaign_id, character_id, turn_number, roll_type, actor,"
        " notation, total, dc, outcome) VALUES (?,?,3,'skill','player','d20+2',9,12,'fail')",
        (cid, char_id),
    )
    db.commit()

    state = get_scenario_state(cid, conn=db)

    assert state["campaign"]["id"] == cid
    assert state["hero"]["id"] == char_id
    assert state["session"]["scene_enemies"] == ["bandit"]

    turns = state["mechanics"]
    t2 = next(t for t in turns if t["turn_number"] == 2)
    assert t2["decision"]["action_type"] == "attack"
    assert len(t2["dice_rolls"]) == 1
    assert t2["dice_rolls"][0]["total"] == 17
    assert len(t2["state_changes"]) == 1
    assert t2["state_changes"][0]["resource"] == "hp"
    t3 = next(t for t in turns if t["turn_number"] == 3)
    assert t3["dice_rolls"][0]["outcome"] == "fail"

    # filtr since_turn
    state2 = get_scenario_state(cid, since_turn=2, conn=db)
    nums = [t["turn_number"] for t in state2["mechanics"]]
    assert 2 not in nums and 3 in nums


# ─── draft_scenario_setup — Kreator: issue# + opis → setup przez LLM ─────────

def _mk_catalog(db):
    db.executescript("""
        CREATE TABLE game_config_enemies (
            key TEXT PRIMARY KEY, label TEXT, tier TEXT, is_active INTEGER DEFAULT 1
        );
    """)
    db.execute("INSERT INTO game_config_enemies (key, label, tier) VALUES ('bandit','Bandyta','standard')")
    db.execute("INSERT INTO game_config_enemies (key, label, tier) VALUES ('wolf','Wilk','minion')")
    db.execute("INSERT INTO game_locations (key, label) VALUES ('karczma_x','Karczma Pod Kotem')")
    db.commit()


def test_draft_builds_setup_from_llm_with_catalogs():
    """Kreator: LLM dostaje katalogi (wrogowie/lokacje/bohaterowie) + treść issue,
    zwraca JSON setupu gotowy pod prepare_scenario."""
    from app.services.scenario_service import draft_scenario_setup

    db = _make_db()
    _mk_catalog(db)
    hero_id = _mk_hero(db)

    captured = {}

    def fake_llm(messages):
        captured["prompt"] = "\n".join(m["content"] for m in messages)
        return json.dumps({
            "reply": "Ustawiam zasadzkę bandytów nocą.",
            "setup": {
                "hero_id": hero_id,
                "issue_number": 1183,
                "title": "Zasadzka",
                "scene_enemies": ["bandit"],
                "ingame_hours": 23,
                "opening_narration": "Noc. Zaułek.",
                "agent_notes": "brak DC w issue",
            },
        })

    def fake_fetch(issue_number):
        assert issue_number == 1183
        return {"number": 1183, "title": "[BUG] encounter w zaułku",
                "body": "Acceptance: walka startuje nocą."}

    res = draft_scenario_setup(
        issue_number=1183, description="przetestuj zasadzkę",
        conn=db, llm=fake_llm, fetch_issue=fake_fetch,
    )

    assert res["setup"]["hero_id"] == hero_id
    assert res["setup"]["scene_enemies"] == ["bandit"]
    assert res["reply"].startswith("Ustawiam")
    assert res["issue"]["number"] == 1183
    # LLM musiał dostać: katalog wrogów, lokacje, bohaterów i treść issue
    assert "bandit" in captured["prompt"]
    assert "karczma_x" in captured["prompt"]
    assert "Tester" in captured["prompt"]
    assert "walka startuje nocą" in captured["prompt"]


def test_draft_tolerates_fenced_json_and_filters_unknown_enemies():
    """Odporność: LLM opakowuje JSON w ```json``` i wymyśla nieistniejącego wroga —
    fence zdjęty, nieznany klucz wycięty + dopisany do agent_notes."""
    from app.services.scenario_service import draft_scenario_setup

    db = _make_db()
    _mk_catalog(db)
    hero_id = _mk_hero(db)

    def fake_llm(messages):
        return ("```json\n" + json.dumps({
            "reply": "ok",
            "setup": {"hero_id": hero_id, "scene_enemies": ["bandit", "smok_pradawny"]},
        }) + "\n```")

    res = draft_scenario_setup(description="cokolwiek", conn=db, llm=fake_llm)
    assert res["setup"]["scene_enemies"] == ["bandit"]
    assert "smok_pradawny" in res["setup"]["agent_notes"]


def test_draft_requires_issue_or_description():
    from app.services.scenario_service import draft_scenario_setup, ScenarioError

    db = _make_db()
    try:
        draft_scenario_setup(conn=db, llm=lambda m: "{}")
        assert False, "expected ScenarioError"
    except ScenarioError:
        pass


def test_list_scenarios_returns_only_scenario_campaigns():
    from app.services.scenario_service import prepare_scenario, list_scenarios

    db = _make_db()
    hero_id = _mk_hero(db)
    db.execute(
        "INSERT INTO campaigns (title, system_id, model_id, owner_user_id)"
        " VALUES ('Zwykła kampania', 'fantasy', 'default', 7)"
    )
    db.commit()
    res = prepare_scenario({"hero_id": hero_id, "issue_number": 1183}, conn=db)

    rows = list_scenarios(conn=db)
    assert len(rows) == 1
    assert rows[0]["campaign_id"] == res["campaign_id"]
    assert rows[0]["issue_number"] == 1183
