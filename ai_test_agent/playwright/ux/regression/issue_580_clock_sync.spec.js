/**
 * REGRESSION #580 — zegar gry jest spójny (pojedyncze źródło prawdy).
 * Kontrakt /clock: ingame_hours = (day-1)*24 + hour. Sama synchronizacja kolumny
 * `game_sessions.ingame_hours` z session_flags jest pokryta pytestem (read wewnętrzny).
 * Acceptance: /clock zwraca spójne day/hour wyprowadzone z ingame_hours.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #580 — /clock spójny (day/hour z ingame_hours)", async ({ page }) => {
  const r = await page.request.get("/api/campaigns/74/clock");
  expect(r.ok(), "endpoint /clock nie odpowiada 200").toBeTruthy();
  const c = await r.json();
  expect(typeof c.ingame_hours).toBe("number");
  expect(c.ingame_hours).toBeGreaterThanOrEqual(0);
  // Spójność wyprowadzeń (jedno źródło): day i hour pochodzą z ingame_hours.
  expect(c.hour).toBe(c.ingame_hours % 24);
  expect(c.day).toBe(Math.floor(c.ingame_hours / 24) + 1);
});
