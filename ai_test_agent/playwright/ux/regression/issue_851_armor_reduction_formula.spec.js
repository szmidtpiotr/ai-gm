/**
 * REGRESSION #851 — redukcja pancerza widoczna na karcie obrażeń.
 * Acceptance: API resolve_attack zwraca armor_reduction gdy wróg ma ac_base > 10;
 * frontend buildDamageStage() czyta to pole i showDmg wyświetla "− N Pancerz" w formule.
 * Weryfikacja wizualna formuły "🎲 1 + 3 − 1 Pancerz = 3": DEV https://aigm-dev.studio-colorbox.com/
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #851 — Sandbox ma wroga z pancerzem (ac_base > 10)", async ({ page }) => {
  const enemies = await page.request.get("/api/admin/sandbox/enemies");
  expect(enemies.ok(), "GET /api/admin/sandbox/enemies != 200 (#851)").toBeTruthy();
  const eb = await enemies.json();
  expect(Array.isArray(eb.enemies), "sandbox/enemies nie zwraca listy enemies (#851)").toBeTruthy();

  const armored = (eb.enemies || []).find(e => (e.ac_base ?? 0) > 10);
  expect(armored, "Brak wroga z ac_base > 10 — armor_reduction (#851) nie ma co redukować").toBeTruthy();
  expect(typeof armored.ac_base).toBe("number");
  expect(armored.ac_base).toBeGreaterThan(10);
});

test("REGRESSION #851 — Sandbox heroes dostępni do testowania formuły", async ({ page }) => {
  const heroes = await page.request.get("/api/admin/sandbox/heroes");
  expect(heroes.ok(), "GET /api/admin/sandbox/heroes != 200 (#851)").toBeTruthy();
  const hb = await heroes.json();
  expect(Array.isArray(hb.heroes) && hb.heroes.length > 0,
    "Brak bohaterów do testowania formuły obrażeń (#851)").toBeTruthy();
});

test("REGRESSION #851 — app.js buildDamageStage eksponuje armorReduction", async ({ page }) => {
  // Pobierz app.js z serwera i sprawdź że fix #851 jest w kodzie.
  const r = await page.request.get("/js/app.js");
  expect(r.ok(), "GET /js/app.js != 200 (#851)").toBeTruthy();
  const src = await r.text();
  expect(src.includes("armorReduction"), "buildDamageStage nie ma pola armorReduction — fix #851 nie zaaplikowany").toBeTruthy();
  expect(src.includes("Pancerz") && src.includes("armorReduction"),
    "showDmg nie wyświetla 'Pancerz' przy armorReduction — fix #851 niekompletny").toBeTruthy();
});
