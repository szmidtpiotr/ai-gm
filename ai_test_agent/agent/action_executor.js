const { DEFAULTS } = require("./models");
const { SELECTORS, OPEN_SCREEN_TO_SELECTOR, resolveGmWaitTimeoutMs } = require("./ui_actions");

/** @deprecated używaj OPEN_SCREEN_TO_SELECTOR — eksport pod kompatybilność importów */
const SCREEN_TO_SELECTOR = {
  inventory: OPEN_SCREEN_TO_SELECTOR.inventory,
  character: OPEN_SCREEN_TO_SELECTOR.character,
  map: OPEN_SCREEN_TO_SELECTOR.map,
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
    if (optional) {
      console.warn(`[executor] click opcjonalny nieudany: ${selector}`, e.message);
    } else {
      throw e;
    }
  }
}

async function execute(action, page) {
  if (!action || !action.type) return;

  const gmWait = resolveGmWaitTimeoutMs();

  switch (action.type) {
    case "send_chat_message": {
      const text = action.params?.text || "";
      await page.locator(SELECTORS.chatInput).first().fill(text);
      const streamPromise = page.waitForResponse(
        (r) =>
          r.url().includes("/turns/stream") && r.request().method() === "POST" && r.status() < 500,
        { timeout: 90_000 }
      );
      await page.locator(SELECTORS.sendBtn).first().click();
      await streamPromise.catch(() => {});
      break;
    }
    case "wait_for_gm_response": {
      const requested = action.params?.timeout_ms;
      const timeout =
        requested != null && Number(requested) > 0
          ? Math.max(Number(requested), gmWait)
          : gmWait;
      await page.waitForFunction(
        (rootSel) => {
          const root = document.querySelector(rootSel);
          if (!root) {
            return false;
          }
          const asst = root.querySelector(".message.assistant");
          const err = root.querySelector(".message.error");
          return !!(asst || err);
        },
        SELECTORS.chatRoot,
        { timeout }
      );
      break;
    }
    case "open_screen": {
      const screen = action.params?.screen;
      const sel = OPEN_SCREEN_TO_SELECTOR[screen];
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

module.exports = { execute, SCREEN_TO_SELECTOR, tryClick, SELECTORS, OPEN_SCREEN_TO_SELECTOR };
