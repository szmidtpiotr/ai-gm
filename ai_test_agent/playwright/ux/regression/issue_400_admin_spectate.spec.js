/**
 * REGRESSION #400 — Admin spectator + resume.
 * Admin przegląda WSZYSTKIE kampanie (filtr po userze = dropdown), podgląda
 * read-only i wznawia (re-attach bohatera + aktywacja). Endpointy gated przez is_admin.
 * Acceptance (deterministyczny): admin dostaje listę userów + kampanii; non-admin → 403.
 * Logika resume/list pokryta pytestem test_issue400_admin_spectate.py.
 */
const { test, expect } = require("@playwright/test");

const ADMIN = 1;        // Demo (is_admin=1)
const NON_ADMIN = 1011; // demo2 (is_admin=0)

test("REGRESSION #400 — admin spectator: kontrakt + gating", async ({ page }) => {
  // users — admin dostaje liste
  const ru = await page.request.get(`/api/admin-spectate/users?admin_user_id=${ADMIN}`);
  expect(ru.ok(), "users nie odpowiada 200 dla admina (#400)").toBeTruthy();
  const ju = await ru.json();
  expect(Array.isArray(ju.users), "users musi być tablicą (#400)").toBeTruthy();
  expect(ju.users.length, "lista userów pusta (#400)").toBeGreaterThan(0);

  // campaigns — admin dostaje liste wszystkich
  const rc = await page.request.get(`/api/admin-spectate/campaigns?admin_user_id=${ADMIN}`);
  expect(rc.ok(), "campaigns nie odpowiada 200 dla admina (#400)").toBeTruthy();
  const jc = await rc.json();
  expect(Array.isArray(jc.campaigns), "campaigns musi być tablicą (#400)").toBeTruthy();
  for (const c of jc.campaigns.slice(0, 5)) {
    expect(c.id, "kampania bez id (#400)").toBeTruthy();
    expect("last_turn" in c, "kampania bez last_turn (#400)").toBeTruthy();
    expect("character_id" in c, "kampania bez character_id (#400)").toBeTruthy();
  }

  // gating — non-admin dostaje 403
  const rg = await page.request.get(`/api/admin-spectate/users?admin_user_id=${NON_ADMIN}`);
  expect(rg.status(), "non-admin musi dostać 403 (#400)").toBe(403);
});
