const { ACTION_TYPES, ALLOWED_SCREENS, ALLOWED_CLICK_SELECTORS } = require("./models");

const FALLBACK = {
  type: "wait_for_gm_response",
  params: { timeout_ms: 3000 },
  reasoning: "validator_fallback",
  done: false,
};

function validate(raw, history = []) {
  if (raw == null || raw === undefined) {
    console.warn("[validator] null/undefined action — fallback");
    return FALLBACK;
  }

  let action;
  try {
    action = typeof raw === "string" ? JSON.parse(raw) : raw;
  } catch {
    console.warn("[validator] invalid JSON — fallback");
    return FALLBACK;
  }

  if (!action || typeof action !== "object") {
    return FALLBACK;
  }

  if (!ACTION_TYPES.includes(action.type)) {
    console.warn(`[validator] unknown type: ${action.type} — fallback`);
    return FALLBACK;
  }

  if (action.type === "send_chat_message") {
    const text = action.params?.text || "";
    if (!String(text).trim()) return FALLBACK;
    if (String(text).length > 500) {
      action.params = { ...action.params, text: String(text).slice(0, 500) };
    }
    const BANNED = ["<script", "SYSTEM:", "IGNORE PREVIOUS", "prompt injection"];
    if (BANNED.some((b) => String(text).toUpperCase().includes(b.toUpperCase()))) {
      console.warn("[validator] injection detected — fallback");
      return FALLBACK;
    }
  }

  if (action.type === "open_screen" && !ALLOWED_SCREENS.includes(action.params?.screen)) {
    return FALLBACK;
  }

  if (action.type === "click" && !ALLOWED_CLICK_SELECTORS.includes(action.params?.selector)) {
    console.warn(`[validator] selector not in whitelist: ${action.params?.selector}`);
    return FALLBACK;
  }

  if (history.length >= 3) {
    const last3 = history.slice(-3);
    const allSame = last3.every(
      (h) => h && h.type === action.type && JSON.stringify(h.params) === JSON.stringify(action.params)
    );
    if (allSame) {
      console.warn("[validator] loop detected — forcing finish");
      return {
        type: "finish",
        params: { success: false, reason: "loop_detected" },
        reasoning: "loop_detected",
        done: true,
      };
    }
  }

  return action;
}

module.exports = { validate, FALLBACK };
