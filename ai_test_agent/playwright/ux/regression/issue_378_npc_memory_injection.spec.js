/**
 * REGRESSION #378 (D3) — NPC memory context injection.
 * Acceptance: campaign_known_npcs entries for a campaign are returned
 * via the known-npcs endpoint (which reads from the same table as the
 * LLM injector), confirming the data path is intact end-to-end.
 */
const { test, expect } = require("@playwright/test");

const ADMIN_TOKEN_HEADER = async (request) => {
  const r = await request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  const body = await r.json();
  return body.token;
};

test("REGRESSION #378 — known-npcs endpoint returns NPC memory entries for campaign with known NPCs", async ({
  page,
}) => {
  const token = await ADMIN_TOKEN_HEADER(page.request);

  // Campaign 999433 had Borun added during game-test-player run
  const r = await page.request.get("/api/admin/campaigns/999433/known-npcs", {
    headers: { Authorization: `Bearer ${token}` },
  });

  expect(r.ok(), "known-npcs endpoint must respond 200 (#378)").toBeTruthy();
  const body = await r.json();

  expect(
    typeof body.count,
    "response must have count field"
  ).toBe("number");
  expect(Array.isArray(body.npcs), "response must have npcs array").toBeTruthy();
});

test("REGRESSION #378 — known-npcs returns memory-source NPC when notes exist", async ({
  page,
}) => {
  const token = await ADMIN_TOKEN_HEADER(page.request);

  const r = await page.request.get("/api/admin/campaigns/999433/known-npcs", {
    headers: { Authorization: `Bearer ${token}` },
  });
  const body = await r.json();

  const memoryNpcs = (body.npcs || []).filter((n) => n.source === "memory");
  const borun = memoryNpcs.find((n) => n.label === "Borun");

  expect(
    borun !== undefined,
    `Expected 'Borun' memory NPC in campaign 999433 — got: ${JSON.stringify(memoryNpcs.map((n) => n.label))}`
  ).toBeTruthy();
  expect(
    borun.description,
    "Borun's description (notes) must be non-empty"
  ).toBeTruthy();
});
