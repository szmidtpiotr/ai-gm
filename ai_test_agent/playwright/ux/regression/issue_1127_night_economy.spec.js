/**
 * REGRESSION #1127 (PT14) — Nocna ekonomia: sklepy zamknięte 21-5, karczma otwarta, paser nocą.
 * Acceptance: endpoint sklepu zwraca kontrakt nocnej ekonomii (shop_open / is_black_market),
 * a zwykły kupiec NIE jest czarnym rynkiem.
 */
const { test, expect } = require("@playwright/test");

// Deterministyczny kontrakt — bez LLM. Zwykły kupiec (merchant_aldric, id=1),
// bohater testowy z kampanią (clock znany). GET jest read-only.
const SHOP_NPC_ID = 1;            // merchant_aldric — normalny sklep
const CHARACTER_ID = 99996348;    // test hero (kampania 990001105)

test("REGRESSION #1127 — shop endpoint exposes night-economy contract", async ({ page }) => {
  const r = await page.request.get(
    `/api/shop/${SHOP_NPC_ID}?character_id=${CHARACTER_ID}`
  );
  expect(r.ok(), "endpoint /api/shop nie odpowiada 200 (#1127)").toBeTruthy();

  const body = await r.json();
  const data = body.data || body;

  // Nowe pola kontraktu nocnej ekonomii muszą istnieć.
  expect(data, "brak pola shop_open (#1127)").toHaveProperty("shop_open");
  expect(data, "brak pola is_black_market (#1127)").toHaveProperty("is_black_market");

  // Zwykły kupiec nigdy nie jest czarnym rynkiem.
  expect(data.is_black_market, "zwykły kupiec oznaczony jako paser (#1127)").toBeFalsy();
});
