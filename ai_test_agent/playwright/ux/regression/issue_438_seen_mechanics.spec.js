/**
 * REGRESSION #438 (E23) — seen_mechanics: endpoints mark-seen i list działają poprawnie.
 * Acceptance: POST /api/users/{id}/seen-mechanics zapisuje mechanikę; GET zwraca listę; duplikaty ignorowane.
 */
const { test, expect } = require("@playwright/test");

const DEMO_USER_ID = 1;
const TEST_KEY = "dice_roll";

test("REGRESSION #438 — GET /api/users/{id}/seen-mechanics zwraca listę", async ({ page }) => {
  const r = await page.request.get(`/api/users/${DEMO_USER_ID}/seen-mechanics`);
  expect(r.ok(), `GET seen-mechanics nie odpowiada 200 (#438), status=${r.status()}`).toBeTruthy();
  const body = await r.json();
  expect(body, "Odpowiedź musi zawierać klucz 'seen'").toHaveProperty("seen");
  expect(Array.isArray(body.seen), "'seen' musi być tablicą").toBeTruthy();
});

test("REGRESSION #438 — POST /api/users/{id}/seen-mechanics zapisuje i jest idempotentne", async ({ page }) => {
  // mark once
  const r1 = await page.request.post(`/api/users/${DEMO_USER_ID}/seen-mechanics`, {
    data: { mechanic_key: TEST_KEY },
  });
  expect(r1.ok(), `POST seen-mechanics failed: status=${r1.status()}`).toBeTruthy();
  const b1 = await r1.json();
  expect(b1.ok, "Odpowiedź musi zawierać ok:true").toBe(true);

  // mark again (idempotent)
  const r2 = await page.request.post(`/api/users/${DEMO_USER_ID}/seen-mechanics`, {
    data: { mechanic_key: TEST_KEY },
  });
  expect(r2.ok(), `Drugi POST seen-mechanics failed: status=${r2.status()}`).toBeTruthy();
  const b2 = await r2.json();
  expect(b2.ok, "Drugi POST musi też zwracać ok:true").toBe(true);

  // verify GET shows key
  const r3 = await page.request.get(`/api/users/${DEMO_USER_ID}/seen-mechanics`);
  const b3 = await r3.json();
  const keys = b3.seen.map((s) => s.mechanic_key);
  expect(keys.includes(TEST_KEY), `'${TEST_KEY}' powinien być w liście seen`).toBeTruthy();
});
