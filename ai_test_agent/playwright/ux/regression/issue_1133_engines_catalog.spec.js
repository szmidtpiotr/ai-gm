/**
 * REGRESSION #1133 (PT-D4d) — silniki social+world losują z katalogu game_config_encounters.
 * Acceptance: katalog serwuje rekordy combat ORAZ social (silnik ma z czego losować);
 * pusty katalog → fallback hardcode (weryfikowane pytestem). Tu sprawdzamy kontrakt:
 * katalog niepusty i zawiera oba rodzaje, więc dobór z katalogu jest aktywny.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), "dev-login nie zwrócił 200").toBeTruthy();
  const body = await r.json();
  expect(body.token, "brak tokenu admina").toBeTruthy();
  return body.token;
}

test("REGRESSION #1133 — katalog encounterów serwuje combat i social", async ({ page }) => {
  const token = await adminToken(page);
  const headers = { Authorization: `Bearer ${token}` };

  const r = await page.request.get("/api/admin/forge/encounters/catalog", { headers });
  expect(r.ok(), "endpoint katalogu nie odpowiada 200 (#1133)").toBeTruthy();
  const body = await r.json();
  const rows = body.encounters || [];

  const combat = rows.filter((e) => e.kind === "combat");
  const social = rows.filter((e) => e.kind === "social");

  expect(combat.length, "brak rekordów combat w katalogu — silnik nie ma z czego losować").toBeGreaterThan(0);
  expect(social.length, "brak rekordów social w katalogu — silnik nie ma z czego losować").toBeGreaterThan(0);

  // rekordy social muszą nieść stat/skill/dc (kształt konsumowany przez silnik)
  const s = social[0];
  const payload = s.payload || (s.payload_json ? JSON.parse(s.payload_json) : {});
  expect(payload.skill, "rekord social bez skill").toBeTruthy();
  expect(payload.dc, "rekord social bez dc").toBeTruthy();
});
