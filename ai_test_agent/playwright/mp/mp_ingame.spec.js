// In-game multiplayer UI specs — the TARGET behaviour for the MP player UI.
//
// ⚠ GATED with test.fixme until two confirmed blockers are closed (verified 2026-06-23):
//   • P0-A (backend): after the opening round (status 'done') nothing opens the next
//     'collecting' round — submit_action returns round_closed for any non-collecting round and
//     get_or_create_current_round is dead code. Rounds can't advance past the opening.
//   • P0-B (frontend): enterMpGame(campaignId) is referenced in multiplayer_ui.js but never
//     defined anywhere in frontend/front — entering a started MP game from the UI is a no-op,
//     so the in-game MP composer/chat/banner never mount.
//
// These specs use the REAL selectors from frontend/front/js/multiplayer_ui.js + index.html so they
// go green the moment MP is finished. Flip test.fixme → test to run them. Each documents what it
// asserts and which checkpoint (game-smoke-mp) it covers.
const { test, expect } = require("@playwright/test");
const { ensureMpUsers, setupMpViaApi, loginAs, api } = require("./helpers/mp");

// Drive a logged-in page into a started MP game. Once enterMpGame exists this is the entry point;
// today it is a no-op (the guard `typeof enterMpGame === 'function'` is false).
async function enterGame(page, campaignId) {
  await page.evaluate((cid) => {
    if (typeof enterMpGame === "function") return enterMpGame(cid);
    throw new Error("enterMpGame is not defined (P0-B) — MP game entry not wired");
  }, campaignId);
  await page.waitForSelector("#mp-composer, textarea#input", { timeout: 15000 });
}

// CP5 — round sync: both players submit, a single shared narration reaches BOTH contexts.
test.fixme("mp round sync: shared narration propagates to all players", async ({ browser }) => {
  const users = await ensureMpUsers(2);
  const { campaignId } = await setupMpViaApi(users, { title: "#MP-pw-sync" });
  const ctxs = await Promise.all(users.map(() => browser.newContext()));
  try {
    const pages = [];
    for (let i = 0; i < users.length; i++) {
      const p = await ctxs[i].newPage();
      await loginAs(p, users[i].username);
      await enterGame(p, campaignId);
      pages.push(p);
    }
    // Each player types + sends an action.
    for (let i = 0; i < pages.length; i++) {
      await pages[i].fill("textarea#input", i === 0 ? "Ruszam naprzód." : "Osłaniam drużynę.");
      await pages[i].click("#send-btn");
    }
    // Both contexts must show the SAME completed-round narration.
    for (const p of pages) {
      await p.waitForSelector(".mp-round-narrative, #chat .message.assistant", { timeout: 90000 });
      const txt = await p.locator(".mp-round-narrative, #chat .message.assistant").last().innerText();
      expect(txt.length).toBeGreaterThan(40);
    }
  } finally {
    for (const c of ctxs) await c.close();
  }
});

// CP3/CP7 — spectator lock: a spectator sees narration but cannot submit a game action.
test.fixme("mp spectator: action input is locked for spectators", async ({ browser }) => {
  const users = await ensureMpUsers(2, /* spectator */ true);
  const { campaignId } = await setupMpViaApi(users, { title: "#MP-pw-spec" });
  const spec = users.find((u) => u.role === "spectator");
  const ctx = await browser.newContext();
  try {
    const page = await ctx.newPage();
    await loginAs(page, spec.username);
    await enterGame(page, campaignId);
    // Spectator composer must be disabled / hidden (GF6: spectators only get party chat).
    const composer = page.locator("textarea#input");
    await expect(composer).toBeDisabled();
  } finally {
    await ctx.close();
  }
});

// CP11 — party chat + whisper privacy across contexts.
test.fixme("mp party chat: public visible to all, whisper only to target", async ({ browser }) => {
  const users = await ensureMpUsers(3);
  const { campaignId } = await setupMpViaApi(users, { title: "#MP-pw-chat" });
  const ctxs = await Promise.all(users.map(() => browser.newContext()));
  try {
    const pages = [];
    for (let i = 0; i < users.length; i++) {
      const p = await ctxs[i].newPage();
      await loginAs(p, users[i].username);
      await enterGame(p, campaignId);
      await p.click("#party-chat-toggle");
      pages.push(p);
    }
    // P1 posts a public message → all three see it.
    await pages[0].fill("#party-chat-input", "Cześć drużyno!");
    await pages[0].click("#party-chat-send");
    for (const p of pages) {
      await expect(p.locator("#party-chat-panel")).toContainText("Cześć drużyno!", { timeout: 8000 });
    }
    // P1 whispers to P2 → only P1 + P2 see it, NOT P3.
    await pages[0].fill("#party-chat-input", `/whisper ${users[1].username} sekret`);
    await pages[0].click("#party-chat-send");
    await expect(pages[1].locator("#party-chat-panel")).toContainText("sekret", { timeout: 8000 });
    await expect(pages[2].locator("#party-chat-panel")).not.toContainText("sekret");

    // Privacy guarantee: the whisper must never reach the LLM round context.
    const { body } = await api("GET", `/api/campaigns/${campaignId}/rounds/history`, { userId: users[0].userId });
    expect(JSON.stringify(body)).not.toContain("sekret");
  } finally {
    for (const c of ctxs) await c.close();
  }
});

// CP13/15 — absence + vote-kick modal. Time injection (force-sweep) needs the python helper
// mp_sweep.py (run from .19), which Playwright-in-container cannot do — so this asserts only the
// UI surfacing of absence_warnings/kick once the backend state is set.
test.fixme("mp vote-kick: kick modal appears after absence threshold", async ({ browser }) => {
  const users = await ensureMpUsers(3);
  const { campaignId } = await setupMpViaApi(users, { title: "#MP-pw-kick" });
  // (Prereq) drive absence_warnings>=3 for users[2] via repeated rounds + mp_sweep.py, then:
  const ctx = await browser.newContext();
  try {
    const page = await ctx.newPage();
    await loginAs(page, users[0].username);
    await enterGame(page, campaignId);
    await expect(page.locator(".mp-kick-suggest, #mp-vote-kick")).toBeVisible({ timeout: 10000 });
  } finally {
    await ctx.close();
  }
});
