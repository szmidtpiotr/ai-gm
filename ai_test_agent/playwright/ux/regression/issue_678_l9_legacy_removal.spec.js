/**
 * REGRESSION #678 (L9) — Usunięcie trybu proceduralnego lochu.
 * Acceptance: /dungeons/advance-room zwraca 410; /dungeons/resolve-room zwraca 410;
 * panel admin Lochy nie zawiera pól legacy (nd-pool, nd-boss, nd-rooms);
 * pola kafelkowe (nd-tile-cat, nd-chest, nd-bloot) są obecne.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #678 — advance-room endpoint zwraca 410 Gone", async ({ page }) => {
  const r = await page.request.post("/api/dungeons/advance-room", {
    data: {},
  });
  expect(r.status(), "advance-room powinien zwrócić 410 Gone (#678)").toBe(410);
});

test("REGRESSION #678 — resolve-room endpoint zwraca 410 Gone", async ({ page }) => {
  const r = await page.request.post("/api/dungeons/resolve-room", {
    data: {},
  });
  expect(r.status(), "resolve-room powinien zwrócić 410 Gone (#678)").toBe(410);
});

test("REGRESSION #678 — /api/dungeons lista nie zawiera aktywnych legacy lochów", async ({ page }) => {
  const r = await page.request.get("/api/dungeons");
  expect(r.ok(), "GET /api/dungeons powinien zwrócić 200").toBeTruthy();
  const body = await r.json();
  const dungeons = body.dungeons || [];
  const activeLegacy = dungeons.filter(
    d => d.is_active && (!d.tile_category_key || d.tile_category_key === "")
  );
  expect(
    activeLegacy.length,
    `Aktywne legacy lochy (bez tile_category_key): ${activeLegacy.map(d => d.key).join(", ")}`
  ).toBe(0);
});

test("REGRESSION #678 — /api/dungeons zwraca listę lochów (endpoint działa po usunięciu legacy)", async ({ page }) => {
  const r = await page.request.get("/api/dungeons");
  expect(r.ok(), "GET /api/dungeons powinien zwrócić 200 (#678)").toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.dungeons), "dungeons powinno być tablicą").toBeTruthy();
});
