/**
 * REGRESSION #1017 (Forge structured beats) — acts[].key_beats[] muszą być OBIEKTAMI z beat_key,
 * nigdy gołymi stringami. Po #1017 generator Forge produkuje strukturę PlotBeat, a stare plany
 * list[str] są podnoszone do obiektów przy walidacji.
 * Acceptance: każdy zapisany plan kampanii (gm_plan_json.acts[].key_beats[]) ma beaty jako obiekty
 * z niepustym beat_key; brak gołych stringów.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1017 — key_beats w zapisanych planach to obiekty z beat_key", async ({ page }) => {
  const r = await page.request.get("/api/campaign-templates");
  expect(r.ok(), "endpoint /api/campaign-templates nie odpowiada 200 (#1017)").toBeTruthy();
  const body = await r.json();
  const items = body.items || [];

  let checkedBeats = 0;
  for (const tpl of items) {
    let plan = tpl.gm_plan_json;
    if (typeof plan === "string") {
      try { plan = JSON.parse(plan); } catch { continue; }
    }
    if (!plan || !Array.isArray(plan.acts)) continue;
    for (const act of plan.acts) {
      for (const beat of (act.key_beats || [])) {
        checkedBeats++;
        expect(typeof beat, `beat to goły string w planie "${tpl.title}" (#1017)`).toBe("object");
        expect(beat.beat_key, `beat bez beat_key w planie "${tpl.title}" (#1017)`).toBeTruthy();
      }
    }
  }
  // Smoke: endpoint kontrakt OK nawet gdy żaden plan nie ma jeszcze beatów.
  expect(Array.isArray(items), "lista szablonów nie jest tablicą").toBeTruthy();
  console.log(`#1017 — sprawdzono ${checkedBeats} beatów w ${items.length} szablonach`);
});
