// Lobby host-kick — RUNNABLE. Covers the manual host-kick path that actually ships in the UI
// (G3 #787 / G13 #799): host opens the lobby, clicks ✕ on a member, that member is removed and
// their hero is freed back to idle. This is distinct from the in-game absence-triggered vote-kick
// suggestion (see the gated fixme in mp_ingame.spec.js) — that variant's UI isn't built yet.
const { test, expect } = require("@playwright/test");
const { ensureMpUsers, setupMpLobbyViaApi, loginAs, api } = require("./helpers/mp");

// Drive a logged-in host page into the lobby screen for the given campaign.
async function openLobby(page, campaignId) {
  await page.evaluate((cid) => {
    if (typeof _showLobbyScreen === "function") return _showLobbyScreen(cid);
    throw new Error("_showLobbyScreen is not defined — MP lobby UI not loaded");
  }, campaignId);
  await page.waitForSelector("#lobby-members-list", { state: "visible", timeout: 15000 });
}

test("mp lobby kick: host removes a member and frees their hero", async ({ browser }) => {
  const users = await ensureMpUsers(2);
  const { campaignId } = await setupMpLobbyViaApi(users, { title: "#MP-pw-kick-lobby" });
  const host = users[0];
  const victim = users[1];

  const ctx = await browser.newContext();
  try {
    const page = await ctx.newPage();
    await loginAs(page, host.username);
    await openLobby(page, campaignId);

    // The victim's slot carries a ✕ kick button (host-only, non-owner members).
    const kickBtn = page.locator(".lf-party-slot__kick");
    await expect(kickBtn.first()).toBeVisible({ timeout: 10000 });
    await kickBtn.first().click();

    // Backend truth: the victim's membership flips to 'kicked' and the hero is freed to idle.
    await expect.poll(async () => {
      const { body } = await api("GET", `/api/multiplayer/campaigns/${campaignId}/lobby`, { userId: host.userId });
      const m = (body.members || []).find((x) => x.user_id === victim.userId);
      // kicked members are either dropped from the list or marked status='kicked'
      return !m || m.status === "kicked";
    }, { timeout: 10000 }).toBe(true);

    // Hero freed: the victim's character is no longer bound to this campaign.
    const { body: heroes } = await api("GET", `/api/characters?user_id=${victim.userId}`);
    const hero = (Array.isArray(heroes) ? heroes : heroes.items || []).find((c) => c.id === victim.heroId);
    if (hero) expect(hero.campaign_id == null || hero.status === "idle").toBeTruthy();
  } finally {
    await ctx.close();
  }
});
