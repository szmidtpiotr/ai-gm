/**
 * REGRESSION #1297 — narrator name-drift wroga (Harl vs Witek).
 * Acceptance: po korekcie kampania #9998881 nie zawiera „Witek" w turach, a herszt
 * występuje jako „Harl" (spójnie z planem key_enemies + kartą wroga).
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

test("REGRESSION #1297 — tury kampanii bez 'Witek', z 'Harl'", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.get(
    `/api/admin/campaigns/${CAMPAIGN_ID}/turns?limit=100`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  expect(r.ok(), "turns endpoint nie odpowiada 200 (#1297)").toBeTruthy();
  const body = await r.json();
  const blob = JSON.stringify(body.items || []);

  expect(blob.includes("Witek"), "w turach nadal jest 'Witek' (#1297)").toBeFalsy();
  expect(blob.includes("Witka"), "w turach nadal jest odmiana 'Witka' (#1297)").toBeFalsy();
  expect(blob.includes("Harl"), "brak 'Harl' w turach — herszt nienazwany zgodnie z planem").toBeTruthy();
});
