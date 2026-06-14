/**
 * REGRESSION #604 (S9) — prymityw `stacking_levels` + kondycja `exhausted` w katalogu.
 * Acceptance: kondycja `exhausted` jest zaseedowana i widoczna w publicznym katalogu
 * kondycji; opis wskazuje na poziomy wyczerpania / omdlenie. Kontrakt endpointu —
 * deterministyczny, bez LLM. Mechanikę poziomów (×poziom, próg 2 = block_action)
 * weryfikuje pytest + Combat Sandbox.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #604 — kondycja exhausted w katalogu /api/mechanics/conditions", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/conditions");
  expect(r.ok(), "endpoint /api/mechanics/conditions nie odpowiada 200 (#604)").toBeTruthy();
  const body = await r.json();
  const exhausted = (body.conditions || []).find((c) => c.key === "exhausted");
  expect(exhausted, "brak kondycji exhausted w katalogu (#604)").toBeTruthy();
  expect(exhausted.label).toBe("Wyczerpany");
  expect((exhausted.description || "").toLowerCase()).toMatch(/poziom|omdl|wyczerp/);
});
