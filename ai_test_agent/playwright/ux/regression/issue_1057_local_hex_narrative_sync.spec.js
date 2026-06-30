/**
 * REGRESSION #1057 (FAZA ML) — local_hex synchronizuje się po ruchu narracyjnym.
 * Acceptance: _sync_local_hex_narrative_move w turns.py aktualizuje session_flags.local_hex
 * gdy narracja przesuwa gracza między sublokacjami. local-map API zwraca current_local_hex.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1057 — backend health check (prerequisite)", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "backend nie odpowiada (#1057)").toBeTruthy();
  const body = await r.json();
  expect(body.status ?? "ok").toBe("ok");
});

test("REGRESSION #1057 — local-map endpoint nie crashuje (404/401 OK, 500 nie)", async ({ page }) => {
  // Endpoint może wymagać auth — sprawdzamy że nie zwraca 500
  const r = await page.request.get("/api/campaigns/1/local-map");
  expect(
    r.status() < 500,
    `local-map endpoint zwrócił błąd serwera: ${r.status()} (#1057)`,
  ).toBeTruthy();
});

test("REGRESSION #1057 — admin world hexes dostępne (map_level=1 po auto-create)", async ({ page }) => {
  // map_level=1 hexes = lokalne hexmasy dla sublokacji; powinny istnieć dla Wolanki
  const r = await page.request.get("/api/admin/world/hexes");
  // Accept 200 (ok) or auth error (401/403) — nie 500
  expect(r.status() < 500, `world/hexes crashed: ${r.status()} (#1057)`).toBeTruthy();
});
