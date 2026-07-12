/**
 * REGRESSION #1349 (WALKA-T1) — modal zasadzki w drodze niesie dane wroga.
 * Acceptance: GET /suggested-actions zwraca `travel_notice`; gdy to zasadzka
 * (reason startsWith "encounter") z rozpoznanym wrogiem, notice niesie
 * enemy{key,label,image_url,count} + relative_threat{glyph,label,tier} (surowy
 * ratio UKRYTY) i message z nazwą wroga; nieznany/pusty enemy_key → generyczny
 * modal (bez bloku enemy). Kontrakt endpointu — pełny flow zasadzki pokrywa
 * pytest test_issue1349_ambush_notice.py.
 */
const { test, expect } = require("@playwright/test");

const CAMPAIGN_ID = 1; // Demo (user 1) — endpoint tani, bez auth.

test("REGRESSION #1349 — travel_notice: kontrakt bloku wroga zasadzki", async ({ page }) => {
  const r = await page.request.get(`/api/campaigns/${CAMPAIGN_ID}/suggested-actions`);
  expect(r.ok(), "GET /suggested-actions musi odpowiadać 200 (#1349)").toBeTruthy();
  const body = await r.json();
  expect(body).toHaveProperty("travel_notice");

  const n = body.travel_notice;
  if (n && typeof n.reason === "string" && n.reason.startsWith("encounter")) {
    if (n.enemy) {
      // Wróg rozpoznany → pełny blok + message z nazwą.
      expect(typeof n.enemy.key).toBe("string");
      expect(typeof n.enemy.label).toBe("string");
      expect(typeof n.enemy.count).toBe("number");
      expect(n.message.includes("Stań do walki")).toBeTruthy();
      if (n.relative_threat) {
        // Surowy ratio/threat/budget NIE mogą wyciec do gracza.
        expect(n.relative_threat).toHaveProperty("glyph");
        expect(n.relative_threat).toHaveProperty("label");
        expect(n.relative_threat).toHaveProperty("tier");
        expect(n.relative_threat).not.toHaveProperty("ratio");
        expect(n.relative_threat).not.toHaveProperty("budget");
      }
    } else {
      // Nieznany/pusty enemy_key → generyczny fallback, brak bloku enemy.
      expect(n).not.toHaveProperty("relative_threat");
    }
  }
});
