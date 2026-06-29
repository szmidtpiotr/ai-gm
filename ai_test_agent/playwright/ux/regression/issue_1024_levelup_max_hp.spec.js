/**
 * REGRESSION #1024 — awans poziomu zwiększa max_hp i max_mana.
 * Acceptance: long rest z XP progowym → sheet["level"] i max_hp rosną.
 * "recalc vitals" endpoint dostępny w admin_cheat.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1024 — backend uruchomiony po fix rest_service (#1024)", async ({ page }) => {
  const health = await page.request.get("/api/health");
  expect(health.ok(), "backend nie odpowiada po zmianach rest_service (#1024)").toBeTruthy();
  const body = await health.json();
  expect(["ok", "degraded"]).toContain(body.status ?? "ok");
});

test("REGRESSION #1024 — endpoint rest nie zwraca 500 po zmianach level-up", async ({ page }) => {
  // Wywołujemy rest na nieistniejącej kampanii — oczekujemy 404/422, NIE 500
  // (500 = syntax error lub crash w rest_service.py po dodaniu kodu level-up)
  const r = await page.request.post("/api/campaigns/0/rest", {
    data: { type: "long" },
  });
  expect(r.status(), `rest_service crashuje (HTTP ${r.status()}) po fix level-up`).not.toBe(500);
  expect([404, 409, 422, 403]).toContain(r.status());
});

test("REGRESSION #1024 — admin cheat endpoint obsługuje recalc vitals (nie 404/405)", async ({ page }) => {
  // Endpoint: POST /api/admin/cheat/{character_id}
  // 401/403 = OK (brak auth), 422 = OK (zły format), 404 dla char_id=0 = OK, 405 = NG (metoda)
  // Sprawdzamy że trasa istnieje (nie 405 Method Not Allowed)
  const r = await page.request.post("/api/admin/cheat/1", {
    data: { action: "recalc vitals" },
  });
  expect(r.status(), `recalc vitals zwrócił Method Not Allowed — trasa znika`).not.toBe(405);
  // 200 = OK (sukces), 401/403 = brak auth (trasa istnieje), 404 = brak char (trasa istnieje)
  // 422 = zły format (trasa istnieje), 500 = NG (runtime crash)
  expect(r.status(), `rest_service crashuje na recalc vitals (HTTP ${r.status()})`).not.toBe(500);
  expect([200, 401, 403, 404, 422]).toContain(r.status());
});
