/**
 * REGRESSION #568 — „brak lootu po zwycięstwie": RNG, nie bug.
 * Werdykt: `roll_loot` rzuca każdy wpis tabeli niezależnie wg wagi (loot_enemy:
 * bandaż 50% / pochodnia 40% / sztylet 15%) → P(nic) ≈ 25%. Logika rolla pokryta pytest
 * (`test_issue568_loot_rng_not_bug.py`, 3/3). Ten spec to kotwica danych: tabela loot_enemy
 * NADAL ma wpisy z sensownymi wagami — czyli loot W OGÓLE może wypaść (gdyby wpisów nie było,
 * „brak lootu" byłby gwarantowany = realny bug).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #568 — loot_enemy ma wpisy z wagami (loot może wypaść)", async ({ page }) => {
  const login = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  const { token } = await login.json();
  const r = await page.request.get("/api/admin/loot-tables/loot_enemy/entries", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "endpoint entries nie odpowiada 200 (#568)").toBeTruthy();
  const body = await r.json();
  const items = body.items || body.data || [];
  expect(items.length, "tabela loot_enemy pusta → loot nigdy nie wypadnie = bug (#568)").toBeGreaterThan(0);
  // Każdy wpis ma dodatnią wagę (szansę dropu)
  for (const e of items) {
    expect(Number(e.weight), `wpis ${e.source_key} ma wagę ≤0 (#568)`).toBeGreaterThan(0);
  }
});
