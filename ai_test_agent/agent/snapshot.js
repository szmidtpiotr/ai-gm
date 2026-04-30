const { DEFAULTS } = require("./models");

/**
 * Odczyt ostatnich wiadomości z wierszy campaign_turns (gm_decisions).
 */
function decisionsToMessages(decisionsData) {
  const raw = decisionsData?.decisions || [];
  const chronological = [...raw].reverse();
  const out = [];
  for (const d of chronological) {
    const det = d.details || {};
    const u = (det.user_text || "").trim();
    const a = (det.assistant_text || "").trim();
    if (u) out.push({ role: "player", text: u });
    if (a) out.push({ role: "gm", text: a, is_legal: d.is_legal });
  }
  return out.slice(-DEFAULTS.LAST_MESSAGES_N);
}

async function buildSnapshot(page, scenario, characterId, campaignId, step, backendUrl) {
  const stateRes = await fetch(`${backendUrl}/api/debug/player_state?character_id=${characterId}`);
  const playerState = stateRes.ok ? await stateRes.json() : {};

  const decisionsRes = await fetch(
    `${backendUrl}/api/debug/gm_decisions?session_id=${encodeURIComponent(String(campaignId))}&limit=12`
  );
  const decisionsData = decisionsRes.ok ? await decisionsRes.json() : { decisions: [] };
  const lastMessages = decisionsToMessages(decisionsData);

  const visibleActions = await page.evaluate(() => {
    const visible = [];
    const send = document.querySelector("#send-btn");
    if (send && !send.disabled) visible.push("send_chat_message");
    if (document.querySelector("#dice-btn")) visible.push("open_screen:character");
    if (document.querySelector("#archive-toggle-btn")) visible.push("click:#archive-toggle-btn");
    return visible;
  });

  return {
    step,
    player_state: {
      location: playerState.location,
      hp: playerState.hp,
      max_hp: playerState.max_hp,
      gold_gp: playerState.gold_gp,
      quests_active: playerState.quests_active,
      quests_completed: playerState.quests_completed,
    },
    last_messages: lastMessages,
    visible_actions: visibleActions,
    scenario_goal: scenario.goal,
  };
}

module.exports = { buildSnapshot, decisionsToMessages };
