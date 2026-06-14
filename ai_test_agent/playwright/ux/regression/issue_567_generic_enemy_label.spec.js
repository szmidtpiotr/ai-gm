/**
 * REGRESSION #567 — generyczny placeholder walki nie pokazuje dosłownego „Wróg".
 * Seed `key='enemy'` ma neutralną etykietę („Napastnik"); żaden wróg w katalogu nie nazywa się „Wróg".
 * Acceptance: katalog wrogów nie zawiera labelu „Wróg"; wpis 'enemy' = „Napastnik".
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #567 — brak dosłownego 'Wróg' w katalogu wrogów", async ({ page }) => {
  const r = await page.request.get("/api/admin/sandbox/enemies");
  expect(r.ok(), "endpoint /api/admin/sandbox/enemies nie odpowiada 200").toBeTruthy();
  const body = await r.json();
  const enemies = body.enemies || [];
  expect(enemies.length).toBeGreaterThan(0);

  const wrog = enemies.filter((e) => String(e.label).trim().toLowerCase() === "wróg");
  expect(wrog, `wróg-placeholder nadal w katalogu: ${JSON.stringify(wrog)}`).toHaveLength(0);

  const generic = enemies.find((e) => e.key === "enemy");
  if (generic) {
    expect(generic.label).toBe("Napastnik");
  }
});
