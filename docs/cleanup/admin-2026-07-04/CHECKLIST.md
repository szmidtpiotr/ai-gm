# CHECKLIST — cleanup admin #1177 (2026-07-04)

Batch 1 (wszystko LOW, frontend-only). Oznacz: ✅ usuń / ❌ zostaw / ⏸ kwarantanna.

Status: **ZAMKNIĘTE** — wszystkie F-01…F-10 wdrożone, zmergowane do `develop`, zweryfikowane (smoke `/admin/` + `/admin2/` = 200, usunięte pliki = 404).

- [x] ✅ F-01 — usuń `admin/sections/knowledge.js` (martwy, żyje w tools.js) — `4c2dcb8d`
- [x] ✅ F-02 — usuń `admin/shared/form.js` (0 importerów) — `15bb9cbf`
- [x] ✅ F-03 — usuń `admin_panel_v2/sections/{designer,dungeons,campaigns_settings}.js` (nie w moduleMap) — `e121e8be`
- [x] ✅ F-04 — usuń nginx `/panel/` + `/admin_panel/` + redirect `/panel` (→ nieistniejący katalog, 404) — `487e26be`
- [x] ✅ F-05 — bump `components.css?v=4` → `?v=5` — `f506d3c6`
- [x] ✅ F-06 — wersjonuj `table.js` w overview.js → `?v=7` (koniec podwójnej instancji) — `93952282`
- [x] ✅ F-07 — usuń nieużywaną `badgeId` — `7cf3e4a0`
- [x] ✅ F-08 — usuń martwy `PORTED` + nieosiągalną gałąź route() — `a2571dd6`
- [x] ✅ F-09 — popraw komentarze „15 sekcji" → 18 — `27120c08`
- [x] ✅ F-10 — dodaj `console.error` w catch route() — `08dd89b2`

Po batchu: restart kontenera frontendu (F-04 nginx) ✅ zrobiony, smoke `/admin/` + `/admin2/` ✅ 200, bump `?v` już w F-05/F-06 ✅, commit-per-finding ✅, update #1177 ✅, STOP.
