/**
 * REGRESSION #607 (S12) — prymitywy extra_action + on_expire_apply + kondycja hasted.
 * Acceptance: kondycja `hasted` jest w katalogu na DEV (seed wdrożony), a jej cel
 * on_expire (`exhausted`) też istnieje — silnik ma na czym oprzeć wygaśnięcie.
 * Mechanikę (darmowa zmiana strefy, exhausted po wygaśnięciu) pokrywa pytest test_issue607_s12_hasted.py.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #607 — hasted + exhausted w katalogu kondycji (seed S12)", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/conditions");
  expect(r.ok(), "katalog kondycji nie odpowiada 200 (#607)").toBeTruthy();
  const body = await r.json();
  const keys = (body.conditions || []).map((c) => c.key);

  expect(keys.includes("hasted"), "brak kondycji 'hasted' — seed S12 nie wdrożony").toBeTruthy();
  expect(keys.includes("exhausted"), "brak 'exhausted' — cel on_expire_apply hasted").toBeTruthy();

  const hasted = (body.conditions || []).find((c) => c.key === "hasted");
  expect(hasted, "wpis hasted istnieje").toBeTruthy();
  expect(/przy[śs]piesz/i.test(hasted.description || ""), "opis hasted opisuje przyśpieszenie").toBeTruthy();
});
