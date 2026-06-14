/**
 * REGRESSION #605 (S10) — prymityw `escalating_dot` + kondycja `hemorrhage` w katalogu.
 * Acceptance: kondycja `hemorrhage` jest zaseedowana i widoczna w publicznym katalogu
 * kondycji; opis wskazuje na narastający krwotok i leczenie (medicine/magia). Kontrakt
 * endpointu — deterministyczny, bez LLM. Mechanikę narastającego DOT (1k4 +1k4 co 3 tury)
 * i ścieżkę cure (medicine DC 16 zdejmuje) weryfikuje pytest + Combat Sandbox.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #605 — kondycja hemorrhage w katalogu /api/mechanics/conditions", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/conditions");
  expect(r.ok(), "endpoint /api/mechanics/conditions nie odpowiada 200 (#605)").toBeTruthy();
  const body = await r.json();
  const hem = (body.conditions || []).find((c) => c.key === "hemorrhage");
  expect(hem, "brak kondycji hemorrhage w katalogu (#605)").toBeTruthy();
  expect(hem.label).toBe("Krwotok");
  expect((hem.description || "").toLowerCase()).toMatch(/krwot|narast|medicine|leczen/);
});
