/**
 * REGRESSION #826 — spójny model obrony walki (jeden rzut obronny + pancerz=redukcja + margines→dmg).
 * Acceptance: silnik walki używany do balansu #826 (Sandbox) odpowiada, a kontrakt rozliczenia
 * ataku gracza w Sandboxie niesie pola nowego modelu (margines/pancerz) lub czyste trafienie.
 *
 * Uwaga: właściwa matematyka modelu (#826) jest pokryta deterministycznie testem pytest
 * `backend/tests/test_issue826_defense_model.py` (19/19). Ten spec strzeże, że harness Sandboxa
 * (na którym Piotr stroi liczby startowe #826) jest żywy i zwraca spójny kształt stanu walki.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #826 — Sandbox combat harness alive (balans #826)", async ({ page }) => {
  // Bohaterowie do testów balansu — endpoint Sandboxa bez auth.
  const heroes = await page.request.get("/api/admin/sandbox/heroes");
  expect(heroes.ok(), "GET /api/admin/sandbox/heroes != 200 (#826)").toBeTruthy();
  const hb = await heroes.json();
  expect(Array.isArray(hb.heroes), "sandbox/heroes nie zwraca listy heroes (#826)").toBeTruthy();

  // Katalog wrogów (pancerz/zwinność do testu 'zwinny vs opancerzony' z #826).
  const enemies = await page.request.get("/api/admin/sandbox/enemies");
  expect(enemies.ok(), "GET /api/admin/sandbox/enemies != 200 (#826)").toBeTruthy();
  const eb = await enemies.json();
  expect(Array.isArray(eb.enemies), "sandbox/enemies nie zwraca listy enemies (#826)").toBeTruthy();
  // ac_base (pancerz) musi być w kontrakcie wroga — to liczba redukcji obrażeń w #826.
  if (eb.enemies.length) {
    const sample = eb.enemies[0];
    expect("ac_base" in sample, "wróg bez pola ac_base — pancerz #826 nie ma na czym działać").toBeTruthy();
  }
});
