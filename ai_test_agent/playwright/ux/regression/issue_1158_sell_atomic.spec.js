/**
 * REGRESSION #1158 — sell_item atomowy: usunięcie przedmiotu + wypłata złota w jednej transakcji.
 * Pełna logika pokryta pytestem backend/tests/test_issue1158_sell_atomic.py (RED→GREEN:
 *   gdy kredyt złota rzuci, DELETE się rolluje i przedmiot zostaje — koniec znikania bez wypłaty).
 * Ten spec pilnuje kontraktu katalogu sprzedaży: muszą istnieć sprzedawalne przedmioty
 * (consumables/items), inaczej ścieżka sell_item nie ma czego rozliczać.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const login = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(login.ok(), "admin login must succeed (#1158)").toBeTruthy();
  const body = await login.json();
  const token = body.token || body.access_token;
  expect(token, "login must return token (#1158)").toBeTruthy();
  return token;
}

test("REGRESSION #1158 — katalog sprzedaży niepusty (ścieżka sell_item osiągalna)", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { headers: { Authorization: `Bearer ${token}` } };

  const rc = await page.request.get("/api/admin/consumables", auth);
  expect(rc.ok(), "/api/admin/consumables nie odpowiada 200 (#1158)").toBeTruthy();
  const cb = await rc.json();
  const consumables = Array.isArray(cb) ? cb : (cb.consumables ?? cb.items ?? []);
  expect(consumables.length, "brak consumables do sprzedaży (#1158)").toBeGreaterThanOrEqual(1);

  const withPrice = consumables.filter((c) => Number(c.base_price ?? c.value_gp ?? 0) > 0);
  expect(withPrice.length, "żaden consumable nie ma ceny — sell_item nic nie wypłaci (#1158)").toBeGreaterThanOrEqual(1);
});
