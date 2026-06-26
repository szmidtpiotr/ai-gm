/**
 * REGRESSION #999 — quest-bar reads character_quests (status='active'), not world_state.
 * Acceptance: GET /api/campaigns/{id}/quests returns ONLY active quests, each shaped
 * {title, objective, reward} for the HUD; the known completed quest from the 99791
 * repro ("Nocna przesyłka") must NOT appear on the bar.
 */
const { test, expect } = require("@playwright/test");

const REPRO_CAMPAIGN = 99791; // Mizel — issue #999 repro campaign

test("REGRESSION #999 — quest bar exposes active-quest contract", async ({ page }) => {
  const r = await page.request.get(`/api/campaigns/${REPRO_CAMPAIGN}/quests`);
  expect(r.ok(), "GET /quests must return 200 (#999)").toBeTruthy();

  const body = await r.json();
  expect(Array.isArray(body.active_quests), "active_quests must be a list").toBeTruthy();

  for (const q of body.active_quests) {
    // HUD renderQuestBar reads title / objective / reward
    expect(q, "each quest carries title").toHaveProperty("title");
    expect(q, "each quest carries objective (mapped from narrative)").toHaveProperty("objective");
    expect(q, "each quest carries reward key").toHaveProperty("reward");
  }

  const titles = body.active_quests.map((q) => q.title);
  expect(
    titles.includes("Nocna przesyłka"),
    "completed quest 'Nocna przesyłka' must be pruned from the bar (#999 root cause)"
  ).toBeFalsy();
});
