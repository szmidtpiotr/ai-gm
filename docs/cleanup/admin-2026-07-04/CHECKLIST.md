# CHECKLIST — cleanup admin #1177 (2026-07-04)

Batch 1 (wszystko LOW, frontend-only). Oznacz: ✅ usuń / ❌ zostaw / ⏸ kwarantanna.

- [ ] F-01 — usuń `admin/sections/knowledge.js` (martwy, żyje w tools.js)
- [ ] F-02 — usuń `admin/shared/form.js` (0 importerów)
- [ ] F-03 — usuń `admin_panel_v2/sections/{designer,dungeons,campaigns_settings}.js` (nie w moduleMap)
- [ ] F-04 — usuń nginx `/panel/` + `/admin_panel/` + redirect `/panel` (→ nieistniejący katalog, 404)
- [ ] F-05 — bump `components.css?v=4` → `?v=5`
- [ ] F-06 — wersjonuj `table.js` w overview.js → `?v=7` (koniec podwójnej instancji)
- [ ] F-07 — usuń nieużywaną `badgeId`
- [ ] F-08 — usuń martwy `PORTED` + nieosiągalną gałąź route()
- [ ] F-09 — popraw komentarze „15 sekcji" → 18
- [ ] F-10 — dodaj `console.error` w catch route()

Po batchu: restart kontenera frontendu (F-04 nginx), smoke `/admin/` + `/admin2/`, bump `?v` już w F-05/F-06, commit-per-finding, update #1177, STOP.
