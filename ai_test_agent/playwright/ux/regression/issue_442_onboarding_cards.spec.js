/**
 * REGRESSION #442 (E27) — Onboarding cards for new mechanics (affixes, crafting).
 * Acceptance: seen-mechanics endpoint supports "affixes" and "crafting" keys;
 *             mechanic-cards library returns content for all seen mechanics.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

test("REGRESSION #442 — seen-mechanics endpoint accepts affixes key", async ({ request }) => {
  // user 1 (demo) — mark affixes as seen
  const r = await request.post(`${BASE}/api/users/1/seen-mechanics`, {
    data: { mechanic_key: "affixes" },
  });
  expect(r.ok(), `seen-mechanics POST failed: ${r.status()}`).toBeTruthy();
  const body = await r.json();
  expect(body.ok).toBeTruthy();
  expect(body.mechanic_key).toBe("affixes");
});

test("REGRESSION #442 — seen-mechanics endpoint accepts crafting key", async ({ request }) => {
  const r = await request.post(`${BASE}/api/users/1/seen-mechanics`, {
    data: { mechanic_key: "crafting" },
  });
  expect(r.ok(), `seen-mechanics POST crafting failed: ${r.status()}`).toBeTruthy();
  const body = await r.json();
  expect(body.ok).toBeTruthy();
});

test("REGRESSION #442 — mechanic-cards library returns affixes card with content", async ({ request }) => {
  // Ensure affixes is marked as seen first
  await request.post(`${BASE}/api/users/1/seen-mechanics`, { data: { mechanic_key: "affixes" } });
  const r = await request.get(`${BASE}/api/users/1/mechanic-cards`);
  expect(r.ok(), `mechanic-cards GET failed: ${r.status()}`).toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.cards), "cards must be array").toBeTruthy();
  const affixCard = body.cards.find(c => c.mechanic_key === "affixes");
  expect(affixCard, "affixes card not found in library").toBeTruthy();
  expect(affixCard.title, "affixes card missing title").toBeTruthy();
  expect(affixCard.content, "affixes card missing content").toBeTruthy();
});
