/**
 * REGRESSION #754 — strukturalny rejestr rzutów kostką (dice_rolls).
 * Acceptance: endpoint GET /api/campaigns/{id}/dice-rolls odpowiada 200 ze strukturą
 * {campaign_id, count, dice_rolls[]}, a filtr roll_type jest respektowany (kontrakt API).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #754 — endpoint dice-rolls zwraca strukturę rejestru rzutów", async ({ page }) => {
  const r = await page.request.get("/api/campaigns/1/dice-rolls?limit=5");
  expect(r.ok(), "endpoint dice-rolls nie odpowiada 200 (#754)").toBeTruthy();
  const body = await r.json();
  expect(body).toHaveProperty("campaign_id");
  expect(body).toHaveProperty("count");
  expect(Array.isArray(body.dice_rolls), "dice_rolls musi być tablicą (#754)").toBeTruthy();
});

test("REGRESSION #754 — filtr roll_type jest respektowany", async ({ page }) => {
  const r = await page.request.get("/api/campaigns/1/dice-rolls?roll_type=skill_test&limit=10");
  expect(r.ok()).toBeTruthy();
  const body = await r.json();
  // Każdy zwrócony rzut (jeśli są) musi mieć żądany typ.
  for (const roll of body.dice_rolls) {
    expect(roll.roll_type).toBe("skill_test");
  }
});
