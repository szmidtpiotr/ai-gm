/**
 * REGRESSION #810 (G29) — ochrona promptu MP przed injection: endpoint /round/submit
 * waliduje action_text (limit długości + niepusty) zanim trafi do promptu LLM.
 * Acceptance: tekst > 1000 znaków → 400 "too long"; pusty/whitespace → 400 "cannot be empty";
 * tekst w granicy limitu przechodzi walidację długości (nie jest odrzucony jako za długi).
 */
const { test, expect } = require("@playwright/test");

const SUBMIT = "/api/campaigns/999999/round/submit?user_id=1";
const baseBody = { character_id: 1, character_name: "Test" };

test("REGRESSION #810 — action_text > 1000 znaków odrzucone (400 too long)", async ({ page }) => {
  const r = await page.request.post(SUBMIT, {
    data: { ...baseBody, action_text: "a".repeat(1001) },
  });
  expect(r.status(), "tekst 1001 znaków musi dać 400 (#810)").toBe(400);
  const body = await r.json();
  expect(String(body.detail || ""), "komunikat o przekroczeniu limitu").toContain("too long");
});

test("REGRESSION #810 — pusty/whitespace action_text odrzucone (400 empty)", async ({ page }) => {
  const r = await page.request.post(SUBMIT, {
    data: { ...baseBody, action_text: "   " },
  });
  expect(r.status(), "pusty tekst musi dać 400 (#810)").toBe(400);
  const body = await r.json();
  expect(String(body.detail || ""), "komunikat o pustym tekście").toContain("cannot be empty");
});

test("REGRESSION #810 — tekst w granicy limitu (1000) przechodzi walidację długości", async ({ page }) => {
  const r = await page.request.post(SUBMIT, {
    data: { ...baseBody, action_text: "a".repeat(1000) },
  });
  // Walidacja długości NIE może odrzucić tekstu o dokładnej długości limitu.
  // (Dalej może paść 4xx z powodu nieistniejącej kampanii 999999 — to OK,
  //  byle nie był to błąd "too long".)
  if (r.status() === 400) {
    const body = await r.json();
    expect(String(body.detail || ""), "1000 znaków NIE może być 'too long'").not.toContain("too long");
  } else {
    expect(r.status()).not.toBe(400);
  }
});
