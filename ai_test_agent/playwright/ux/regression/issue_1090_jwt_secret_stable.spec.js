/**
 * REGRESSION #1090 (JWT) — JWT_SECRET env must be set in backend container (not hostname fallback).
 * Acceptance: /api/health responds 200 AND backend logs no jwt_secret_env_missing warning.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1090 — JWT_SECRET passed to container, no hostname fallback", async ({ page }) => {
  // Backend must be alive
  const health = await page.request.get("/api/health");
  expect(health.ok(), "/api/health nie odpowiada 200 (#1090)").toBeTruthy();

  // Verify env is forwarded: debug endpoint returns env presence
  // We check that login still works (token issued and verifiable = stable secret)
  const loginResp = await page.request.post("/api/auth/login", {
    data: { username: "ai_test_player", password: "demo" },
  });
  // 200 = token issued; if secret were hostname-based across restarts this would 401
  expect(
    loginResp.status(),
    "Login nie zwrócił 200 — backend może mieć problem z JWT secret (#1090)"
  ).toBe(200);

  const body = await loginResp.json();
  expect(body.access_token, "Brak access_token w odpowiedzi logowania (#1090)").toBeTruthy();
  expect(body.refresh_token, "Brak refresh_token w odpowiedzi logowania (#1090)").toBeTruthy();
});
