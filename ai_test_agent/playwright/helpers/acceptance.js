/**
 * Acceptance-test helpers for the C1–C19 series (FAZA 1 core loop).
 *
 * Each acceptance test PLAYS the game with a real LLM, driving up to a turn
 * budget (default 30) toward a goal predicate. This mirrors how a human would
 * verify the feature, rather than asserting on internal stubs.
 */
const { expect } = require("@playwright/test");
const { sendTurnAndWaitForGm } = require("./player_flow");
const { getPlayerState } = require("./game_state");

const MAX_TURNS = 30;

/**
 * Drive turns until `goal` returns truthy or the turn budget is exhausted.
 *
 * @param {import('@playwright/test').Page} page
 * @param {object} opts
 * @param {string|string[]} opts.messages  single message or a list cycled per turn
 * @param {number} [opts.maxTurns=30]
 * @param {(ctx:{page:any,text:string,responses:string[],turn:number})=>Promise<boolean>|boolean} opts.goal
 * @param {number} [opts.turnTimeout=90000]
 * @returns {Promise<{achieved:boolean, turns:number, responses:string[]}>}
 */
async function playUntilGoal(page, { messages, maxTurns = MAX_TURNS, goal, turnTimeout = 90000 }) {
  const responses = [];
  for (let i = 0; i < maxTurns; i++) {
    const msg = Array.isArray(messages) ? messages[i % messages.length] : messages;
    const bubble = await sendTurnAndWaitForGm(page, msg, { timeout: turnTimeout });
    const text = ((await bubble.textContent()) || "").trim();
    responses.push(text);
    let done = false;
    try {
      done = await goal({ page, text, responses, turn: i + 1 });
    } catch (_) {
      done = false;
    }
    if (done) return { achieved: true, turns: i + 1, responses };
  }
  return { achieved: false, turns: maxTurns, responses };
}

/** True if any of `words` (case-insensitive) appears in `text`. */
function containsAny(text, words) {
  const low = (text || "").toLowerCase();
  return words.some((w) => low.includes(w.toLowerCase()));
}

/** Player-facing keywords that signal the GM is nudging the player to move/travel. */
const TRAVEL_HINT_WORDS = [
  "wyrusz",
  "ruszyć",
  "ruszaj",
  "udaj się",
  "udać się",
  "opuść",
  "opuścić",
  "podróż",
  "wędrów",
  "w stronę",
  "ścieżk",
  "drog",
  "dalej w",
  "czas ruszyć",
  "nie zwlekaj",
];

/** Currencies that must NOT appear once C13 (gold-only) is in force. */
const NON_GP_CURRENCY_WORDS = [
  "srebrn", // srebrne monety / sztuki srebra
  "miedzia",
  "miedzian",
  "silver",
  "copper",
  "elektrum",
];

/** Words signalling the LLM wrongly narrated equipment/gold loss (C17). */
const EQUIPMENT_LOSS_WORDS = [
  "straciłeś ekwipunek",
  "straciłeś cały",
  "bez broni",
  "pusta sakiewka",
  "pustą sakiewk",
  "nie masz nic",
  "obudziłeś się bez",
  "zgubiłeś ekwipunek",
  "okradziono cię",
];

async function playerState(characterId) {
  return getPlayerState(characterId);
}

module.exports = {
  MAX_TURNS,
  playUntilGoal,
  containsAny,
  playerState,
  TRAVEL_HINT_WORDS,
  NON_GP_CURRENCY_WORDS,
  EQUIPMENT_LOSS_WORDS,
};
