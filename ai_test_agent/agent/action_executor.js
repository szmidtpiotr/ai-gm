const { DEFAULTS } = require("./models");

const SCREEN_TO_SELECTOR = {
  // UI: "Karta postaci" = #dice-btn; brak dedykowanych #inventory-btn / #map-btn
  inventory: "#inventory-btn",
  character: "#dice-btn",
  map: "#map-btn",
};

async function tryClick(page, selector, { optional = true } = {}) {
  if (!selector) return;
  try {
    const loc = page.locator(selector);
    if (optional && (await loc.count()) === 0) {
      console.warn(`[executor] brak elementu: ${selector}`);
      return;
    }
    await loc.first().click({ timeout: DEFAULTS.STEP_TIMEOUT_MS });
  } catch (e) {
    if (optional) console.warn(`[executor] click opcjonalny nieudany: ${selector}`, e.message);
    else throw e;
  }
}

async function execute(action, page) {
  if (!action || !action.type) return;

  switch (action.type) {
    case "send_chat_message": {
      const text = action.params?.text || "";
      await page.fill("textarea#input", text);
      const streamPromise = page.waitForResponse(
        (r) =>
          r.url().includes("/turns/stream") && r.request().method() === "POST" && r.status() < 500,
        { timeout: 90_000 }
      );
      await page.click("#send-btn");
      await streamPromise.catch(() => {});
      break;
    }
    case "wait_for_gm_response": {
      const timeout = action.params?.timeout_ms || DEFAULTS.GM_WAIT_TIMEOUT_MS;
      await page.waitForFunction(
        () => {
          const chat = document.getElementById("chat");
          if (!chat) return false;
          const asst = chat.querySelector(".message.assistant");
          const err = chat.querySelector(".message.error");
          return !!(asst || err);
        },
        null,
        { timeout }
      );
      break;
    }
    case "open_screen": {
      const screen = action.params?.screen;
      const sel = SCREEN_TO_SELECTOR[screen];
      await tryClick(page, sel, { optional: true });
      break;
    }
    case "click": {
      await tryClick(page, action.params?.selector, { optional: false });
      break;
    }
    case "finish":
      break;
    default:
      console.warn(`[executor] unhandled action type: ${action.type}`);
  }
}

module.exports = { execute, SCREEN_TO_SELECTOR, tryClick };
