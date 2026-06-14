/**
 * REGRESSION #563 (U15) — wound tiers single source of truth.
 * Acceptance: /api/config/wound-thresholds zwraca pełną tabelę tierów
 * (label + color + penalty), a label i kara pochodzą z tego samego tieru
 * (label↔kara nigdy się nie rozjadą). Frontend single-source'uje stąd.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #563 — endpoint zwraca pełną tabelę tierów ran", async ({ page }) => {
  const r = await page.request.get("/api/config/wound-thresholds");
  expect(r.ok(), "endpoint /config/wound-thresholds nie odpowiada 200 (#563)").toBeTruthy();
  const body = await r.json();

  // back-compat: płaskie progi nadal obecne
  expect(body.healthy_pct).toBe(75);
  expect(body.moderate_pct).toBe(50);
  expect(body.critical_pct).toBe(25);

  // U15: pełna tabela tierów
  expect(Array.isArray(body.tiers), "brak tablicy tiers (#563)").toBeTruthy();
  expect(body.tiers.length).toBe(5);

  const byTier = Object.fromEntries(body.tiers.map((t) => [t.tier, t]));
  // każdy tier ma label/color/penalty (poza healthy — label null)
  expect(byTier.healthy.label).toBeNull();
  expect(byTier.healthy.penalty).toBe(0);
  expect(byTier.minor.label).toBe("Ranny");
  expect(byTier.minor.penalty).toBe(-1);
  expect(byTier.moderate.label).toBe("Ciężko Ranny");
  expect(byTier.moderate.penalty).toBe(-2);
  expect(byTier.serious.penalty).toBe(-4);
  expect(byTier.near_death.label).toBe("Na Skraju Śmierci");

  // każdy tier ma kolor #hex
  for (const t of body.tiers) {
    expect(String(t.color)).toMatch(/^#[0-9a-fA-F]{6}$/);
  }
});
