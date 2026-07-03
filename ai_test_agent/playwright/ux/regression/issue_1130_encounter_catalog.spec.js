/**
 * REGRESSION #1130 (PT-D4a) — kanoniczny katalog encounterów w bazie.
 * Migracja game_config_encounters + seed z hardcode musi wgrać się przy starcie
 * backendu bez wywalenia bootu. Zła migracja = backend nie wstaje (health != 200).
 * Endpoint panelu (lista/edycja) dochodzi w #1132 — tu smoke, że fundament nie psuje startu.
 * Acceptance: /api/health = 200 po deployu z migracją katalogu.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1130 — migracja katalogu encounterów nie wywala startu backendu", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "backend nie odpowiada 200 — migracja #1130 mogła wywalić boot").toBeTruthy();
  const body = await r.json();
  expect(body.status, "health.status != ok").toBe("ok");
});
