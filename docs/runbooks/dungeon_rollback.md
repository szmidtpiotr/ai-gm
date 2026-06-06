# Dungeon System Rollback Runbook

Issue: [#224 — Dungeon Tile Card System](https://github.com/szmidtpiotr/ai-gm/issues/224)

The dungeon system has two implementations gated by the `DUNGEON_SYSTEM` environment variable:

| Value | Code path |
|-------|-----------|
| `tiles` (default) | New tile-based system (`dungeon_tile_service.py`) |
| `legacy` | Frozen procedural rooms (`_legacy` functions in `dungeon_service.py`) |

This runbook covers reverting to legacy in case of a critical issue with the tile system.

---

## When to roll back

Roll back if you observe any of:

- New dungeon entries fail with backend 500 across all dungeons (not a single bad tile)
- Path generation hangs or loops despite a healthy tile pool (>= 10 active non-boss tiles + 1 boss per category)
- Active runs corrupt `session_flags.dungeon_run` in a way that blocks turn submission
- Image gen service unavailable AND no fallback tile images exist

Do NOT roll back for:

- A single dungeon config being broken (fix that config instead — set `is_active=0`)
- A single missing tile image (regenerate via admin panel)
- A bad tile_category_key on one game_dungeons row (fix the row)

---

## Rollback procedure (DEV)

```bash
ssh claude@192.168.1.61
cd /home/piotrszmidt/ai-gm
```

Add env var to `docker-compose.dev.yml` under `backend.environment`:

```yaml
    environment:
      - DUNGEON_SYSTEM=legacy
      # ... other existing vars
```

Rebuild:

```bash
docker compose -f docker-compose.dev.yml up -d --build backend
```

Verify:

```bash
docker compose -f docker-compose.dev.yml logs backend --tail=20 | grep dungeon
```

The backend will now route all dungeon flow (enter, advance, resolve) to `_enter_dungeon_legacy`, `_advance_room_legacy`, `_resolve_room_legacy`. Existing legacy dungeon rows in `game_dungeons` (those without `tile_category_key`) work as they did before tile work.

---

## Rollback procedure (PROD)

```bash
ssh claude@192.168.1.63
cd /home/piotrszmidt/ai-gm
```

Edit `docker-compose.yml` (NOT `.dev.yml` — PROD uses base file):

```yaml
    environment:
      - DUNGEON_SYSTEM=legacy
```

Deploy:

```bash
./scripts/deploy_prod.sh
```

Or for a faster rebuild without full deploy:

```bash
docker compose up -d --build backend
```

---

## Active-run cleanup (mandatory after rollback)

Players who were mid-dungeon when the rollback happened have tile-mode state in `session_flags.dungeon_run` that the legacy code can't read. Clear all in-progress dungeon runs:

```bash
# DEV
ssh claude@192.168.1.61 'docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db "
  UPDATE game_sessions
  SET session_flags = json_remove(session_flags, '\''$.dungeon_run'\'')
  WHERE json_extract(session_flags, '\''$.dungeon_run.system'\'') = '\''tiles'\'';
"'

# PROD — confirm with user before running
ssh claude@192.168.1.63 'docker exec ai-gm-backend-1 sqlite3 /data/ai_gm.db "
  UPDATE game_sessions
  SET session_flags = json_remove(session_flags, '\''$.dungeon_run'\'')
  WHERE json_extract(session_flags, '\''$.dungeon_run.system'\'') = '\''tiles'\'';
"'
```

Players are returned to the overworld. Cooldowns are NOT reset (intentional — they entered the dungeon, that's what cooldown tracks).

---

## Verification after rollback

1. Pick any active legacy dungeon (e.g. `dungeon_goblin_warren` if it has no `tile_category_key`):
   ```bash
   docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db "
     SELECT key, label, tile_category_key, rooms FROM game_dungeons WHERE is_active = 1;
   "
   ```
2. Enter it as a player. Backend logs should show `_enter_dungeon_legacy` invocation pattern (room types `combat`/`chest`/`trap`/`riddle`/`rest`).
3. Complete a turn. Verify combat resolution, room advance, loot grant all work.

---

## Returning to tiles after rollback

Once the issue is fixed:

1. Remove the env var from `docker-compose*.yml`
2. `up -d --build backend`
3. Players starting NEW dungeons get the tile system
4. Players still in legacy runs (if any) finish out in legacy mode — no migration needed

---

## Removal timeline

The `DUNGEON_SYSTEM` flag and `_legacy` functions are scheduled for removal **2 weeks after** tile-mode stable production with zero P0 bugs. Track removal as a separate issue.

Files to delete after the flag is removed:
- `_enter_dungeon_legacy`, `_advance_room_legacy`, `_resolve_room_legacy`, `_generate_dungeon_instance_legacy` in `backend/app/services/dungeon_service.py`
- `_use_legacy()` helper
- All `_room_type` random-pick helpers (`_pick_room_type`, default room weights)
- Trap fixtures (`traps = [...]` array in legacy code path)
- Rest-room descriptions in legacy code path
- Migration to NULL old `game_dungeons` columns: `enemy_pool`, `room_types_json`, `boss_enemy`
