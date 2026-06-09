/**
 * REGRESSION #443 (E28) — Tutorial kampania: is_tutorial w campaigns + has-campaigns endpoint.
 * Acceptance: kampanie mają kolumnę is_tutorial; has-campaigns zwraca bool; app.js ma _askTutorial.
 */
const { test, expect } = require("@playwright/test");

const DEMO_USER_ID = 1;

test("REGRESSION #443 — GET /api/users/{id}/has-campaigns zwraca {has_campaigns: bool}", async ({ page }) => {
  const r = await page.request.get(`/api/users/${DEMO_USER_ID}/has-campaigns`);
  expect(r.ok(), `has-campaigns endpoint zwrócił ${r.status()} (#443)`).toBeTruthy();
  const body = await r.json();
  expect(body).toHaveProperty("has_campaigns");
  expect(typeof body.has_campaigns).toBe("boolean");
  // Demo user has campaigns so should be true
  expect(body.has_campaigns).toBe(true);
});

test("REGRESSION #443 — POST /campaigns akceptuje is_tutorial=true", async ({ page }) => {
  const resp = await page.request.post("/api/campaigns", {
    data: {
      title: "PW Tutorial Test #443",
      system_id: "fantasy",
      model_id: "default",
      owner_user_id: DEMO_USER_ID,
      language: "pl",
      mode: "solo",
      status: "active",
      is_tutorial: true,
    },
  });
  expect(
    resp.status() !== 422,
    `POST /campaigns z is_tutorial=true nie powinno zwracać 422 (validation error), got ${resp.status()}`
  ).toBeTruthy();
  if (resp.ok()) {
    const camp = await resp.json();
    const campId = camp.id;
    // cleanup
    if (campId) {
      await page.request.delete(`/api/admin/campaigns/${campId}`).catch(() => {});
    }
  }
});

test("REGRESSION #443 — _askTutorial i is_tutorial functions exist in app.js", async ({ page }) => {
  const resp = await page.request.get("/js/app.js");
  expect(resp.ok()).toBeTruthy();
  const src = await resp.text();
  expect(src.includes("_askTutorial"), "_askTutorial musi być w app.js (#443)").toBeTruthy();
  expect(src.includes("is_tutorial"), "is_tutorial musi być w app.js (#443)").toBeTruthy();
  expect(src.includes("Moja Pierwsza Przygoda"), "Tytuł tutorialu musi być w app.js (#443)").toBeTruthy();
});
