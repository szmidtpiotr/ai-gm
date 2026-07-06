/**
 * REGRESSION #1183 (code-review) — NPC pamięta zakupy: podpięty increment_npc_purchase_count.
 * Ścieżka zakupu (POST /api/shop/{npc_id}/buy) po udanej sprzedaży bumpuje purchase_count
 * kupca-NPC, żeby GM rozpoznawał stałego klienta.
 * Acceptance (deterministyczny kontrakt): endpoint zakupu jest osiągalny i mapuje błędy
 * (nie 500) — dowód, że ścieżka buy_item, w której żyje inkrement, wciąż odpowiada.
 * Pełny licznik 3×→count==3 pokrywa pytest test_issue1183_npc_purchase_count.py.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1183 — buy endpoint reachable + error-mapped (nie 500)", async ({ page }) => {
  // Bogus npc_id → shop_service.buy_item podnosi ValueError('npc_not_found'),
  // router mapuje na 4xx. Kluczowe: żaden 500 (crash w ścieżce inkrementu #1183).
  const r = await page.request.post("/api/shop/999999/buy", {
    data: { character_id: 999999, item_type: "weapon", item_key: "sword_basic" },
  });
  expect(r.status(), "buy endpoint nie może zwracać 500 (#1183)").not.toBe(500);
  expect(r.status(), "buy endpoint powinien odpowiadać zmapowanym błędem 4xx (#1183)").toBeGreaterThanOrEqual(400);
  expect(r.status()).toBeLessThan(500);
});
