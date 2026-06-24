/**
 * REGRESSION #982 (NPC-FALLBACK) — sub-lokacje dziedziczą NPC z huba gdy własne = 0.
 * Acceptance: backend żyje i serwuje dane NPC/lokacji; fallback pokryty pytestem.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #982 — pending/counts zawiera klucz npcs (location-injector aktywny)", async ({ page }) => {
  const r = await page.request.get("/api/admin/world/pending/counts");
  expect(r.ok(), "GET /pending/counts nie odpowiada 200 (#982)").toBeTruthy();
  const body = await r.json();
  expect(typeof body.npcs, "pending/counts musi mieć klucz npcs (#982)").toBe("number");
  expect(typeof body.locations, "pending/counts musi mieć klucz locations (#982)").toBe("number");
});

test("REGRESSION #982 — pending/npcs zwraca listę (service location_context_injector działa)", async ({ page }) => {
  const r = await page.request.get("/api/admin/world/pending/npcs");
  expect(r.ok(), "GET /pending/npcs nie odpowiada 200 (#982)").toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.items), "pending/npcs.items musi być tablicą (#982)").toBeTruthy();
});
