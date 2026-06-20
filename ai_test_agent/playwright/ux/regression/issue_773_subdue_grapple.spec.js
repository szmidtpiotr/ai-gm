/**
 * REGRESSION #773 — Mechanika obezwładnienia (grapple/schwytanie poza walką).
 * Acceptance: kondycja `schwytany` istnieje w katalogu kondycji gracza (block_action),
 * potwierdza że mechanika 2A jest zaseedowana i widoczna w grze.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #773 — kondycja schwytany w katalogu kondycji", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/conditions");
  expect(r.ok(), "endpoint /api/mechanics/conditions nie odpowiada 200 (#773)").toBeTruthy();
  const body = await r.json();
  const conds = Array.isArray(body.conditions) ? body.conditions : [];
  const schwytany = conds.find((c) => c.key === "schwytany");
  expect(schwytany, "kondycja 'schwytany' musi być zaseedowana (#773 2A)").toBeTruthy();
  expect(String(schwytany.label || "").length, "schwytany musi mieć etykietę").toBeGreaterThan(0);
});
