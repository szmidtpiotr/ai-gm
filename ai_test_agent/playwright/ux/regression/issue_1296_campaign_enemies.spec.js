/**
 * REGRESSION #1296 (NPC-SEED-3) — endpoint wrogów kampanii zwraca roster planu
 * z materializacją, zasilający zakładkę ⚔ Przeciwnicy.
 * Acceptance: /api/admin/campaigns/9998881/enemies listuje wyrostki_spod_mlyna +
 * herszt_wyrostkow_harl jako materialized=true (playable).
 */
const { test, expect } = require("@playwright/test");

const CAMPAIGN_ID = 9998881;

async function adminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), "dev-login nie zwrócił 200").toBeTruthy();
  const b = await r.json();
  return b.token || b.access_token;
}

test("REGRESSION #1296 — roster wrogów kampanii z statusem materializacji", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.get(
    `/api/admin/campaigns/${CAMPAIGN_ID}/enemies`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  expect(r.ok(), "enemies endpoint nie odpowiada 200 (#1296)").toBeTruthy();
  const body = await r.json();
  const byKey = Object.fromEntries((body.enemies || []).map((e) => [e.key, e]));

  expect(byKey["wyrostki_spod_mlyna"], "brak wyrostków w roster").toBeTruthy();
  expect(byKey["herszt_wyrostkow_harl"], "brak Harla w roster").toBeTruthy();
  expect(byKey["herszt_wyrostkow_harl"].materialized, "Harl nie jest materialized").toBeTruthy();
  expect(byKey["herszt_wyrostkow_harl"].hp_base, "Harl bez HP z katalogu").toBeGreaterThan(0);
});
