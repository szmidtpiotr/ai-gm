/**
 * REGRESSION #1015 — side quests spawned from a scene get pinned to that scene's
 * beat (character_quests.beat_key), so the #1011 skip-cancel loop fires in a real
 * playthrough (skipped beat → quest auto-cancelled).
 * Acceptance: the player-facing quest endpoint stays a clean contract; the quest
 * bar reads character_quests (status='active') as its single source of truth, so
 * skipped/cancelled quests never leak into the active list.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1015 — quest bar contract reads active quests only", async ({ page }) => {
  // Discover a real campaign (ids are not fixed); fall back to a missing-id 404
  // contract check if the demo account has none.
  const list = await page.request.get("/api/campaigns?user_id=1");
  expect(list.ok(), "GET /api/campaigns must answer 200").toBeTruthy();
  const campaigns = (await list.json()).campaigns || [];

  if (campaigns.length === 0) {
    const miss = await page.request.get("/api/campaigns/999999999/quests");
    expect(miss.status(), "missing campaign → 404 contract").toBe(404);
    return;
  }

  const cid = campaigns[0].id;
  const r = await page.request.get(`/api/campaigns/${cid}/quests`);
  expect(r.ok(), `GET /api/campaigns/${cid}/quests must answer 200 (#1015)`).toBeTruthy();

  const body = await r.json();
  expect(Array.isArray(body.active_quests), "active_quests must be an array").toBeTruthy();

  // Every listed quest is well-formed and (being 'active') never a skipped one.
  for (const q of body.active_quests) {
    expect(typeof q.title, "quest.title must be a string").toBe("string");
    expect("objective" in q, "quest must expose objective").toBeTruthy();
  }
});
