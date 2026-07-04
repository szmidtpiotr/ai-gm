/**
 * REGRESSION #1187 (HARDEN) — jedna warstwa auth chroni cały namespace /api/admin/*.
 * Acceptance: dowolny endpoint /api/admin/* bez tokena → 401; dev-login (allowlist)
 * osiągalny bez tokena; endpointy spoza /api/admin niezmienione.
 */
const { test, expect } = require("@playwright/test");

const GUARDED = [
  "/api/admin/world/pending/counts",
  "/api/admin/images/config",
  "/api/admin/sandbox/heroes",
  "/api/admin/game-mechanics/content",
  "/api/admin/visual/config",
];

test("REGRESSION #1187 — /api/admin/* bez tokena zwraca 401", async ({ page }) => {
  for (const ep of GUARDED) {
    const r = await page.request.get(ep);
    expect(r.status(), `${ep} powinien być 401 bez tokena (#1187)`).toBe(401);
  }
});

test("REGRESSION #1187 — dev-login (allowlist) osiągalny bez tokena", async ({ page }) => {
  // Złe dane logowania → 401 "Invalid credentials" z samego endpointu,
  // NIE 401 z warstwy ("admin token"). Kluczowe: żądanie DOCIERA do handlera.
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "nope-1187", password: "x" },
  });
  const body = await r.json().catch(() => ({}));
  const detail = String(body.detail || "");
  expect(detail.toLowerCase(), "dev-login musi dotrzeć do handlera (allowlist)").not.toContain("admin token");
});

test("REGRESSION #1187 — endpoint spoza /api/admin niezmieniony", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "/api/health musi zostać publiczne (#1187)").toBeTruthy();
});
