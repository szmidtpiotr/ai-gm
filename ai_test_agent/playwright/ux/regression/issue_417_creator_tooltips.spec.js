/**
 * REGRESSION #417 (E2) — Kreator bohatera: tooltipy z opisami + przykładami mechanicznymi.
 * Acceptance: GET /api/mechanics/creator-help zwraca archetypy/staty/skille,
 * każdy z description + mechanical example (formuła rzutu / DC).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #417 — creator-help endpoint zwraca opisy + przykłady", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/creator-help");
  expect(r.ok(), "endpoint /mechanics/creator-help nie odpowiada 200 (#417)").toBeTruthy();

  const body = await r.json();
  expect(Array.isArray(body.archetypes), "brak archetypes[] (#417)").toBeTruthy();
  expect(Array.isArray(body.stats), "brak stats[] (#417)").toBeTruthy();
  expect(Array.isArray(body.skills), "brak skills[] (#417)").toBeTruthy();

  // Archetypy: 3 core + każdy ma description i example
  const archKeys = body.archetypes.map((a) => a.key);
  expect(archKeys).toEqual(expect.arrayContaining(["warrior", "rogue", "scholar"]));
  for (const a of body.archetypes) {
    expect(a.description, `archetyp ${a.key} bez opisu (#417)`).toBeTruthy();
    expect(a.example, `archetyp ${a.key} bez przykładu (#417)`).toBeTruthy();
  }

  // 7 statów (z LCK) z przykładem rzutu
  const statKeys = body.stats.map((s) => s.key);
  expect(statKeys).toEqual(
    expect.arrayContaining(["STR", "DEX", "CON", "INT", "WIS", "CHA", "LCK"])
  );
  for (const s of body.stats) {
    expect(s.example, `stat ${s.key} bez przykładu rzutu (#417)`).toBeTruthy();
  }

  // Skille z DC/przykładem użycia
  expect(body.skills.length).toBeGreaterThanOrEqual(5);
  for (const s of body.skills) {
    expect(s.description, `skill ${s.key} bez opisu (#417)`).toBeTruthy();
    expect(s.example, `skill ${s.key} bez przykładu (#417)`).toBeTruthy();
  }
});
