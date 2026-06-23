/**
 * REGRESSION #932 — POST /multiplayer/campaigns zwraca 200 (brak model_id w INSERT naprawiony).
 * Acceptance: endpoint tworzy lobby bez 500, kampania ma model_id='default'.
 */
const { test, expect } = require("@playwright/test");

const HOST_USER_ID = 1;

test("REGRESSION #932 — create_lobby returns 200 + campaign_id", async ({ page }) => {
  const resp = await page.request.post(
    `/api/multiplayer/campaigns?user_id=${HOST_USER_ID}`,
    {
      data: { title: "PW932 Lobby", max_players: 2, round_timer_minutes: 60 },
    }
  );
  expect(resp.status(), "create_lobby nie zwraca 200 (#932)").toBe(200);
  const body = await resp.json();
  expect(body.campaign_id, "campaign_id missing in response").toBeTruthy();
  expect(body.lobby_status).toBe("open");

  // cleanup
  const campaignId = body.campaign_id;
  if (campaignId) {
    await page.request.delete(`/api/admin/campaigns/${campaignId}?user_id=${HOST_USER_ID}`).catch(() => {});
  }
});
