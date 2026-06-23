// In-game multiplayer UI specs — verified against frontend/front/js/multiplayer_ui.js + index.html.
//
// Blockers resolved (2026-06-23):
//   • P0-A (#959 commit f635420a): done→collecting auto-advance FIXED in multiplayer_round_service
//   • P0-B (#960): enterMpGame() now calls multiplayerUI.activate() after enterGame() so that
//     round polling, party chat panel and spectator mode are properly wired up.
//
// ⚠ test.fixme remains only on vote-kick (CP13/15) — requires:
//   a) vote-kick UI elements in index.html (.mp-kick-suggest / #mp-vote-kick) — not yet added
//   b) absence_warnings setup via external mp_sweep.py — cannot be triggered from within Playwright
const { test, expect } = require("@playwright/test");
const { ensureMpUsers, setupMpViaApi, loginAs, api } = require("./helpers/mp");

// Drive a logged-in page into a started MP game and wait for the game composer to appear.
async function enterGame(page, campaignId) {
  await page.evaluate((cid) => {
    if (typeof enterMpGame === "function") return enterMpGame(cid);
    throw new Error("enterMpGame is not defined — MP game entry not wired");
  }, campaignId);
  // #chat-input is the game composer input; #composer is its container.
  await page.waitForSelector("#chat-input, #composer", { timeout: 15000 });
}

// CP5 — round sync: both players submit, a single shared narration reaches BOTH contexts.
test("mp round sync: shared narration propagates to all players", async ({ browser }) => {
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
    // Wait for the collecting round to open (opening narration may still be generating).
    // #send-btn is disabled until the round is in 'collecting' state.
    for (const p of pages) {
      await p.waitForSelector("#send-btn:not([disabled])", { timeout: 90000 });
    }
    // Record narration count before submitting (opening narration already shown).
    const prevCount = await pages[0].locator("#chat-messages .message.message--gm").count();
    // Each player types + sends a game action.
    for (let i = 0; i < pages.length; i++) {
      await pages[i].fill("#chat-input", i === 0 ? "Ruszam naprzód." : "Osłaniam drużynę.");
      await pages[i].click("#send-btn");
    }
    // Both contexts must show a NEW completed-round narration (count increases on both pages).
    for (const p of pages) {
      await p.waitForFunction(
        (prev) => document.querySelectorAll("#chat-messages .message.message--gm").length > prev,
        prevCount,
        { timeout: 90000 }
      );
      const txt = await p.locator("#chat-messages .message.message--gm").last().innerText();
      expect(txt.length, "narration too short — may be an error placeholder").toBeGreaterThan(40);
    }
  } finally {
    for (const c of ctxs) await c.close();
  }
});

// CP3/CP7 — spectator lock: a spectator sees the game screen but composer shows spectator hint.
test("mp spectator: action input shows spectator mode hint", async ({ browser }) => {
  const users = await ensureMpUsers(2, /* spectator */ true);
  const { campaignId } = await setupMpViaApi(users, { title: "#MP-pw-spec" });
  const spec = users.find((u) => u.role === "spectator");
  const ctx = await browser.newContext();
  try {
    const page = await ctx.newPage();
    await loginAs(page, spec.username);
    await enterGame(page, campaignId);
    // GF6: spectator gets a read-only composer with a "Widz" placeholder.
    // The input itself is not DOM-disabled (send is re-enabled for /whisper to party chat)
    // but the placeholder text signals the spectator restriction to the player.
    const composer = page.locator("#chat-input");
    await expect(composer).toHaveAttribute("placeholder", /Widz/);
  } finally {
    await ctx.close();
  }
});

// CP11 — party chat: public messages visible to all members.
// Whisper privacy via /whisper <characterName> text is tested at API level (see pytest)
// because frontend regex (\S+) requires space-free character names; UI whisper deferred.
test("mp party chat: public messages visible to all members", async ({ browser }) => {
  const users = await ensureMpUsers(3);
  const { campaignId } = await setupMpViaApi(users, { title: "#MP-pw-chat" });
  const ctxs = await Promise.all(users.map(() => browser.newContext()));
  try {
    const pages = [];
    for (let i = 0; i < users.length; i++) {
      const p = await ctxs[i].newPage();
      await loginAs(p, users[i].username);
      await enterGame(p, campaignId);
      // Toggle open the party chat body (hidden by default; shown by #party-chat-panel toggle).
      await p.click(".mp-chat-panel__toggle");
      await p.waitForSelector("#mp-chat-body", { state: "visible", timeout: 5000 });
      pages.push(p);
    }
    // P1 posts a public message → all three see it in #mp-chat-messages.
    await pages[0].fill("#mp-chat-input", "Cześć drużyno!");
    await pages[0].click(".mp-chat-send-btn");
    for (const p of pages) {
      await expect(p.locator("#mp-chat-messages")).toContainText("Cześć drużyno!", { timeout: 8000 });
    }
  } finally {
    for (const c of ctxs) await c.close();
  }
});

// CP13/15 — in-game absence-triggered vote-kick SUGGESTION (distinct from lobby host-kick).
// Lobby host-kick (the path that actually ships) is covered runnable in mp_lobby_kick.spec.js.
// ⚠ GATED: the in-game suggestion UI (.mp-kick-suggest / #mp-vote-kick) isn't built yet, AND
// driving absence_warnings>=3 needs external mp_sweep.py (not runnable from this container).
// Remove fixme once both exist.
test.fixme("mp vote-kick: in-game kick suggestion appears after absence threshold", async ({ browser }) => {
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
