/**
 * REGRESSION #997 (NAZEWNICTWO) — Konwencja nazewnicza MIX słowiańsko-germański.
 * Acceptance: API świata działa; pending locations nie zawierają starych offenderów
 * (Cieszowice/Wolanka/Brzezino/Strażyn). Nowe nazwy w world_map_seed.json + promptach.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #997 — /api/admin/world/pending/counts odpowiada 200", async ({ page }) => {
  const r = await page.request.get("/api/admin/world/pending/counts");
  expect(r.ok(), "endpoint pending/counts nie odpowiada 200 (#997)").toBeTruthy();
  const body = await r.json();
  expect(typeof body.locations, "brak pola locations w pending/counts (#997)").toBe("number");
});

test("REGRESSION #997 — pending locations nie zawierają offenderów", async ({ page }) => {
  const r = await page.request.get("/api/admin/world/pending/locations");
  expect(r.ok(), "endpoint pending/locations nie odpowiada 200 (#997)").toBeTruthy();
  const body = await r.json();
  const items = Array.isArray(body) ? body : (body.items || body.locations || []);
  const offenders = ["Cieszowice", "Wolanka", "Brzezino", "Strażyn"];
  for (const off of offenders) {
    const found = items.some(l => (l.label || "") === off);
    expect(found, `Offender '${off}' nadal w pending locations (#997)`).toBeFalsy();
  }
});
