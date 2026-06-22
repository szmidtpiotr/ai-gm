/**
 * REGRESSION #919 (H4b) — persisted admin toggle for the content/offline LLM profile.
 * Acceptance: GET/PATCH /api/settings/content-llm istnieją, router się ładuje i wymusza
 * auth (401 bez tokenu) — nie 404/500 (zepsuty import/rejestracja po dodaniu endpointów).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #919 — content-llm settings endpoint loads + enforces auth", async ({ page }) => {
  const r = await page.request.get("/api/settings/content-llm");
  expect(
    r.status(),
    `content-llm GET zwróciło ${r.status()} — endpoint nie zarejestrowany / router padł (#919)?`
  ).toBe(401);

  const p = await page.request.patch("/api/settings/content-llm", { data: { enabled: false } });
  expect(
    p.status(),
    `content-llm PATCH zwróciło ${p.status()} — endpoint nie zarejestrowany (#919)?`
  ).toBe(401);
});
