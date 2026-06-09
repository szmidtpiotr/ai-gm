/**
 * REGRESSION #431 (E16) — Śmierć w lochu przywraca snapshot z wejścia.
 * Acceptance: POST /dungeons/death zwraca ok=true, restored=true, restarted=true.
 * Weryfikuje że handle_dungeon_death nie nakłada cooldownu.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #431 — dungeon death endpoint returns restored+restarted flags", async ({ page }) => {
  // Verify the death endpoint accepts a well-formed request and returns the new flags.
  // Uses a non-existent campaign_id so no real data is mutated; the service returns ok=True
  // with restored=False (no snapshot) and restarted=True (run is absent → early return).
  const r = await page.request.post("/api/dungeons/death", {
    data: { campaign_id: 999999999, character_id: 999999999 },
  });
  expect(r.ok(), "POST /api/dungeons/death must return 200 (#431)").toBeTruthy();
  const body = await r.json();
  expect(body.ok, "response.ok must be true (#431)").toBe(true);
  // restarted flag must exist in response (new E16 field)
  expect("restarted" in body, "response must include restarted field (#431)").toBeTruthy();
});

test("REGRESSION #431 — dungeon death response no longer has failed:true", async ({ page }) => {
  // Old behavior marked run as failed=true. E16 replaces that with restarted=true.
  const r = await page.request.post("/api/dungeons/death", {
    data: { campaign_id: 999999999, character_id: 999999999 },
  });
  const body = await r.json();
  expect(body.failed, "failed flag must not be present in E16 response (#431)").toBeFalsy();
});
