/**
 * REGRESSION #579 — sklepy wiejskie bez jawnego asortymentu dostają domyślny stock wg roli.
 * Kowal (is_crafter) ma broń/zbroję do kupienia zamiast pustej listy.
 * Acceptance: /api/shop/by-key/kowal_brzezino zwraca niepustą listę items.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #579 — kowal_brzezino ma asortyment do kupna", async ({ page }) => {
  const r = await page.request.get("/api/shop/by-key/kowal_brzezino?character_id=2&location_key=brzezino");
  expect(r.ok(), "endpoint sklepu nie odpowiada 200").toBeTruthy();
  const body = await r.json();
  const items = (body.data && body.data.items) || [];
  expect(items.length, "kowal nadal ma pustą listę kupna").toBeGreaterThan(0);
  // smith → powinien mieć broń lub zbroję
  const types = new Set(items.map((i) => i.type));
  expect(types.has("weapon") || types.has("armor")).toBeTruthy();
});
