/**
 * REGRESSION #606 (S11) — prymityw `reroll` + kondycje inspired / cursed (pełny).
 * Acceptance: kondycje `inspired` i `cursed` są w publicznym katalogu z opisem przerzutu /
 * złego omenu; endpoint przerzutu gracza POST /campaigns/{id}/skill-test/reroll jest wpięty
 * (GET → 405, nie 404). Deterministyczne — bez LLM.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #606 — inspired i cursed w katalogu /api/mechanics/conditions", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/conditions");
  expect(r.ok(), "endpoint /api/mechanics/conditions nie odpowiada 200 (#606)").toBeTruthy();
  const body = await r.json();
  const byKey = Object.fromEntries((body.conditions || []).map((c) => [c.key, c]));

  expect(byKey.inspired, "brak kondycji inspired (#606)").toBeTruthy();
  expect(byKey.inspired.label).toBe("Zainspirowany");
  expect((byKey.inspired.description || "").toLowerCase()).toMatch(/przerzuc|inspir/);

  expect(byKey.cursed, "brak kondycji cursed (#606)").toBeTruthy();
  expect((byKey.cursed.description || "").toLowerCase()).toMatch(/omen|przerzuc|klątw/);
});

test("REGRESSION #606 — endpoint przerzutu gracza wpięty (POST-only route)", async ({ page }) => {
  // Trasa istnieje tylko jako POST → GET musi zwrócić 405 (a nie 404 jak nieistniejąca trasa).
  const r = await page.request.get("/api/campaigns/1/skill-test/reroll");
  expect(r.status(), "skill-test/reroll powinno istnieć jako POST (405 na GET, nie 404) (#606)").toBe(405);

  const missing = await page.request.get("/api/campaigns/1/skill-test/nonexistent-xyz");
  expect(missing.status(), "kontrola: nieistniejąca trasa zwraca 404 (#606)").toBe(404);
});
