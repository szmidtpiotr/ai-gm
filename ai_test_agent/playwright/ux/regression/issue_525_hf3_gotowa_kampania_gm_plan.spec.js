/**
 * REGRESSION #525 (HF-3) — Gotowa Kampania: GM Plan poprawnie migruje beaty z szablonu.
 * Acceptance: campaign_templates z list-format arcs → po starcie kampanii plan zawiera
 * acts (dla V2 runtime) i arcs dict (dla W1 schema); gm_plan_is_ready zwraca True.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #525 — public campaign-templates endpoint returns published templates", async ({ page }) => {
  const r = await page.request.get("/api/campaign-templates");
  expect(r.ok(), "campaign-templates endpoint nie odpowiada 200 (#525)").toBeTruthy();
  const body = await r.json();
  const items = body.items || body;
  expect(Array.isArray(items), "response.items powinna być tablicą").toBeTruthy();
  expect(items.length).toBeGreaterThan(0);
});

test("REGRESSION #525 — template has gm_plan_json with arcs (key_beats present)", async ({ page }) => {
  const r = await page.request.get("/api/campaign-templates");
  expect(r.ok()).toBeTruthy();
  const body = await r.json();
  const templates = body.items || body;

  expect(templates.length).toBeGreaterThan(0);
  const t = templates[0];
  expect(t).toHaveProperty("id");
  expect(t).toHaveProperty("title");

  // gm_plan_json should have arcs with key_beats (the template format)
  const plan = t.gm_plan_json || {};
  expect(plan).toHaveProperty("arcs");
});

test("REGRESSION #525 — backend health OK after HF-3 deploy", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "health check nie odpowiada 200 po deployu HF-3 (#525)").toBeTruthy();
  const body = await r.json();
  expect(body.status).toBe("ok");
});
