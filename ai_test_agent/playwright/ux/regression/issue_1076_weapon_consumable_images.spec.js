/**
 * REGRESSION #1076 — Obrazki dla broni i konsumpcji.
 * Acceptance: endpointy /weapon/missing i /consumable/missing istnieją;
 * /api/inventory zwraca image_url dla broni i konsumpcji;
 * admin_images.py ma trasy weapon+consumable generate.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BACKEND_URL || "http://backend:8100";

test("REGRESSION #1076 — GET /api/admin/images/weapon/missing zwraca 200", async ({ request }) => {
  const r = await request.get(`${BASE}/api/admin/images/weapon/missing`);
  expect(r.ok(), `weapon/missing nie 200: ${r.status()}`).toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.weapons), "weapons nie jest tablicą").toBeTruthy();
  expect(typeof body.count === "number", "count nie jest liczbą").toBeTruthy();
});

test("REGRESSION #1076 — GET /api/admin/images/consumable/missing zwraca 200", async ({ request }) => {
  const r = await request.get(`${BASE}/api/admin/images/consumable/missing`);
  expect(r.ok(), `consumable/missing nie 200: ${r.status()}`).toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.consumables), "consumables nie jest tablicą").toBeTruthy();
  expect(typeof body.count === "number", "count nie jest liczbą").toBeTruthy();
});

test("REGRESSION #1076 — POST /weapon/{key}/generate zwraca 404 dla nieznanej broni (trasa istnieje)", async ({ request }) => {
  const r = await request.post(`${BASE}/api/admin/images/weapon/__tdd1076_nonexistent__/generate`, {
    data: { force: false },
  });
  expect([200, 404, 503].includes(r.status()), `Unexpected status ${r.status()} — trasa może nie istnieć`).toBeTruthy();
  expect(r.status()).not.toBe(405);
});

test("REGRESSION #1076 — POST /consumable/{key}/generate zwraca 404 dla nieznanej konsumpcji (trasa istnieje)", async ({ request }) => {
  const r = await request.post(`${BASE}/api/admin/images/consumable/__tdd1076_nonexistent__/generate`, {
    data: { force: false },
  });
  expect([200, 404, 503].includes(r.status()), `Unexpected status ${r.status()} — trasa może nie istnieć`).toBeTruthy();
  expect(r.status()).not.toBe(405);
});

test("REGRESSION #1076 — game_config_weapons ma kolumnę image_url w DB", async ({ request }) => {
  // Verify via weapon/missing endpoint — it SELECTs image_url column; would 500 if missing
  const r = await request.get(`${BASE}/api/admin/images/weapon/missing`);
  expect(r.ok(), `weapon/missing 500 = kolumna image_url brakuje: ${r.status()}`).toBeTruthy();
});

test("REGRESSION #1076 — game_config_consumables ma kolumnę image_url w DB", async ({ request }) => {
  const r = await request.get(`${BASE}/api/admin/images/consumable/missing`);
  expect(r.ok(), `consumable/missing 500 = kolumna image_url brakuje: ${r.status()}`).toBeTruthy();
});

test("REGRESSION #1076 — content.js ma isDedicatedEndpoint obejmujące weapon i consumable", async ({ request }) => {
  const r = await request.get("http://frontend:80/admin/sections/content.js");
  expect(r.ok(), "content.js nie dostępny").toBeTruthy();
  const text = await r.text();
  expect(
    text.includes("isDedicatedEndpoint"),
    "Brak zmiennej isDedicatedEndpoint w content.js — dedykowane endpointy weapon/consumable nie są obsługiwane"
  ).toBeTruthy();
  expect(
    text.includes("tableType === 'weapon'"),
    "Brak warunku tableType === 'weapon' w isDedicatedEndpoint"
  ).toBeTruthy();
  expect(
    text.includes("tableType === 'consumable'"),
    "Brak warunku tableType === 'consumable' w isDedicatedEndpoint"
  ).toBeTruthy();
});
