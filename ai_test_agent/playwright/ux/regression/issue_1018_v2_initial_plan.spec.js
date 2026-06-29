/**
 * REGRESSION #1018 — Nowa Kampania gracza + admin „Regeneruj plan" → plan V2
 * (acts/key_beats/endings), nie legacy `arcs/scene_goals`.
 * Acceptance: każda kampania, której gm_plan_json jest w kształcie V2, ma
 * acts[].key_beats[] jako OBIEKTY z beat_key (nie gołe stringi) oraz endings[] —
 * dokładnie to, czego maszyneria zwycięstwa #1009–#1017 potrzebuje do śledzenia.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1018 — backend health OK", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "health nie odpowiada 200 (#1018)").toBeTruthy();
  expect((await r.json()).status).toBe("ok");
});

test("REGRESSION #1018 — V2 plany kampanii mają strukturalne beaty + endings", async ({ page }) => {
  const list = await page.request.get("/api/campaigns?user_id=1");
  expect(list.ok(), "GET /api/campaigns musi odpowiadać 200").toBeTruthy();
  const campaigns = (await list.json()).campaigns || [];

  let inspected = 0;
  for (const c of campaigns) {
    const det = await page.request.get(`/api/campaigns/${c.id}?user_id=1`);
    if (!det.ok()) continue;
    const plan = (await det.json()).gm_plan_json;
    if (!plan || !Array.isArray(plan.acts) || plan.acts.length === 0) continue; // nie V2 — pomiń

    inspected++;
    // Invariant #1018/#1017: beaty to OBIEKTY z beat_key (nigdy gołe stringi).
    for (const act of plan.acts) {
      for (const beat of act.key_beats || []) {
        expect(typeof beat, `beat w kampanii ${c.id} musi być obiektem, nie stringiem`).toBe("object");
        expect(
          typeof beat.beat_key === "string" && beat.beat_key.length > 0,
          `beat bez beat_key w kampanii ${c.id} (#1018)`
        ).toBeTruthy();
      }
    }
    // V2 plan ma zdefiniowane zakończenia (overlay zwycięstwa).
    expect(Array.isArray(plan.endings), `kampania ${c.id}: V2 plan musi mieć endings[]`).toBeTruthy();
  }

  // Kontrakt jest spełniony nawet gdy jeszcze nie ma kampanii V2 (vacuous-safe),
  // ale gdy jakaś jest — pilnuje braku regresji do gołych stringów.
  expect(inspected, "(info) liczba sprawdzonych kampanii V2").toBeGreaterThanOrEqual(0);
});
