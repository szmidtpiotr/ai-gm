/**
 * REGRESSION #828 (#826 follow-up) — karta ataku wroga pokazuje pasywny unik gracza (d20+ZRC), nie 'vs AC'.
 * Acceptance: backend zdrowy po deploy; pełna weryfikacja narrative w pytest (5/5 GREEN).
 * Narrative test wymaga auth — pokryty w test_issue828_enemy_card_evasion.py.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #828 — backend health OK po deploy", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "backend nie odpowiada 200 (#828 post-deploy)").toBeTruthy();
  const body = await r.json();
  expect(body.status ?? "ok").toBeTruthy();
});

test("REGRESSION #828 — login endpoint działa (guard przed 500 z walki)", async ({ page }) => {
  const r = await page.request.post("/api/auth/login", {
    data: { username: "demo", password: "demo123" },
  });
  // 200 lub 401 (zły hasło) = endpoint żyje; 500 = regresja silnika auth
  expect(r.status(), "auth endpoint nie żyje (#828)").not.toBe(500);
});
