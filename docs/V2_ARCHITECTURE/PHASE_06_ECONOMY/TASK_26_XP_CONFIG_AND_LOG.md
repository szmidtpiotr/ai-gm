# TASK 26 — XP Configuration Panel + XP Log

**Status:** ⚠ Admin side ✅, **player UI niezaimplementowany, 21/22 źródeł niepodpiętych** — patrz `AUDIT_2026_05_18.md`.

**Phase:** 06 — Economy
**Depends on:** Task 25V2 (XP system design), Task 01 (DB Schema)
**Unlocks:** Admin can tune XP economy without code changes; players can trace their earnings

> **2026-05-18 audit:** Seed danych (22 źródeł XP) + admin endpointy ✅ (commit `5fb1b9a`). ALE:
> - **Tylko `combat.kill_*` faktycznie wywołuje `grant_character_xp`** w aplikacji. Pozostałe 21 źródeł (campaign tags, exploration triggers, skill DC bonuses, narrative XP_GRANT, session) **są seeded w bazie ale nigdy nie strzelają** — martwy kod do podpięcia w Stage 2D ROADMAP.md.
> - **Player "Historia PD" view** nie zaimplementowane (endpoint istnieje, frontend nie czyta).
> - **Admin XP Report endpoint** istnieje, używany w admin panel.
>
> Stage 2D w roadmap rozbija wpięcie 22 źródeł na 15 sub-itemów (XS1–XS15).

---

## Overview

Two connected features:
1. **Admin XP Config Panel** — all XP award amounts stored in DB, editable in admin panel per category
2. **XP Log / Trace** — per-grant log visible to player (character sheet) and admin (campaign report)

---

## Part 1 — `game_config_xp_awards` Table

### Schema

```sql
CREATE TABLE IF NOT EXISTS game_config_xp_awards (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category    TEXT NOT NULL
        CHECK(category IN ('combat','campaign','exploration','skills','narrative','session')),
    source_key  TEXT UNIQUE NOT NULL,
    label       TEXT NOT NULL,
    description TEXT,
    xp_amount   INTEGER NOT NULL DEFAULT 0,
    is_active   INTEGER NOT NULL DEFAULT 1,
    is_locked   INTEGER NOT NULL DEFAULT 0,
    -- is_locked=1: admin can edit amount but cannot delete or deactivate
    locked_at   TEXT DEFAULT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### Seed Data

```sql
INSERT OR IGNORE INTO game_config_xp_awards
    (category, source_key, label, description, xp_amount, is_locked) VALUES

-- Combat
('combat','kill_weak',          'Zabicie słabego wroga',           'Wróg tier=weak',        10,  1),
('combat','kill_standard',      'Zabicie standardowego wroga',     'Wróg tier=standard',    25,  1),
('combat','kill_elite',         'Zabicie elitarnego wroga',        'Wróg tier=elite',       50,  1),
('combat','kill_boss',          'Zabicie bossa',                   'Wróg tier=boss',        150, 1),
('combat','death_save_survived','Przeżycie rzutu na śmierć',       'Po każdym przeżytym rzucie', 15, 1),
('combat','outnumbered_victory','Zwycięstwo w przewadze (3+ wrogów)','Wszyscy wrogowie pokonani', 20, 1),

-- Campaign
('campaign','beat_complete',    'Cel kampanii ukończony',          '[BEAT_COMPLETE] tag',   30,  1),
('campaign','side_quest',       'Zlecenie poboczne ukończone',     '[QUEST_COMPLETE] tag',  40,  1),
('campaign','dungeon_cleared',  'Loch wyczyszczony',               '[DUNGEON_CLEAR] tag',   75,  1),
('campaign','campaign_ending',  'Zakończenie kampanii',            '[CAMPAIGN_END] tag',    200, 1),

-- Exploration
('exploration','location_new',  'Odkrycie nowej lokacji',          'Pierwsza wizyta w makrolokacji', 15, 1),
('exploration','npc_first_talk','Pierwsza rozmowa z NPC',          'Pierwszy DIALOGUE z danym kluczem NPC', 5, 1),
('exploration','secret',        'Odkrycie sekretu / wskazówki',   '[DISCOVERY:lore_key] tag', 10, 1),
('exploration','hidden_room',   'Odkrycie ukrytego przejścia',     '[DISCOVERY:secret_location] tag', 10, 1),

-- Skills
('skills','skill_dc_12',        'Test umiejętności DC 12–15',      'Sukces w teście DC w zakresie', 3,  1),
('skills','skill_dc_16',        'Test umiejętności DC 16–19',      'Sukces w teście DC w zakresie', 8,  1),
('skills','skill_dc_20',        'Test umiejętności DC 20+',        'Wyjątkowy sukces',      15,  1),
('skills','opposed_major_npc',  'Wygrana w teście z ważną postacią','NPC importance=critical/supporting', 10, 1),

-- Narrative (narrator emits [XP_GRANT:source_key:amount])
('narrative','nonviolent_solution','Rozwiązanie bez walki',        'Konflikt zakończony bez walki', 20, 1),
('narrative','heroic_sacrifice','Bohaterskie poświęcenie',          'Obrażenia przyjęte dla NPC',   25, 1),
('narrative','clever_environment','Kreatywne użycie otoczenia',    'Nieoczekiwane rozwiązanie',     10, 1),
('narrative','moral_choice',    'Trudny wybór moralny',             'Decyzja z realnym kosztem',    15, 1),
('narrative','unexpected_ally', 'Pozyskanie niespodziewanego sojusznika','Wróg przekonany do współpracy', 10, 1),
('narrative','major_discovery', 'Odkrycie kluczowej prawdy',        'Ważna tajemnica kampanii',     15, 1),
('narrative','_cap_per_session','Limit narracyjnych PD / sesję',   'Maksymalna kwota z kategorii narracja', 50, 1),

-- Session
('session','session_20turns',   'Sesja 20–39 tur',                 'Przyznawane przy długim odpoczynku', 10, 1),
('session','session_40turns',   'Sesja 40+ tur',                   'Przyznawane przy długim odpoczynku', 20, 1);
```

### Mechanic Resolver Integration

Resolver reads from table instead of hardcoded values:

```python
# Global cache (refreshed on startup or admin change)
_xp_cache: dict[str, int] = {}

def get_xp_amount(source_key: str) -> int:
    if not _xp_cache:
        _load_xp_cache()
    award = _xp_cache.get(source_key)
    if not award or not award["is_active"]:
        return 0
    return award["xp_amount"]

def _load_xp_cache():
    rows = db.execute("SELECT source_key, xp_amount, is_active FROM game_config_xp_awards").fetchall()
    _xp_cache.update({r["source_key"]: r for r in rows})

# Usage in resolver:
xp = get_xp_amount("kill_standard")  # reads from DB, not hardcoded 25
```

Cache invalidated when admin updates any row via the panel.

---

## Part 2 — `character_xp_grants` Enhancements

### Additional Columns

```sql
ALTER TABLE character_xp_grants ADD COLUMN source_key TEXT DEFAULT NULL;
-- References game_config_xp_awards.source_key

ALTER TABLE character_xp_grants ADD COLUMN campaign_id INTEGER DEFAULT NULL;
ALTER TABLE character_xp_grants ADD COLUMN turn_number INTEGER DEFAULT NULL;
ALTER TABLE character_xp_grants ADD COLUMN detail TEXT DEFAULT NULL;
-- Human-readable detail: enemy name, beat key, NPC key, etc.
```

### Grant Function

```python
def grant_xp(character_id, campaign_id, turn_number, source_key, detail=None):
    amount = get_xp_amount(source_key)
    if amount == 0:
        return  # source inactive or amount is 0

    db.execute("""
        INSERT INTO character_xp_grants
            (character_id, campaign_id, turn_number, amount, source_key, detail)
        VALUES (?, ?, ?, ?, ?, ?)
    """, [character_id, campaign_id, turn_number, amount, source_key, detail])

    # Emit game_event for MCP/analytics
    write_game_event("xp_granted", campaign_id, character_id, user_id, {
        "amount": amount,
        "source_key": source_key,
        "detail": detail,
        "total_xp_after": get_total_xp(character_id)
    })

# Example calls:
grant_xp(char_id, camp_id, turn, "kill_standard", detail="goblin_scout")
grant_xp(char_id, camp_id, turn, "beat_complete", detail="tavern_job_offer")
grant_xp(char_id, camp_id, turn, "location_new", detail="graustein_tavern")
```

---

## Part 3 — Admin Panel: "Nagrody PD" Section

**Location:** Mechaniki tab → new sub-tab "Nagrody PD"

### Table View (grouped by category tabs)

```
┌─────────────────────────────────────────────────────────────┐
│  ⭐ Nagrody PD                                              │
├─────────────────────────────────────────────────────────────┤
│  [Walka] [Kampania] [Eksploracja] [Umiejętności]            │
│  [Narracja] [Sesja]                                         │
├──────────────────────────────┬────────┬──────────┬──────────┤
│ Źródło                       │   PD   │ Aktywny  │          │
├──────────────────────────────┼────────┼──────────┼──────────┤
│ Zabicie słabego wroga        │ [10]   │   ✅     │  🔒      │
│ Zabicie standardowego wroga  │ [25]   │   ✅     │  🔒      │
│ Zabicie elitarnego wroga     │ [50]   │   ✅     │  🔒      │
│ Zabicie bossa                │ [150]  │   ✅     │  🔒      │
│ Przeżycie rzutu na śmierć    │ [15]   │   ✅     │  🔒      │
│ Zwycięstwo w przewadze (3+)  │ [20]   │   ✅     │  🔒      │
└──────────────────────────────┴────────┴──────────┴──────────┘
```

- `[10]` = inline editable number input. Click → type new value → Enter to save.
- ✅ toggle = enable/disable source (locked rows cannot be disabled)
- 🔒 = is_locked, cannot be deleted

**Behavior on change:**
- PATCH `/api/admin/xp-awards/{id}` with `{xp_amount: 30}`
- Backend updates row + invalidates XP cache
- Next resolver call picks up new value immediately

---

## Part 4 — XP Log UI

### Player View — Character Sheet "Historia PD" section

Collapsible section in the Overview tab, below conditions:

```
📊 Historia PD                       Łącznie: 145 PD
──────────────────────────────────────────────────────
[Kampania: Zdrada pod Graustein  ▾]

  T.12  +25  ⚔ Zabito: Goblin Zwiadowca
  T.12  +15  💀 Przeżyto rzut na śmierć
  T.09  +30  📖 Cel: Spotkanie w karczmie
  T.07  +15  🗺 Lokacja: Karczma Pod Krzyżem
  T.05  + 5  👤 NPC: Wotan (Karczmiarz)

──────────────────────────────────────────────────────
Oczekujące: +55 PD ⏳ (odblokowane przy długim odpoczynku)
```

Category icons: ⚔ combat | 📖 campaign | 🗺 exploration | 🎲 skills | 🎭 narrative | 💤 session

API: `GET /api/characters/{id}/xp-log?campaign_id={id}&limit=20`

### Admin View — Campaign XP Report

In the Campaign section (Admin Panel → Campaigns):

```
📊 Raport PD — "Zdrada pod Graustein"    Aldric | 145 PD total
──────────────────────────────────────────────────────────────
Walka:        55 PD
  ⚔ kill_standard ×2   50 PD   Goblin Zwiadowca, Goblin Łucznik
  💀 death_save          15 PD

Kampania:     30 PD
  📖 beat_complete ×1   30 PD   tavern_job_offer

Eksploracja:  20 PD
  🗺 location_new ×1    15 PD   graustein_tavern
  👤 npc_first_talk ×1   5 PD   wotan

Umiejętności:  0 PD   (brak testów powyżej DC 12 jeszcze)
Narracja:      0 PD   (brak zdarzeń narracyjnych)
Sesja:         0 PD   (oczekuje na odpoczynek)
──────────────────────────────────────────────────────────────
Oczekujące:  +55 PD    Ostatnia tura: 12
```

API: `GET /api/admin/campaigns/{id}/xp-report`

---

## API Endpoints

```
# XP Awards Config
GET    /api/admin/xp-awards                → full list, grouped by category
PATCH  /api/admin/xp-awards/{id}          → update xp_amount or is_active

# XP Log (player)
GET    /api/characters/{id}/xp-log
       ?campaign_id=&limit=20&offset=0
       → paginated list of grants for this character

# XP Report (admin)
GET    /api/admin/campaigns/{id}/xp-report
       → aggregated XP breakdown for the campaign's hero
```

---

## Test Checklist

- [ ] Admin changes kill_standard from 25 → 30 → next goblin kill awards 30 XP
- [ ] Admin deactivates `npc_first_talk` → talking to new NPC grants 0 XP
- [ ] Locked sources (is_locked=1) cannot be deleted or toggled off
- [ ] Every XP grant writes a row to `character_xp_grants` with source_key + detail
- [ ] Player XP log shows correct entries in correct order
- [ ] Pending XP shown separately from total earned
- [ ] Admin XP report aggregates by category correctly
- [ ] XP cache invalidated immediately after admin panel change

---

## Related Tasks
- Task 25V2 (XP Progression) — defines the full XP sources; this task makes them configurable
- Task 01 (DB Schema) — new table added to migrations
- Task 08 (Observability) — `game_events` gets `xp_granted` events for MCP analytics
- Task 35 (Character Sheet UI) — Historia PD section in Overview tab
