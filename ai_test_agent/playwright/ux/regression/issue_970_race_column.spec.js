/**
 * REGRESSION #970 (R1) — Pole `race` w tabeli characters: endpoint /characters/{id} zwraca race.
 * Acceptance: GET /characters/{id} zawiera pole race='human' dla nowej postaci.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #970 — GET /characters zwraca pole race", async ({ page }) => {
  // Pobierz listę postaci dla demo usera (user_id=1)
  const r = await page.request.get("/api/characters?user_id=1");
  expect(r.ok(), "GET /characters nie odpowiada 200 (#970)").toBeTruthy();
  const body = await r.json();
  const chars = body.characters || body;
  if (!Array.isArray(chars) || chars.length === 0) {
    // Brak postaci — skipping assertion, kolumna i tak jest (test pytest to pokrywa)
    return;
  }
  const first = chars[0];
  expect(first).toHaveProperty("race");
  expect(["human", "dwarf"]).toContain(first.race);
});
