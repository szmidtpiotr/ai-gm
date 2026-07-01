/**
 * REGRESSION #1069 (NL1) — non-lethal intent gate: intimidate/capture keywords
 * trigger advantage_gate instead of COMBAT_START.
 * Acceptance: 'intimidation' skill exists in game config (required for __GATE:intimidate).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1069 — intimidation skill exists in game config", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/skills");
  expect(r.ok(), "skills endpoint not responding 200 (#1069)").toBeTruthy();
  const body = await r.json();
  const skills = body.skills || (Array.isArray(body) ? body : []);
  const intimidation = skills.find(
    (s) => (s.key || "").toLowerCase() === "intimidation"
  );
  expect(
    intimidation,
    "intimidation skill missing from game_config_skills — required for #1069 gate"
  ).toBeTruthy();
});

test("REGRESSION #1069 — backend health ok (gate pipeline alive)", async ({ page }) => {
  const health = await page.request.get("/api/health");
  expect(health.ok(), "backend health check failed (#1069)").toBeTruthy();
});
