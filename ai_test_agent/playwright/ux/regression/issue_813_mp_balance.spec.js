/**
 * REGRESSION #813 (G15) — Flagi balansu MP: GET/PATCH /api/admin/sandbox/mp-balance.
 * Acceptance: endpoint zwraca 5 flag z domyślnymi wartościami (10/20/30%, floor=50, HP=0.5, skalowanie neutralne 1.0); PATCH zmienia flagę bez redeployu.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #813 — GET /api/admin/sandbox/mp-balance zwraca domyślne flagi balansu MP", async ({ page }) => {
  const r = await page.request.get("/api/admin/sandbox/mp-balance");
  expect(r.ok(), "endpoint mp-balance nie odpowiada 200 (#813)").toBeTruthy();
  const body = await r.json();

  // Five required keys
  expect(body).toHaveProperty("wipe_gold_pct_by_level");
  expect(body).toHaveProperty("wipe_gold_floor");
  expect(body).toHaveProperty("wipe_hp_pct");
  expect(body).toHaveProperty("mp_difficulty_scale_by_count");
  expect(body).toHaveProperty("mp_loot_scale_by_count");

  // Default values per spec
  expect(body["wipe_gold_pct_by_level"]["1-3"], "wipe% level 1-3 must be 0.10").toBe(0.1);
  expect(body["wipe_gold_pct_by_level"]["4-7"], "wipe% level 4-7 must be 0.20").toBe(0.2);
  expect(body["wipe_gold_pct_by_level"]["8+"],  "wipe% level 8+ must be 0.30").toBe(0.3);
  expect(body["wipe_gold_floor"], "wipe_gold_floor must be 50").toBe(50);
  expect(body["wipe_hp_pct"],     "wipe_hp_pct must be 0.5").toBe(0.5);

  // Scaling neutral (1.0) for all player counts
  for (const k of ["1", "2", "3", "4"]) {
    expect(body["mp_difficulty_scale_by_count"][k], `difficulty scale[${k}] must be 1.0`).toBe(1);
    expect(body["mp_loot_scale_by_count"][k],       `loot scale[${k}] must be 1.0`).toBe(1);
  }
});

test("REGRESSION #813 — PATCH /api/admin/sandbox/mp-balance aktualizuje flagę bez redeployu", async ({ page }) => {
  // Patch wipe_gold_floor to a test value
  const patch = await page.request.patch("/api/admin/sandbox/mp-balance", {
    data: { wipe_gold_floor: 99 },
    headers: { "Content-Type": "application/json" },
  });
  expect(patch.ok(), "PATCH mp-balance nie odpowiada 200 (#813)").toBeTruthy();
  const patchBody = await patch.json();
  expect(patchBody.ok,                     "PATCH ok must be true").toBe(true);
  expect(patchBody.updated,                "updated list must include wipe_gold_floor").toContain("wipe_gold_floor");

  // Verify GET reflects the change
  const r = await page.request.get("/api/admin/sandbox/mp-balance");
  const body = await r.json();
  expect(body["wipe_gold_floor"], "GET after PATCH must show updated value 99").toBe(99);

  // Restore default so other tests are not affected
  await page.request.patch("/api/admin/sandbox/mp-balance", {
    data: { wipe_gold_floor: 50 },
    headers: { "Content-Type": "application/json" },
  });
});
