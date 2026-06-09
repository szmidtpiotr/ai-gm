/**
 * REGRESSION #439 (E24) — onboarding_service: check_onboarding_triggers filtruje seen/unseen mechaniki.
 * Acceptance: GET seen-mechanics zwraca listę; po mark-seen karta dla tej mechaniki nie jest już zwracana.
 */
const { test, expect } = require("@playwright/test");

const DEMO_USER_ID = 1;

test("REGRESSION #439 — GET /api/users/{id}/seen-mechanics zawiera poprawny kształt danych", async ({ page }) => {
  const r = await page.request.get(`/api/users/${DEMO_USER_ID}/seen-mechanics`);
  expect(r.ok(), `GET seen-mechanics zwrócił ${r.status()} (#439)`).toBeTruthy();
  const body = await r.json();
  expect(body).toHaveProperty("seen");
  expect(Array.isArray(body.seen)).toBeTruthy();

  // If any entries, check shape
  if (body.seen.length > 0) {
    const entry = body.seen[0];
    expect(entry).toHaveProperty("mechanic_key");
    expect(entry).toHaveProperty("seen_at");
  }
});

test("REGRESSION #439 — mark-seen → mechanika pojawia się w liście seen", async ({ page }) => {
  const testKey = "xp_gained";

  // mark as seen
  const post = await page.request.post(`/api/users/${DEMO_USER_ID}/seen-mechanics`, {
    data: { mechanic_key: testKey },
  });
  expect(post.ok(), `POST mark-seen failed: ${post.status()}`).toBeTruthy();
  const pb = await post.json();
  expect(pb.ok).toBe(true);

  // verify in list
  const get = await page.request.get(`/api/users/${DEMO_USER_ID}/seen-mechanics`);
  const gb = await get.json();
  const keys = gb.seen.map((s) => s.mechanic_key);
  expect(
    keys.includes(testKey),
    `'${testKey}' powinien pojawić się w seen po mark-seen (#439)`
  ).toBeTruthy();
});
