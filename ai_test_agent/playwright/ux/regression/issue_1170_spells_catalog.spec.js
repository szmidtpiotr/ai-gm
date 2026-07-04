/**
 * REGRESSION #1170 — publiczny katalog zaklęć GET /api/spells.
 * Acceptance: modal Awansuj Scholara dostaje pełny katalog (200 + spells[]
 * z polami key/label/description), zamiast pustej listy po 404.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1170 — GET /api/spells zwraca katalog z polami UI", async ({ page }) => {
  const r = await page.request.get("/api/spells");
  expect(r.ok(), "/api/spells musi odpowiadać 200 (#1170)").toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.spells), "spells musi być tablicą").toBeTruthy();
  expect(body.spells.length, "katalog nie może być pusty (seed)").toBeGreaterThan(0);
  const first = body.spells[0];
  expect(first.key, "brak key").toBeTruthy();
  expect(first.label, "brak label").toBeTruthy();
  expect("description" in first, "brak description").toBeTruthy();
});
