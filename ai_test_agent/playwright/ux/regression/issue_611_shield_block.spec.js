/**
 * REGRESSION #611 (S16) — reakcja `shield_block` (blok tarczą).
 * Acceptance: skill `shield_block` (STR) jest w katalogu skilli, a endpoint
 * declare-reaction akceptuje reaction_type=shield_block (walidacja: nieznany
 * typ → 400; brak aktywnej walki → 400, ale NIE „unknown reaction_type").
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #611 — skill shield_block w katalogu (STR)", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/skills");
  expect(r.ok(), "/api/mechanics/skills nie odpowiada 200 (#611)").toBeTruthy();
  const body = await r.json();
  const byKey = Object.fromEntries((body.skills || []).map((s) => [s.key, s.linked_stat]));
  expect(byKey["shield_block"], "brak skilla shield_block w katalogu (#611)").toBe("STR");
  // S15 dodge nadal obecny (XOR partner) — brak regresji
  expect(byKey["dodge"], "dodge zniknął z katalogu (regresja #610)").toBe("DEX");
});

test("REGRESSION #611 — declare-reaction zna typ shield_block (walidacja przeszła)", async ({ page }) => {
  // Bez aktywnej walki backend zwróci 400, ale komunikat MUSI dotyczyć braku walki,
  // a NIE „unknown reaction_type" — to potwierdza, że shield_block jest rozpoznawany.
  const r = await page.request.post("/api/campaigns/999999/combat/declare-reaction", {
    data: { reaction_type: "shield_block" },
    headers: { "Content-Type": "application/json" },
  });
  const detail = (await r.json().catch(() => ({})))?.detail || "";
  expect(String(detail).toLowerCase()).not.toContain("unknown reaction_type");
});

test("REGRESSION #611 — declare-reaction odrzuca nieznany typ reakcji", async ({ page }) => {
  const r = await page.request.post("/api/campaigns/999999/combat/declare-reaction", {
    data: { reaction_type: "teleport" },
    headers: { "Content-Type": "application/json" },
  });
  expect(r.status(), "nieznany typ reakcji powinien dać 400 (#611)").toBe(400);
  const detail = (await r.json().catch(() => ({})))?.detail || "";
  expect(String(detail).toLowerCase()).toContain("unknown reaction_type");
});
