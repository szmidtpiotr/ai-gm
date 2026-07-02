/**
 * REGRESSION #1102 — Pętla wskrzeszeń: bramka /resurrect nie może wpuścić żywego bohatera,
 * a szybkie powtórzenie musi trafić na cooldown zamiast znów wskrzeszać.
 * Acceptance: POST /resurrect na żywym bohaterze (current_hp > 0) → 409, nigdy 200/500.
 */
const { test, expect } = require("@playwright/test");

// [TEST] Wojownik — id 99996335, owner user_id=1, status='idle', current_hp=10 (alive)
const ALIVE_TEST_HERO_ID = 99996335;
const OWNER_USER_ID = 1;

test("REGRESSION #1102 — resurrect on alive hero returns 409, not 200/500", async ({ page }) => {
  const r = await page.request.post(
    `/api/characters/${ALIVE_TEST_HERO_ID}/resurrect?user_id=${OWNER_USER_ID}`
  );
  expect(r.status(), "żywy bohater nie może zostać wskrzeszony (#1102 gate)").toBe(409);
  const body = await r.json();
  expect(body.detail || "", "409 detail powinien tłumaczyć że bohater nie jest martwy").toMatch(
    /not dead|cooldown/i
  );
});

test("REGRESSION #1102 — resurrect-preview endpoint stays healthy", async ({ page }) => {
  const r = await page.request.get(
    `/api/characters/${ALIVE_TEST_HERO_ID}/resurrect-preview?user_id=${OWNER_USER_ID}`
  );
  // 200 = preview, 409 = not applicable — both fine. Must NOT be 500.
  expect(r.status(), "resurrect-preview nie może zwracać 500 (#1102)").not.toBe(500);
});
