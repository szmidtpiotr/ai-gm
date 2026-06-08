/**
 * REGRESSION #420 (E5) — Dead-hero campaign is blocked.
 * Acceptance: posting a turn to an ended campaign is rejected with HTTP 410 (Gone).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #420 — ended campaign rejects new turns with 410", async ({ page }) => {
  const r = await page.request.get("/api/campaigns");
  expect(r.ok(), "campaigns list failed (#420)").toBeTruthy();
  const body = await r.json();
  const list = body.campaigns || body || [];
  const ended = list.find((c) => c.status === "ended");
  test.skip(!ended, "no ended campaign in DB");

  const turn = await page.request.post(`/api/campaigns/${ended.id}/turns`, {
    data: { text: "spróbuję kontynuować", character_id: 1 },
  });
  expect(turn.status(), "ended campaign must return 410 Gone (#420)").toBe(410);
});
