/**
 * REGRESSION #1060 (FORGE) — validate-plan endpoint zwraca strukturalne błędy/ostrzeżenia dla planów GM.
 * Acceptance: POST /api/admin/forge/validate-plan istnieje, zwraca issues[] z type/code/act_number/beat_key.
 */
const { test, expect } = require("@playwright/test");

const ADMIN_LOGIN = { username: "demo", password: "demo" };

async function getAdminToken(request) {
  const r = await request.post("/api/admin/dev-login", { data: ADMIN_LOGIN });
  expect(r.ok()).toBeTruthy();
  const body = await r.json();
  return body.token;
}

test("REGRESSION #1060 — validate-plan: orphan beat returns error", async ({ page }) => {
  const token = await getAdminToken(page.request);
  const plan = {
    acts: [{ number: 1, title: "Akt 1", key_beats: [{ summary: "Orphan", optional: false }] }],
  };
  const r = await page.request.post("/api/admin/forge/validate-plan", {
    data: { gm_plan_json: plan },
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "endpoint must return 200").toBeTruthy();
  const body = await r.json();
  expect(body.ok, "plan with orphan beat must not be ok").toBe(false);
  expect(body.issues.length, "must have at least 1 issue").toBeGreaterThan(0);
  const err = body.issues.find((i) => i.type === "error" && i.code === "orphan_beat");
  expect(err, "must have orphan_beat error").toBeTruthy();
  expect(err.act_number, "error must include act_number").toBe(1);
});

test("REGRESSION #1060 — validate-plan: valid plan returns ok=true, no issues", async ({ page }) => {
  const token = await getAdminToken(page.request);
  const plan = {
    acts: [
      {
        number: 1,
        title: "Akt 1",
        key_beats: [
          { summary: "Zabij goblina", optional: false, objective_type: "kill_enemy", objective_value: "goblin" },
        ],
      },
    ],
  };
  const r = await page.request.post("/api/admin/forge/validate-plan", {
    data: { gm_plan_json: plan },
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok()).toBeTruthy();
  const body = await r.json();
  expect(body.ok, "valid plan must be ok").toBe(true);
  expect(body.issues, "valid plan must have no issues").toHaveLength(0);
});

test("REGRESSION #1060 — validate-plan: empty act returns empty_act error", async ({ page }) => {
  const token = await getAdminToken(page.request);
  const plan = { acts: [{ number: 1, title: "Akt 1", key_beats: [] }] };
  const r = await page.request.post("/api/admin/forge/validate-plan", {
    data: { gm_plan_json: plan },
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok()).toBeTruthy();
  const body = await r.json();
  const err = body.issues.find((i) => i.code === "empty_act");
  expect(err, "empty act must produce empty_act error").toBeTruthy();
});

test("REGRESSION #1060 — validate-plan: missing objective_value returns warning", async ({ page }) => {
  const token = await getAdminToken(page.request);
  const plan = {
    acts: [
      {
        number: 1,
        title: "Akt 1",
        key_beats: [{ summary: "Zabij kogokolwiek", optional: false, objective_type: "kill_enemy" }],
      },
    ],
  };
  const r = await page.request.post("/api/admin/forge/validate-plan", {
    data: { gm_plan_json: plan },
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok()).toBeTruthy();
  const body = await r.json();
  const warn = body.issues.find((i) => i.type === "warning" && i.code === "missing_objective_value");
  expect(warn, "missing objective_value must produce warning").toBeTruthy();
  expect(body.ok, "warnings alone must not set ok=false").toBe(true);
});
