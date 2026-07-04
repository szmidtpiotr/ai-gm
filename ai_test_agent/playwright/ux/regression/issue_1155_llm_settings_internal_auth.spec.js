/**
 * REGRESSION #1155 (SEC) — /users/{id}/llm-settings/internal nie może wyciekać api_key bez auth.
 * Acceptance: bez tokena → 401 i żaden api_key nie pojawia się w treści odpowiedzi.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1155 — internal llm-settings 401 + brak api_key bez tokena", async ({ page }) => {
  const r = await page.request.get("/api/users/1/llm-settings/internal");
  expect(r.status(), "endpoint przeszedł bez tokena").toBe(401);
  const body = await r.text();
  expect(body.includes("api_key"), "api_key wyciekł w odpowiedzi bez auth").toBeFalsy();
});
