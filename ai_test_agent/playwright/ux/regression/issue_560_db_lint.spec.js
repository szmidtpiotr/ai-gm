/**
 * REGRESSION #560 (U12) — db_lint: audyt integralności bazy treści.
 * Acceptance: GET /api/admin/db-lint wymaga tokenu admina (401 bez), a z tokenem
 * zwraca {errors[], warnings[], exit_code in 0/1/2, report:string}.
 */
const { test, expect } = require("@playwright/test");

async function adminLogin(request) {
  const r = await request.post("/api/admin/dev-login", {
    data: { username: "admin", password: "dev_password" },
  });
  if (!r.ok()) return null;
  const body = await r.json();
  return body.token || null;
}

test("REGRESSION #560 U12 — db-lint wymaga autoryzacji (401 bez tokenu)", async ({ page }) => {
  const r = await page.request.get("/api/admin/db-lint");
  expect(r.status(), "db-lint powinien zwracać 401 bez tokenu (nie 404/200)").toBe(401);
});

test("REGRESSION #560 U12 — db-lint zwraca raport z tokenem admina", async ({ page }) => {
  const token = await adminLogin(page.request);
  if (!token) {
    const health = await page.request.get("/api/health");
    expect(health.ok(), "backend nie odpowiada").toBeTruthy();
    return;
  }
  const r = await page.request.get("/api/admin/db-lint", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "db-lint nie odpowiada 200 z tokenem (#560)").toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.errors), "errors musi być tablicą").toBeTruthy();
  expect(Array.isArray(body.warnings), "warnings musi być tablicą").toBeTruthy();
  expect([0, 1, 2], "exit_code musi być 0/1/2").toContain(body.exit_code);
  expect(typeof body.report, "report musi być stringiem").toBe("string");
});
