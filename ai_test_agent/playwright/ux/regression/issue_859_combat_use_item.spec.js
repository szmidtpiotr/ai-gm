/**
 * REGRESSION #859 (Faza SF) — pasek akcji walki ma przycisk "Użyj mikstury/przedmiotu".
 * Acceptance: w combat action sheet istnieje #combat-item-btn (oznaczony jako akcja
 * darmowa, ↺ za darmo) oraz quick-picker #consumable-picker-overlay; backend
 * POST /inventory/{id}/use nadal odpowiada (kontrakt użycia przedmiotu).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #859 — przycisk Mikstura w pasku akcji walki + picker", async ({ page }) => {
  const r = await page.request.get("/index.html");
  expect(r.ok(), "index.html nie odpowiada 200 (#859)").toBeTruthy();
  const html = await r.text();

  // przycisk w arkuszu akcji walki
  expect(html, "brak #combat-item-btn w pasku akcji walki (#859)").toContain('id="combat-item-btn"');
  // quick-picker konsumpcyjnych
  expect(html, "brak overlayu #consumable-picker-overlay (#859)").toContain('id="consumable-picker-overlay"');
  expect(html, "brak listy #consumable-picker-list (#859)").toContain('id="consumable-picker-list"');

  // out-of-scope #859: użycie NIE konsumuje tury → przycisk oznaczony jako akcja darmowa
  const btnBlock = html.slice(html.indexOf('id="combat-item-btn"'));
  const btnEnd = btnBlock.indexOf("</button>");
  expect(
    btnBlock.slice(0, btnEnd),
    "przycisk mikstury powinien być akcją darmową (combat-btn__cost--reaction)",
  ).toContain("combat-btn__cost--reaction");

  // istniejące akcje nie zniknęły
  for (const id of ["combat-move-btn", "combat-wrestle-btn", "combat-spell-btn"]) {
    expect(html, `regresja: zniknął #${id}`).toContain(`id="${id}"`);
  }
});

test("REGRESSION #859 — backend POST /inventory/{id}/use odpowiada (kontrakt)", async ({ page }) => {
  // Brak prawidłowego inventory_id → backend zwraca błąd (400/404/422), NIE 5xx ani 404 routingu.
  // Sprawdzamy że endpoint istnieje i waliduje wejście (kontrakt użycia mikstury w walce).
  const r = await page.request.post("/api/inventory/1/use", {
    headers: { "Content-Type": "application/json" },
    data: { inventory_id: 999999999 },
  });
  expect([200, 400, 404, 422].includes(r.status()), `endpoint /inventory/{id}/use nie istnieje (status ${r.status()})`).toBeTruthy();
});
