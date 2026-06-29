/**
 * REGRESSION #1019 — seed campaign templates expose endings[] + optional side beats.
 * Acceptance: each published seed template ("Pierwsze Kroki", "Przeklęte Ziemie", "Cień Licza")
 * carries gm_plan_json.endings (≥1 primary, with title) and ≥1 optional beat, while every arc
 * keeps ≥1 critical (non-optional) beat so it can still auto-close.
 */
const { test, expect } = require("@playwright/test");

const SEED_TITLES = ["Pierwsze Kroki", "Przeklęte Ziemie", "Cień Licza"];

test("REGRESSION #1019 — seed templates have endings + optional beats", async ({ page }) => {
  const r = await page.request.get("/api/campaign-templates");
  expect(r.ok(), "GET /api/campaign-templates nie odpowiada 200 (#1019)").toBeTruthy();
  const body = await r.json();
  const items = body.items || [];

  for (const title of SEED_TITLES) {
    const tpl = items.find((t) => t.title === title);
    expect(tpl, `brak seed-template "${title}" w odpowiedzi`).toBeTruthy();

    const plan = tpl.gm_plan_json || {};

    // endings[] — ≥1 primary z tytułem
    const endings = plan.endings || [];
    expect(Array.isArray(endings) && endings.length > 0, `${title}: brak endings[]`).toBeTruthy();
    const primary = endings.find((e) => e.type === "primary");
    expect(primary, `${title}: brak ending type=primary`).toBeTruthy();
    expect(!!primary.title, `${title}: primary ending bez tytułu`).toBeTruthy();

    // każdy arc: ≥1 krytyczny beat; w całym planie ≥1 optional
    const arcs = plan.arcs || plan.acts || [];
    let optionalCount = 0;
    for (const arc of arcs) {
      const beats = (arc.key_beats || []).filter((b) => b && typeof b === "object");
      const critical = beats.filter((b) => b.optional !== true);
      expect(critical.length > 0, `${title}/${arc.id}: akt bez krytycznego beatu`).toBeTruthy();
      optionalCount += beats.filter((b) => b.optional === true).length;
    }
    expect(optionalCount > 0, `${title}: brak beatu optional:true`).toBeTruthy();
  }
});
