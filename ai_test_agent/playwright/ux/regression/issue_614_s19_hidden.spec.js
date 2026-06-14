/**
 * REGRESSION #614 (S19) — kondycja `hidden` (prymitywy untargetable + ambush_bonus) jest zaseedowana i aktywna.
 * Acceptance: katalog kondycji gracza zawiera `hidden` (Ukryty) z opisem zasadzki (+2k6) i wejścia przez skradanie.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #614 — hidden condition seeded & active", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/conditions");
  expect(r.ok(), "GET /api/mechanics/conditions nie odpowiada 200 (#614)").toBeTruthy();
  const body = await r.json();
  const list = Array.isArray(body.conditions) ? body.conditions : [];
  const hidden = list.find((c) => c.key === "hidden");
  expect(hidden, "kondycja 'hidden' nie istnieje w katalogu (#614)").toBeTruthy();
  expect(hidden.label).toBe("Ukryty");
  // opis musi sygnalizować zasadzkę (+2k6), untargetable (wrogowie nie mogą atakować) i wejście przez skradanie
  expect(/zasadzk/i.test(hidden.description || ""), "opis hidden bez wzmianki o zasadzce").toBeTruthy();
  expect(/2k6/i.test(hidden.description || ""), "opis hidden bez +2k6").toBeTruthy();
  expect(/skradan|stealth/i.test(hidden.description || ""), "opis hidden bez wejścia przez skradanie").toBeTruthy();
});
