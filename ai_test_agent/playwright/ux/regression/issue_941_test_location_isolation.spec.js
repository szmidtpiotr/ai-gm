/**
 * REGRESSION #941 (FIX) — atrapy testowe 'test_loc*' nie są world-eligible.
 * POST /api/locations z kluczem 'test_loc_<ts>' musi utworzyć lokację canonical=0
 * (poza pulą generacji świata), a zwykła lokacja pozostaje canonical=1.
 * Acceptance: testowe lokacje nie wyciekają do realnych kampanii/narracji.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "admin", password: "admin" },
  });
  if (r.ok()) return (await r.json()).token;
  const r2 = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  return (await r2.json()).token;
}

test("REGRESSION #941 — test_loc location is not canonical, normal stays canonical", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { Authorization: `Bearer ${token}` };
  const ts = Date.now();

  // 1) atrapa testowa → canonical falsy
  const testKey = `test_loc_pw_${ts}`;
  const tResp = await page.request.post("/api/locations", {
    headers: auth,
    data: { key: testKey, label: "Updated Label Test", location_type: "macro" },
  });
  expect(tResp.ok(), "POST test_loc nie zwrócił 2xx (#941)").toBeTruthy();
  const testLoc = await tResp.json();
  expect(!testLoc.canonical, "test_loc MUSI być canonical=0 (#941)").toBeTruthy();

  // 2) zwykła lokacja → canonical=1 (brak regresji)
  const realKey = `real_place_pw_${ts}`;
  const rResp = await page.request.post("/api/locations", {
    headers: auth,
    data: { key: realKey, label: "Karczma Pod Lwem", location_type: "macro" },
  });
  expect(rResp.ok(), "POST zwykłej lokacji nie zwrócił 2xx").toBeTruthy();
  const realLoc = await rResp.json();
  expect(Boolean(realLoc.canonical), "zwykła lokacja musi pozostać canonical=1").toBeTruthy();

  // sprzątanie — żadnych śmieci po teście (#941)
  await page.request.delete(`/api/locations/${testKey}`, { headers: auth });
  await page.request.delete(`/api/locations/${realKey}`, { headers: auth });
});
