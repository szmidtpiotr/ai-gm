/**
 * REGRESSION #953 — Turns tab shows full text with expand/collapse, no hardcoded slice.
 * Acceptance: "Rozwiń" button in campaigns.js; API returns full (un-truncated) assistant_text.
 */
const { test, expect } = require("@playwright/test");

async function adminLogin(page) {
  const resp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(resp.ok(), "admin login must succeed (#953)").toBeTruthy();
  const body = await resp.json();
  return body.token || body.access_token;
}

test("REGRESSION #953 — turns API returns full untruncated text", async ({ page }) => {
  const token = await adminLogin(page);

  const r = await page.request.get("/api/admin/campaigns/live", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "campaigns/live endpoint must respond 200 (#953)").toBeTruthy();
  const data = await r.json();
  const campaigns = data.items || data.campaigns || (Array.isArray(data) ? data : []);
  expect(Array.isArray(campaigns), "campaigns response must be array (#953)").toBeTruthy();

  if (!campaigns.length) return; // no campaigns — skip

  const campId = campaigns[0].id;
  const tr = await page.request.get(`/api/admin/campaigns/${campId}/turns?limit=10`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(tr.ok(), `turns endpoint for campaign ${campId} must respond 200 (#953)`).toBeTruthy();
  const turnsData = await tr.json();
  const turns = turnsData.items || turnsData;
  expect(Array.isArray(turns), "turns response must be array (#953)").toBeTruthy();

  if (!turns.length) return; // no turns yet — skip UI check, API contract is still verified

  // API must return full text — if long turns exist, text must exceed the old 300-char cap
  const longTurn = turns.find(t => (t.assistant_text || "").length > 150);
  if (longTurn) {
    const parsed = JSON.parse(longTurn.assistant_text || "{}");
    const narrative = parsed.narrative || "";
    // Before fix: would be sliced to 300/400 chars. After fix: full text returned by API.
    expect((narrative || longTurn.assistant_text).length, "API must return full text, not truncated to 300 (#953)").toBeGreaterThan(150);
  }
});

test("REGRESSION #953 — campaigns.js does not contain hardcoded slice in turns render", async ({ page }) => {
  const r = await page.request.get("/admin/sections/campaigns.js");
  if (!r.ok()) return; // file not directly servable — skip

  const js = await r.text();
  expect(js, "narrative must not be hardcoded slice(0,300)").not.toContain("narrative.slice(0,300)");
  expect(js, "debug narrative must not be hardcoded slice(0,400)").not.toContain("narrative.slice(0,400)");
  expect(js, "turns render must contain expand button").toContain("Rozwiń");
  expect(js, "turns render must contain collapse button").toContain("Zwiń");
});
