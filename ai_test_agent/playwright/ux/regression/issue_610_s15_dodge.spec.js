/**
 * REGRESSION #610 (S15) — system reakcji (pre-deklaracja) + skill `dodge`.
 * Acceptance: skill `dodge` (DEX) jest w katalogu umiejętności, a endpoint pre-deklaracji
 * reakcji jest podpięty (route istnieje — 400 przy braku aktywnej walki, nie 404).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #610 — skill dodge w katalogu (DEX)", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/skills");
  expect(r.ok(), "/api/mechanics/skills nie odpowiada 200 (#610)").toBeTruthy();
  const body = await r.json();
  const skills = Array.isArray(body.skills) ? body.skills : [];
  const dodge = skills.find((s) => s.key === "dodge");
  expect(dodge, "skill 'dodge' brak w katalogu (#610 — seed migrations_admin)").toBeTruthy();
  expect(String(dodge.linked_stat).toUpperCase(), "dodge musi być DEX").toBe("DEX");
});

test("REGRESSION #610 — endpoint declare-reaction podpięty (route istnieje)", async ({ page }) => {
  // Bez aktywnej walki backend zwraca 400 ('no active combat'), nie 404 — dowód że route żyje.
  const r = await page.request.post("/api/campaigns/999999/combat/declare-reaction", {
    data: { reaction_type: "dodge" },
  });
  expect(r.status(), "declare-reaction route nieobecny (404) zamiast 400 (#610)").not.toBe(404);
  expect([400, 422].includes(r.status()), `oczekiwano 400/422, było ${r.status()} (#610)`).toBeTruthy();
});
