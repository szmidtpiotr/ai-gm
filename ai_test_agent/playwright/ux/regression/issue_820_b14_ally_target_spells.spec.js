/**
 * REGRESSION #820 (B14) — czary wsparcia na sojusznika (heal/tarcza single-ally + grupowe).
 * Acceptance: po seedzie B14 katalog czarów zawiera `group_heal` (heal, all_allies)
 *   oraz `divine_shield_ally` (defense, ally) — fundament celowania na przyjazny slot
 *   odblokowany przez G7 (#791, sojusznicy w turn_order jako 'player:N').
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const resp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(resp.ok(), "dev-login nie zwrócił 200").toBeTruthy();
  const { token } = await resp.json();
  return token;
}

test("REGRESSION #820 — group_heal + divine_shield_ally zaseedowane jako czary wsparcia", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.get("/api/admin/spells", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "GET /api/admin/spells nie odpowiada 200 (#820)").toBeTruthy();
  const body = await r.json();
  const items = body.items || [];
  const byKey = Object.fromEntries(items.map((s) => [s.key, s]));

  const gh = byKey["group_heal"];
  expect(gh, "brak czaru group_heal (seed B14)").toBeTruthy();
  expect(gh.spell_type).toBe("heal");
  expect(String(gh.target_zone)).toBe("all_allies");

  const ds = byKey["divine_shield_ally"];
  expect(ds, "brak czaru divine_shield_ally (seed B14)").toBeTruthy();
  expect(ds.spell_type).toBe("defense");
  expect(String(ds.target_zone)).toBe("ally");
});
