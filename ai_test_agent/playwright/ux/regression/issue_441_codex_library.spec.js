/**
 * REGRESSION #441 (E26) — Kodeks biblioteka kart: GET mechanic-cards zwraca widziane karty.
 * Acceptance: endpoint zwraca {cards:[...]} z title+content+seen_at; przycisk Kodeks widoczny w app.js.
 */
const { test, expect } = require("@playwright/test");

const DEMO_USER_ID = 1;

test("REGRESSION #441 — GET /api/users/{id}/mechanic-cards zwraca poprawny kształt", async ({ page }) => {
  const r = await page.request.get(`/api/users/${DEMO_USER_ID}/mechanic-cards`);
  expect(r.ok(), `GET mechanic-cards zwrócił ${r.status()} (#441)`).toBeTruthy();
  const body = await r.json();
  expect(body).toHaveProperty("cards");
  expect(Array.isArray(body.cards)).toBeTruthy();
  if (body.cards.length > 0) {
    const card = body.cards[0];
    expect(card).toHaveProperty("mechanic_key");
    expect(card).toHaveProperty("title");
    expect(card).toHaveProperty("content");
    expect(card).toHaveProperty("seen_at");
  }
});

test("REGRESSION #441 — mark-seen then GET mechanic-cards zwraca tę kartę", async ({ page }) => {
  const key = "death_save";
  await page.request.post(`/api/users/${DEMO_USER_ID}/seen-mechanics`, {
    data: { mechanic_key: key },
  });
  const r = await page.request.get(`/api/users/${DEMO_USER_ID}/mechanic-cards`);
  const body = await r.json();
  const keys = body.cards.map((c) => c.mechanic_key);
  expect(keys.includes(key), `'${key}' powinien być w bibliotece (#441)`).toBeTruthy();
  const card = body.cards.find((c) => c.mechanic_key === key);
  expect(card.title, "Karta musi mieć title").toBeTruthy();
  expect(card.content, "Karta musi mieć content").toBeTruthy();
});

test("REGRESSION #441 — showCodexLibrary function exists in app.js", async ({ page }) => {
  const resp = await page.request.get("/js/app.js");
  expect(resp.ok()).toBeTruthy();
  const src = await resp.text();
  expect(src.includes("showCodexLibrary"), "showCodexLibrary musi być w app.js (#441)").toBeTruthy();
  expect(src.includes("open-codex-btn"), "open-codex-btn musi być w app.js (#441)").toBeTruthy();
});
