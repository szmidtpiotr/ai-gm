/**
 * REGRESSION #762 — rejestr decyzji silnika per tura (turn_decisions).
 * Acceptance: endpoint GET /api/campaigns/{id}/turn-decisions odpowiada 200 ze strukturą
 * (action_type/route/gate per tura).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #762 — turn-decisions zwraca strukturę", async ({ page }) => {
  const r = await page.request.get("/api/campaigns/1/turn-decisions?limit=5");
  expect(r.ok(), "turn-decisions nie odpowiada 200 (#762)").toBeTruthy();
  const body = await r.json();
  expect(body).toHaveProperty("campaign_id");
  expect(Array.isArray(body.turn_decisions)).toBeTruthy();
  for (const d of body.turn_decisions) {
    expect(d).toHaveProperty("route");
    expect(d).toHaveProperty("gate_blocked");
  }
});
