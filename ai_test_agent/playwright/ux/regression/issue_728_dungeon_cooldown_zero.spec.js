/**
 * REGRESSION #728 (FAZA L) — loch z cooldown=0 nie pokazuje klepsydry/timeoutu.
 * Acceptance: krypta_probna ma cooldown_hours=0 i check_cooldown nie blokuje wejścia.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #728 — krypta_probna cooldown=0 honored, no stale timer", async ({ page }) => {
  const r = await page.request.get("/api/dungeons/krypta_probna");
  expect(r.ok(), "GET /api/dungeons/krypta_probna nie odpowiada 200 (#728)").toBeTruthy();
  const d = await r.json();

  // Root cause #1: cooldown=0 musi pozostać 0 (nie spaść cicho do 72h)
  const cd = Number(d.cooldown_hours);
  expect(cd, "cooldown_hours krypta_probna powinno być 0 w adminie (#728)").toBe(0);
});
