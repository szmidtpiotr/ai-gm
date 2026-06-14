/**
 * REGRESSION #564 (U16) — Cost preview + durability + anti-farm + ekrany akcji płatnych.
 * Acceptance (kontrakt API, deterministyczny):
 *  - /api/inventory/{cid} zwraca pole `durability` na pozycjach broni/zbroi
 *    (null gdy bez trwałości, obiekt {current,max,pct,broken,penalty_pct} gdy z trwałością).
 *  - /api/shop/by-key/{npc_key} zwraca kup (items) + sprzedaj (sell_items) + złoto — UI sklepu ma z czego budować.
 *  - GET /api/characters/{cid}/inventory/{inv_id}/affix-costs jest wpięty (read-only podgląd kosztów kuźni).
 * Pełne ścieżki UI (klik kup/sprzedaj, naprawa, kuźnia) + komunikat nadpodaży — weryfikacja manualna na DEV.
 */
const { test, expect } = require("@playwright/test");

const CID = 2;            // [TEST] Wojownik — istnieje na DEV
const SHOP_KEY = "merchant_aldric";

test("REGRESSION #564 — /inventory wystawia pole durability na broni/zbroi", async ({ page }) => {
  const r = await page.request.get(`/api/inventory/${CID}`);
  expect(r.ok(), "endpoint /inventory nie odpowiada 200 (#564)").toBeTruthy();
  const body = await r.json();
  expect(body.ok).toBeTruthy();
  expect(Array.isArray(body.data)).toBeTruthy();

  for (const it of body.data) {
    const t = String(it.item_type || "").toLowerCase();
    if (t === "weapon" || t === "armor") {
      // klucz MUSI być obecny (kontrakt U16) — wartość null lub obiekt
      expect(it, "broń/zbroja bez pola durability (#564)").toHaveProperty("durability");
      if (it.durability) {
        expect(typeof it.durability.pct).toBe("number");
        expect(typeof it.durability.broken).toBe("boolean");
        expect(it.durability).toHaveProperty("penalty_pct");
      }
    }
  }
});

test("REGRESSION #564 — sklep by-key zwraca listy kup/sprzedaj + złoto", async ({ page }) => {
  const r = await page.request.get(`/api/shop/by-key/${SHOP_KEY}?character_id=${CID}`);
  expect(r.ok(), "endpoint /shop/by-key nie odpowiada 200 (#564)").toBeTruthy();
  const body = await r.json();
  expect(body.ok).toBeTruthy();
  const d = body.data;
  expect(Array.isArray(d.items), "brak listy items (kup) (#564)").toBeTruthy();
  expect(Array.isArray(d.sell_items), "brak listy sell_items (sprzedaj) (#564)").toBeTruthy();
  expect(typeof d.character_gold).toBe("number");
  // pozycje zakupu mają cenę do podglądu kosztu
  for (const it of d.items) {
    expect(it).toHaveProperty("buy_price_gp");
  }
});

test("REGRESSION #564 — endpoint affix-costs jest wpięty (read-only podgląd)", async ({ page }) => {
  // Bogus inventory id na istniejącym bohaterze → handler odpowiada (422 item_not_found
  // lub 403 not-your-hero), NIGDY 404 'route not found'. To dowód że trasa istnieje.
  const r = await page.request.get(`/api/characters/${CID}/inventory/99999999/affix-costs?user_id=1`);
  expect([200, 401, 403, 422].includes(r.status()), `affix-costs zwrócił ${r.status()} — trasa niewpięta? (#564)`).toBeTruthy();
});
