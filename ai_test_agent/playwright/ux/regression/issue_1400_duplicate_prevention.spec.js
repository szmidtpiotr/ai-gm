/**
 * REGRESSION #1400 — prewencja duplikatów przy tworzeniu (Kuźnia): kontrakt API.
 * Acceptance: GET /api/admin/duplicates zwraca sekcję prevention {reused, flagged}
 * (licznik uniknięć), a grupy mają pole flagged (bool) sterujące znacznikiem ⚠
 * i sortowaniem. Sam mechanizm reuse/flag pokrywa pytest (test_issue1400_*).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1400 — skan niesie statystyki prewencji i pole flagged", async ({ page }) => {
  const login = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(login.ok(), "dev-login nie działa (#1400)").toBeTruthy();
  const { token } = await login.json();

  const scan = await page.request.get("/api/admin/duplicates", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(scan.ok(), "GET /duplicates nie odpowiada 200 (#1400)").toBeTruthy();
  const body = await scan.json();

  expect(body.prevention, "brak sekcji prevention").toBeTruthy();
  expect(typeof body.prevention.reused, "prevention.reused musi być liczbą").toBe("number");
  expect(typeof body.prevention.flagged, "prevention.flagged musi być liczbą").toBe("number");

  for (const groups of Object.values(body.tables)) {
    for (const g of groups) {
      expect(typeof g.flagged, "każda grupa musi mieć bool flagged").toBe("boolean");
    }
  }
});
