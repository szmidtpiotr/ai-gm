/**
 * REGRESSION #595 — Gracz może wybrać cel ataku w walce z wieloma wrogami.
 * Backend wcześniej ignorował `target_id`; teraz `resolve-attack` przyjmuje to pole.
 * Acceptance: endpoint /combat/resolve-attack akceptuje payload z `target_id`
 * (kontrakt schematu) — odpowiada błędem domenowym "no active combat" (400),
 * NIE błędem walidacji schematu (422). 422 = pole odrzucone = regresja #595.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #595 — resolve-attack akceptuje target_id w schemacie", async ({ page }) => {
  // Kampania bez aktywnej walki → silnik ma odrzucić domenowo (no active combat),
  // ale tylko PO sparsowaniu body. Jeśli `target_id` nie byłby w schemacie,
  // FastAPI zwróciłby 422 zanim dotrze do logiki silnika.
  const resp = await page.request.post(
    "/api/campaigns/99999999/combat/resolve-attack",
    {
      data: { raw_d20: 12, attacker: "player", target_id: "e1" },
      headers: { "Content-Type": "application/json" },
    },
  );
  // Kluczowa asercja: NIE 422 (schemat zaakceptował target_id).
  expect(resp.status(), "target_id odrzucony przez schemat (#595 regresja)").not.toBe(422);
  // Oczekiwany błąd domenowy: brak aktywnej walki → 400.
  expect(resp.status(), "spodziewany 400 'no active combat' (#595)").toBe(400);
  const body = await resp.json().catch(() => ({}));
  expect(
    String(body.detail || "").toLowerCase().includes("no active combat"),
    "detail powinien wskazywać brak aktywnej walki (#595)",
  ).toBeTruthy();
});
