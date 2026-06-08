/**
 * REGRESSION #384 (D9) — Hub kampanii: 5 trybów + dostępność.
 * /api/campaign-modes zwraca 5 trybów (nowa/gotowa/loch/loch_kafelki/multiplayer)
 * z flagą `available`, by hub nie prowadził w broken state.
 * Acceptance (deterministyczny): endpoint zwraca dokładnie 5 trybów z poprawnym kontraktem.
 */
const { test, expect } = require("@playwright/test");

const EXPECTED = ["nowa", "gotowa", "loch", "loch_kafelki", "multiplayer"];

test("REGRESSION #384 — 5 trybów huba z flagą dostępności", async ({ page }) => {
  const r = await page.request.get("/api/campaign-modes");
  expect(r.ok(), "/campaign-modes nie odpowiada 200 (#384)").toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.modes), "modes musi być tablicą (#384)").toBeTruthy();
  const keys = body.modes.map(m => m.key);
  for (const k of EXPECTED) {
    expect(keys.includes(k), `brak trybu '${k}' (#384)`).toBeTruthy();
  }
  for (const m of body.modes) {
    expect(typeof m.available, `tryb ${m.key} bez bool available (#384)`).toBe("boolean");
    expect(m.label, `tryb ${m.key} bez label (#384)`).toBeTruthy();
  }
  // Nowa i Multiplayer zawsze dostępne.
  const byKey = Object.fromEntries(body.modes.map(m => [m.key, m]));
  expect(byKey.nowa.available, "nowa musi być dostępna (#384)").toBeTruthy();
  expect(byKey.multiplayer.available, "multiplayer musi być dostępny (#384)").toBeTruthy();
});
