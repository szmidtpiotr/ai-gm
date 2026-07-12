/**
 * REGRESSION #1324 (Arkanowa Bariera) — skill arcane_ward istnieje w katalogu jako
 * reakcja bojowa INT (magiczny odpowiednik Uniku). Weryfikuje kontrakt katalogu skilli,
 * z którego okno reakcji SF10 buduje trzecią opcję dla maga.
 * Acceptance: /api/mechanics/skills zwraca arcane_ward z linked_stat=INT.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1324 — arcane_ward w katalogu skilli (INT, reakcja maga)", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/skills");
  expect(r.ok(), "katalog skilli nie odpowiada 200 (#1324)").toBeTruthy();
  const body = await r.json();
  const rows = Array.isArray(body) ? body : body.skills || [];
  const ward = rows.find((s) => s && s.key === "arcane_ward");
  expect(ward, "brak skilla arcane_ward w katalogu (#1324)").toBeTruthy();
  expect(ward.linked_stat, "arcane_ward musi być testem INT").toBe("INT");
  expect(String(ward.label || "").toLowerCase()).toContain("bariera");
});
