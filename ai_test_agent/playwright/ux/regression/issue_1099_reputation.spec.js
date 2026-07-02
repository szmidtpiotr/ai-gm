/**
 * REGRESSION #1099 — System reputacji per-region: endpoint ekspozycji reputacji bohatera.
 * Acceptance: GET /api/characters/{id}/reputation zwraca kontrakt {character_id, reputation:[...]}
 * z polami scope_type / scope_key / value / tier — fundament paska reputacji (Kronika #1098).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1099 — endpoint reputacji zwraca poprawny kontrakt", async ({ page }) => {
  const r = await page.request.get("/api/characters/1/reputation");
  expect(r.ok(), "endpoint reputacji nie odpowiada 200 (#1099)").toBeTruthy();

  const body = await r.json();
  expect(body).toHaveProperty("character_id");
  expect(Array.isArray(body.reputation), "reputation musi być listą").toBeTruthy();

  // Jeśli bohater ma jakieś standingi — każdy wpis ma pełny kształt (scope + tier).
  for (const row of body.reputation) {
    expect(row).toHaveProperty("scope_type");
    expect(row).toHaveProperty("scope_key");
    expect(typeof row.value).toBe("number");
    expect(["exalted", "friendly", "neutral", "disliked", "hated"]).toContain(row.tier);
  }
});
