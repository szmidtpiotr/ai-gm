/**
 * REGRESSION #633 (SF10) — reaktywny modal uniku/bloku zastępuje pre-deklarację.
 * Acceptance: endpoint POST /combat/resolve-reaction jest zarejestrowany i waliduje
 * brak aktywnego okna reakcji (400, nie 404). Pełna logika (okno zamiast obrażeń,
 * take/dodge/block, 1/rundę, auto-take) pokryta 35 testami pytest (#633/#610/#611).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #633 — resolve-reaction endpoint wired + waliduje brak okna", async ({ page }) => {
  // Brak aktywnej walki → 400 (endpoint istnieje), NIE 404 (trasa nieznana).
  const r = await page.request.post(
    "/api/campaigns/999999/combat/resolve-reaction",
    { data: { choice: "take" }, headers: { "Content-Type": "application/json" } }
  );
  expect(r.status(), "resolve-reaction powinien zwrócić 400 dla braku walki, nie 404").toBe(400);
});

test("REGRESSION #633 — enemy-turn endpoint istnieje (kontrakt tury wroga)", async ({ page }) => {
  // Bez aktywnej walki enemy-turn też zwraca 400 (no active combat) — trasa zarejestrowana.
  const r = await page.request.post("/api/campaigns/999999/combat/enemy-turn", {
    headers: { "Content-Type": "application/json" },
  });
  expect([400, 422].includes(r.status()), "enemy-turn trasa zarejestrowana").toBeTruthy();
});
