/**
 * REGRESSION #971 (R2) — Warstwa modyfikatorów rasowych: apply_racial_modifiers eksportowane z actor_stats.
 * Acceptance: API zwraca race w odpowiedzi GET /characters/{id}.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #971 — /characters/{id} zwraca race field", async ({ page }) => {
  // Pobierz dowolną postać demo usera przez API
  const listR = await page.request.get("/api/characters?user_id=1");
  if (!listR.ok()) return; // brak postaci = skip
  const listBody = await listR.json();
  const chars = listBody.characters || listBody;
  if (!Array.isArray(chars) || chars.length === 0) return;

  const charId = chars[0].id;
  const r = await page.request.get(`/api/characters/${charId}`);
  expect(r.ok(), `GET /characters/${charId} nie odpowiada 200`).toBeTruthy();
  const body = await r.json();
  expect(body).toHaveProperty("race");
  expect(["human", "dwarf"]).toContain(body.race);
});
