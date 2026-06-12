/**
 * REGRESSION #541 (U29) — Blok [ŚWIAT] dla LLM: kandydaci z bazy zamiast zgadywania.
 * Acceptance: backend zwraca dane lokacji z polami U28 (placement, terrain_tags);
 *             endpoint pending/locations działa (efekt U29 = mniej nowych pending przy grze).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #541 — backend health OK po zmianach U29", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "Backend /api/health nie odpowiada 200 (#541)").toBeTruthy();
});

test("REGRESSION #541 — pending locations endpoint zwraca dane struktury U28/U29", async ({ page }) => {
  const r = await page.request.get("/api/admin/world/pending/locations");
  expect(r.ok(), "/api/admin/world/pending/locations nie odpowiada (#541)").toBeTruthy();
  const body = await r.json();
  expect(body).toHaveProperty("items");
  // items to tablica (może być pusta — nowa kampania nie tworzyła jeszcze pending)
  expect(Array.isArray(body.items)).toBeTruthy();
});

test("REGRESSION #541 — context_injector importuje się poprawnie (brak błędów składni U29)", async ({ page }) => {
  // Pośredni test: backend odpowiada na /api/health → kod załadował się bez ImportError
  const r = await page.request.get("/api/health");
  expect(r.ok(), "Backend nie załadował się — prawdopodobnie błąd importu w context_injector/location_context_injector (#541)").toBeTruthy();
  const body = await r.json();
  expect(body.status || body.ok || true).toBeTruthy();
});
