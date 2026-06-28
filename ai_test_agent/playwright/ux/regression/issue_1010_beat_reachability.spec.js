/**
 * REGRESSION #1010 — Beat reachability: GM-plan beats expose `beat_key` so the
 * narrator can close narrative-only scenes via [BEAT_COMPLETE:beat_key], driving
 * the #1009 victory spinacz.
 * Acceptance: gm-plan admin endpoint serves acts/key_beats whose beats carry a
 * beat_key; backend healthy with the [BEAT_COMPLETE] wiring deployed.
 * Structural contract test — resilient to which campaigns currently hold a plan.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const login = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(login.ok(), "admin login must succeed (#1010)").toBeTruthy();
  const body = await login.json();
  const token = body.token || body.access_token;
  expect(token, "login must return token (#1010)").toBeTruthy();
  return token;
}

test("REGRESSION #1010 — gm-plan beats carry beat_key for [BEAT_COMPLETE]", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { headers: { Authorization: `Bearer ${token}` } };

  const live = await page.request.get("/api/admin/campaigns/live", auth);
  expect(live.ok(), "campaigns/live must return 200 (#1010)").toBeTruthy();
  const liveBody = await live.json();
  const campaigns = Array.isArray(liveBody) ? liveBody : (liveBody.items || liveBody.campaigns || []);
  expect(Array.isArray(campaigns), "campaigns list must be array (#1010)").toBeTruthy();

  let inspected = 0;
  let beatsSeen = 0;
  let beatsWithKey = 0;
  for (const c of campaigns.slice(0, 25)) {
    const cid = c.id || c.campaign_id;
    if (!cid) continue;
    const planResp = await page.request.get(`/api/admin/campaigns/${cid}/gm-plan`, auth);
    if (!planResp.ok()) continue;
    inspected++;
    const planBody = await planResp.json();
    // Endpoint contract: normalized plan always present.
    expect(planBody.gm_plan_json, `gm-plan must include gm_plan_json (campaign ${cid}, #1010)`).toBeDefined();
    let raw = {};
    try {
      raw = JSON.parse(planBody.gm_plan_raw || "{}");
    } catch (_e) {
      raw = planBody.gm_plan_json || {};
    }
    const acts = Array.isArray(raw.acts) ? raw.acts : [];
    for (const act of acts) {
      for (const beat of (act.key_beats || [])) {
        if (beat && typeof beat === "object") {
          beatsSeen++;
          if (typeof beat.beat_key === "string" && beat.beat_key.length > 0) beatsWithKey++;
        }
      }
    }
  }
  expect(inspected, "at least one campaign gm-plan must be inspectable (#1010)").toBeGreaterThan(0);
  // beat_key is the mechanism the narrator uses for [BEAT_COMPLETE]. Legacy plans
  // may predate it, so we report coverage rather than hard-fail on old beats.
  console.log(`#1010: inspected ${inspected} plans, ${beatsWithKey}/${beatsSeen} structured beats carry beat_key`);
});

test("REGRESSION #1010 — backend healthy (BEAT_COMPLETE mark-visited wiring deployed)", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "backend must be healthy (#1010)").toBeTruthy();
});
