/**
 * REGRESSION #1348 (WALKA-T4) — poll GET /combat nie może po cichu gubić stanu końca walki.
 * Acceptance: endpoint zawsze zwraca 200 + kopertę {active, combat}; gdy walka istnieje,
 * `active` liczone z status==='active', a zakończony snapshot (status='ended') niesie
 * `ended_reason` (nigdy {active:false, combat:null} przy realnym końcu). Pełny e2e
 * (zabicie wroga → modal zwycięstwa + loot) pokrywa pytest test_issue1348_combat_vanish.py.
 */
const { test, expect } = require("@playwright/test");

// Kampania Demo (user 1) — zwykle istnieje na DEV. Endpoint jest tani i bez auth.
const CAMPAIGN_ID = 1;

test("REGRESSION #1348 — GET /combat zwraca kopertę {active, combat} (200, nie 404)", async ({ page }) => {
  const r = await page.request.get(`/api/campaigns/${CAMPAIGN_ID}/combat`);
  expect(r.ok(), "poll /combat musi odpowiadać 200 (#1348)").toBeTruthy();
  const body = await r.json();
  // Koperta zawsze obecna — brak walki NIE może być 404 (spam polla).
  expect(body).toHaveProperty("active");
  expect(body).toHaveProperty("combat");
  expect(typeof body.active).toBe("boolean");

  // Gdy snapshot walki obecny — spójność active↔status; ended niesie ended_reason.
  if (body.combat) {
    const st = body.combat.status;
    expect(body.active).toBe(st === "active");
    if (st === "ended") {
      expect(
        body.combat.ended_reason,
        "zakończona walka musi nieść ended_reason (nie cichy vanish, #1348)",
      ).toBeTruthy();
    }
  }
});
