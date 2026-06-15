/**
 * REGRESSION #645 (B4) — Łotrzyk Sneak Attack reużywa kondycji `hidden` (S19), bez duplikatu stanu.
 * Sneak attack to cecha klasy liczona w silniku walki (combat_service._sneak_attack_bonus,
 * pole `sneak_attack` doliczane ponad `ambush_bonus`). Pełny dowód obrażeń = pytest
 * test_issue645_rogue_sneak_attack.py (deterministyczny). Tu pilnujemy kontraktu danych:
 * okno zasadzki nadal istnieje jako kondycja `hidden`, i NIE powstał żaden duplikat stanu
 * typu `sneak`/`sneak_attack` (zasada FAZY S: reużycie kondycji, nie duplikat).
 * Acceptance: `/api/mechanics/conditions` zawiera `hidden`; brak osobnej kondycji sneak.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #645 — sneak attack reużywa hidden, brak duplikatu kondycji", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/conditions");
  expect(r.ok(), "endpoint kondycji nie odpowiada 200 (#645)").toBeTruthy();
  const body = await r.json();
  const conditions = Array.isArray(body) ? body : body.conditions || [];
  const keys = conditions.map((c) => String(c.key || "").toLowerCase());

  // Okno zasadzki (na którym opiera się sneak attack) nadal istnieje.
  expect(keys, "kondycja `hidden` (okno zasadzki) musi istnieć (#645/#614)").toContain("hidden");

  // Sneak attack to cecha klasy w silniku — NIE nowa kondycja. Brak duplikatu stanu.
  const dup = keys.filter((k) => k === "sneak" || k === "sneak_attack");
  expect(dup, "sneak attack nie powinien tworzyć osobnej kondycji (#645)").toEqual([]);
});
