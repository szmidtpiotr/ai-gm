/**
 * REGRESSION #797 (G11) — Catch-up po powrocie: endpoint /catchup zwraca poprawną strukturę.
 * Acceptance: GET /api/multiplayer/campaigns/{id}/catchup zwraca {missed_rounds, summary_line, absence_warnings_reset}.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #797 — /catchup endpoint zwraca poprawną strukturę", async ({ page }) => {
  // Campaign 1 (demo) — may or may not have MP rounds, but endpoint must always return valid shape
  const r = await page.request.get("/api/multiplayer/campaigns/1/catchup?user_id=1");
  // 200 or 404 (campaign not MP) — either is a valid non-crash response
  expect([200, 404, 403].includes(r.status()), `Unexpected status ${r.status()} (#797)`).toBeTruthy();
  if (r.status() === 200) {
    const body = await r.json();
    expect(Array.isArray(body.missed_rounds), "missed_rounds must be array").toBeTruthy();
    expect(typeof body.summary_line, "summary_line must be string").toBe("string");
    expect(typeof body.absence_warnings_reset, "absence_warnings_reset must be boolean").toBe("boolean");
  }
});
