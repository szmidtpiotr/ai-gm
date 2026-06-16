/**
 * REGRESSION #679 (L10) — Flaga dungeon_enabled dla graczy.
 * Acceptance:
 * - GET /campaign-modes nie zawiera 'loch_kafelki'
 * - POST /dungeons/{key}/enter zwraca 403 gdy dungeon_enabled=False
 * - POST /dungeons/{key}/enter zwraca 404 (nie 403) gdy dungeon_enabled=True
 */
const { test, expect } = require("@playwright/test");

const DB_ADMIN_TOKEN = process.env.ADMIN_TOKEN || "dev-admin-token";

test("REGRESSION #679 — campaign-modes nie zawiera loch_kafelki", async ({ page }) => {
  const r = await page.request.get("/api/campaign-modes");
  expect(r.ok(), "GET /api/campaign-modes powinien zwrócić 200").toBeTruthy();
  const body = await r.json();
  const keys = (body.modes || []).map(m => m.key);
  expect(
    keys.includes("loch_kafelki"),
    `'loch_kafelki' nadal w campaign-modes — nie usunięto martwego trybu: ${keys.join(", ")}`
  ).toBeFalsy();
});

test("REGRESSION #679 — campaign-modes zawiera tryb 'loch'", async ({ page }) => {
  const r = await page.request.get("/api/campaign-modes");
  const body = await r.json();
  const keys = (body.modes || []).map(m => m.key);
  expect(
    keys.includes("loch"),
    `Brak trybu 'loch' w campaign-modes: ${keys.join(", ")}`
  ).toBeTruthy();
});

test("REGRESSION #679 — /enter zwraca 404 (nie 403) gdy dungeon_enabled domyślnie ON", async ({ page }) => {
  // Nie ustawiamy flagi — domyślnie dungeon_enabled=True
  // Nieidstninejący klucz → 404, nie 403 (flag check passes)
  const r = await page.request.post("/api/dungeons/nonexistent_key_xyz/enter", {
    data: { campaign_id: 1, character_id: 1 },
  });
  expect(r.status(), "Przy domyślnym ON oczekujemy 404 (nie 403) dla nieistniejącego lochu").toBe(404);
});
