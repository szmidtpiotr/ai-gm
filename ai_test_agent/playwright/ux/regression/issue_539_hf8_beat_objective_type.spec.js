/**
 * REGRESSION #539 (HF-8) — Beat auto-complete działa w Gotowej Kampanii.
 * Acceptance: szablony kampanii mają objective_type na beatach;
 * endpoint /api/campaign-templates zwraca opublikowane szablony z key_beats zawierającymi objective_type.
 * Note: test "Pierwsze Kroki" usunięty — szablon zastąpiony auto-onboardingiem.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #539 — Przeklęte Ziemie beats have objective_type", async ({ page }) => {
  const r = await page.request.get("/api/campaign-templates");
  expect(r.ok()).toBeTruthy();
  const body = await r.json();
  const templates = body.items || body;

  const przekleta = templates.find(t => t.title === "Przeklęte Ziemie" && t.status === "published");
  expect(przekleta, "Szablon 'Przeklęte Ziemie' musi istnieć").toBeTruthy();

  const plan = typeof przekleta.gm_plan_json === "string"
    ? JSON.parse(przekleta.gm_plan_json)
    : przekleta.gm_plan_json;

  const beats = plan.arcs?.[0]?.key_beats || [];
  const confront = beats.find(b => b.beat_key === "confront_evil");
  expect(confront?.objective_type, "confront_evil → kill_enemy").toBe("kill_enemy");

  const seek = beats.find(b => b.beat_key === "seek_origin");
  expect(seek?.objective_type, "seek_origin → talk_to_npc").toBe("talk_to_npc");

  // lich_awakens w Cień Licza celowo nie ma objective_type (pure narrative)
  const lichTemplate = templates.find(t => t.title === "Cień Licza" && t.status === "published");
  const lichPlan = typeof lichTemplate?.gm_plan_json === "string"
    ? JSON.parse(lichTemplate.gm_plan_json)
    : lichTemplate?.gm_plan_json;
  const lichBeats = lichPlan?.arcs?.[0]?.key_beats || [];
  const lichAwakens = lichBeats.find(b => b.beat_key === "lich_awakens");
  // lich_awakens must NOT have objective_type (remains pure LLM narrative beat)
  expect(lichAwakens?.objective_type, "lich_awakens musi zostać bez objective_type").toBeUndefined();
});
