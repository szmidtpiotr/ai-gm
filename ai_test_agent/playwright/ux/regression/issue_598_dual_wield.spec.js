/**
 * REGRESSION #598 — mechanika walki dwoma broniami (dual-wield) istnieje.
 * Acceptance: skill `dual_wield` jest w katalogu umiejętności (GET /api/mechanics/skills),
 * co potwierdza, że cecha bojowa bramkująca drugi atak off-hand jest wdrożona i grantowalna.
 * Pełna mechanika (2 ataki / parowanie) pokryta pytestem test_issue598_dual_wield.py.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #598 — skill dual_wield w katalogu mechanik", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/skills");
  expect(r.ok(), "endpoint /api/mechanics/skills nie odpowiada 200 (#598)").toBeTruthy();
  const body = await r.json();
  const skills = Array.isArray(body) ? body : (body.skills || body.items || []);
  const keys = skills.map((s) => String(s.key || s.id || "").toLowerCase());
  expect(keys, "brak skilla 'dual_wield' w katalogu (#598)").toContain("dual_wield");

  const dw = skills.find((s) => String(s.key || s.id || "").toLowerCase() === "dual_wield");
  // linked_stat = DEX (broń lekka/finesse) — kontrakt cechy
  expect(String(dw.linked_stat || dw.stat || "").toUpperCase()).toBe("DEX");
});
