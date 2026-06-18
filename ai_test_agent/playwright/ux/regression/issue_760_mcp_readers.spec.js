/**
 * REGRESSION #760 — czytniki debugowe: world-snapshots + llm-calls.
 * Acceptance: oba endpointy odpowiadają 200 z przewidywalną strukturą (debug bez replayu).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #760 — world-snapshots zwraca przyciętą strukturę", async ({ page }) => {
  const r = await page.request.get("/api/campaigns/1/world-snapshots?limit=3");
  expect(r.ok(), "world-snapshots nie odpowiada 200 (#760)").toBeTruthy();
  const body = await r.json();
  expect(body).toHaveProperty("campaign_id");
  expect(Array.isArray(body.snapshots), "snapshots musi być tablicą").toBeTruthy();
  for (const s of body.snapshots) {
    expect(s).toHaveProperty("turn_number");
    expect(s).toHaveProperty("enemy_count");
  }
});

test("REGRESSION #760 — llm-calls zwraca telemetrię", async ({ page }) => {
  const r = await page.request.get("/api/admin/campaigns/1/llm-calls?limit=3");
  expect(r.ok(), "llm-calls nie odpowiada 200 (#760)").toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.llm_calls), "llm_calls musi być tablicą").toBeTruthy();
});
