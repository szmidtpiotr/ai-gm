/**
 * REGRESSION #423 (E8) — player ready-campaign picker: only player_visible templates listed.
 * Acceptance: /api/campaign-templates returns published+player_visible templates with the
 * fields the picker cards render (title, description, difficulty_rating). Hidden ones excluded.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #423 — public template list is player-visible only + card-ready", async ({ page }) => {
  const r = await page.request.get("/api/campaign-templates");
  expect(r.ok(), "/api/campaign-templates not 200 (#423)").toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.items), "items must be an array (#423)").toBeTruthy();

  for (const t of body.items) {
    // Endpoint must never surface a hidden template to the player picker.
    expect(t.player_visible, `hidden template leaked to player (#423): id=${t.id}`).not.toBe(0);
    // Card render contract.
    expect("title" in t, "card needs title (#423)").toBeTruthy();
    expect("description" in t, "card needs description (#423)").toBeTruthy();
    expect("difficulty_rating" in t, "card needs difficulty_rating (#423)").toBeTruthy();
  }
});
