const ACTION_TYPES = [
  "send_chat_message",
  "wait_for_gm_response",
  "open_screen",
  "click",
  "finish",
];

const ALLOWED_SCREENS = ["inventory", "character", "map"];

// Whitelist: #inventory-btn / #map-btn may be absent w UI — executor obsłuży łagodnie.
const ALLOWED_CLICK_SELECTORS = [
  "#send-btn",
  "#inventory-btn",
  "#character-btn",
  "#map-btn",
  "#dice-btn",
  "#archive-toggle-btn",
];

const DEFAULTS = {
  MAX_STEPS: 30,
  STEP_TIMEOUT_MS: 10_000,
  TOTAL_TIMEOUT_MS: 180_000,
  GM_WAIT_TIMEOUT_MS: 30_000,
  LOOP_DETECT_N: 3,
  LAST_MESSAGES_N: 6,
};

module.exports = { ACTION_TYPES, ALLOWED_SCREENS, ALLOWED_CLICK_SELECTORS, DEFAULTS };
