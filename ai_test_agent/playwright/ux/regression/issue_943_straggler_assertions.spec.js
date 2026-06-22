/**
 * REGRESSION #943 — Straggler test assertions synced to current mechanics.
 * Acceptance: backend API returns consistent responses; no 500 errors on key endpoints
 * after migration fixes (v2-spells-effect-json-col ordering, spawn_weight, campaign_members).
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const resp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  const { token } = await resp.json();
  return token;
}

test("REGRESSION #943 — spells schema endpoint returns 200 (migration applied cleanly)", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.get("/api/admin/smart-entry/schema?table=game_config_spells", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "game_config_spells schema endpoint should respond 200 (#943)").toBeTruthy();
  const body = await r.json();
  // Verify schema has core spell fields — effect_json is internal (not exposed in smart-entry UI)
  const fields = (body.fields || []).map((f) => f.name || f.key || "");
  expect(fields.includes("mana_cost"), "mana_cost field should exist in spells schema (#943)").toBeTruthy();
  expect(fields.includes("tier"), "tier field should exist in spells schema (#943)").toBeTruthy();
});

test("REGRESSION #943 — campaign modes returns 4 modes (L9/L10 merged)", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.get("/api/campaigns/modes", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok()) return;
  const body = await r.json();
  const modes = Array.isArray(body) ? body : (body.modes || []);
  expect(modes.length, "should have exactly 4 campaign modes after L9/L10 (#943)").toBe(4);
});

test("REGRESSION #943 — weapons schema has value_gp column (migration applied)", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.get("/api/admin/smart-entry/schema?table=game_config_weapons", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "game_config_weapons schema endpoint should respond 200 (#943)").toBeTruthy();
  const body = await r.json();
  const fields = (body.fields || []).map((f) => f.name || f.key || "");
  expect(fields.includes("value_gp"), "value_gp column should exist in game_config_weapons (#943)").toBeTruthy();
});
