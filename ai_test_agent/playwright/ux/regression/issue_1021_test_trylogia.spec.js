/**
 * REGRESSION #1021 — minimalna grywalna kampania testowa (2 akty × 1 beat).
 * Weryfikuje, że opublikowany seed-szablon "[TEST] Przejazd 2-akty — trylogia #1009"
 * jest widoczny w pickerze Gotowej Kampanii i niesie winnable plan V2:
 * 2 akty, każdy 1 krytyczny beat (visit_location / talk_to_npc, wildcard),
 * endings[] z type=='primary'. Deterministyczny kontrakt — bez LLM.
 */
const { test, expect } = require("@playwright/test");

const TITLE = "[TEST] Przejazd 2-akty — trylogia #1009";

test("REGRESSION #1021 — seed-szablon [TEST] widoczny i winnable w pickerze", async ({ page }) => {
  const r = await page.request.get("/api/campaign-templates");
  expect(r.ok(), "GET /api/campaign-templates nie odpowiada 200 (#1021)").toBeTruthy();
  const body = await r.json();
  const items = body.items || [];
  const tpl = items.find((t) => (t.title || "").trim() === TITLE);
  expect(tpl, `szablon "${TITLE}" musi być w pickerze publikowanych kampanii`).toBeTruthy();

  const plan = typeof tpl.gm_plan_json === "string"
    ? JSON.parse(tpl.gm_plan_json)
    : tpl.gm_plan_json || tpl.plan || {};
  const acts = plan.acts || plan.arcs || [];
  expect(acts.length, "spec: dokładnie 2 akty").toBe(2);

  // Akt 1 — reach_first_place / visit_location / wildcard / krytyczny
  const b1 = acts[0].key_beats || [];
  expect(b1.length).toBe(1);
  expect(b1[0].beat_key).toBe("reach_first_place");
  expect(b1[0].objective_type).toBe("visit_location");
  expect(b1[0].objective_value || "").toBe("");
  expect(b1[0].optional === true).toBeFalsy();

  // Akt 2 — meet_the_elder / talk_to_npc / wildcard / krytyczny
  const b2 = acts[1].key_beats || [];
  expect(b2.length).toBe(1);
  expect(b2[0].beat_key).toBe("meet_the_elder");
  expect(b2[0].objective_type).toBe("talk_to_npc");
  expect(b2[0].objective_value || "").toBe("");
  expect(b2[0].optional === true).toBeFalsy();

  // endings[] z ≥1 primary → overlay zwycięstwa
  const endings = plan.endings || [];
  expect(endings.some((e) => e.type === "primary"),
    "spec: 1 ending type=='primary'").toBeTruthy();
});
