/**
 * REGRESSION #1122 (PT12) — travel-interrupt decision buttons + /travel-resume endpoint.
 * Acceptance: the mechanical resume endpoint is wired and gates correctly (no LLM lottery);
 * a campaign with no interrupted travel gets a clean 409, never a 404/405 (route exists).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1122 — /travel-resume endpoint is registered and gates cleanly", async ({ page }) => {
  // Demo campaign 1 has a live session but (normally) no interrupted travel_plan.
  const r = await page.request.post("/api/campaigns/1/travel-resume", {
    headers: { "Content-Type": "application/json" },
    data: {},
  });

  // Route must exist — a missing route would be 404 "Not Found" with FastAPI's default body,
  // or 405 for a wrong method. The gate returns 409/404-session/400 with a detail string.
  expect([400, 404, 409].includes(r.status()), `unexpected status ${r.status()} (#1122)`).toBeTruthy();

  const body = await r.json().catch(() => ({}));
  // Must be a real gate detail — NOT FastAPI's route-missing body {"detail":"Not Found"}.
  expect(typeof body.detail === "string" && body.detail.length > 0, "brak detail w odpowiedzi bramki (#1122)").toBeTruthy();
  expect(body.detail !== "Not Found", "endpoint /travel-resume nie jest zarejestrowany (#1122)").toBeTruthy();
});
