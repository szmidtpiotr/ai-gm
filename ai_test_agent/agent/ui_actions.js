/**
 * Centralne selektory UI gry (Playwright) — preferuj data-testid, potem legacy #id.
 * @see docs/Phase_9A_AI_Test_Agent/9A-6_scenarios_catalog.md
 */

const { DEFAULTS } = require("./models");

/** Domyślny timeout oczekiwania na odpowiedź GM (ms): env, potem stub 8s, potem models. */
function resolveGmWaitTimeoutMs() {
  const raw = process.env.WAIT_GM_TIMEOUT_MS;
  if (raw !== undefined && String(raw).trim() !== "") {
    const n = parseInt(String(raw), 10);
    if (!Number.isNaN(n) && n > 0) {
      return n;
    }
  }
  if (process.env.AI_TEST_STUB_LLM === "1") {
    return 8000;
  }
  return DEFAULTS.GM_WAIT_TIMEOUT_MS;
}

const SELECTORS = {
  chatRoot: "#chat",
  /** Kontener wiadomości (alias dla #chat zgodnie z planem testów) */
  chatMessages: '[data-testid="chat-messages"], #chat',
  chatInput: '[data-testid="chat-input"], textarea#input',
  sendBtn: '[data-testid="chat-send"], #send-btn',
  /** Ostatnia wiadomość GM — dynamicznie; w DOM: .message.assistant + data-testid z ui.js */
  gmMessage: '[data-testid="gm-message"]',
  campaignSelect: "#campaign-select",
  inventoryBtn: '[data-testid="open-inventory"], #inventory-btn',
  characterBtn: '[data-testid="open-character"], #dice-btn',
  mapBtn: '[data-testid="open-map"], #map-btn',
  playerLocation: '[data-testid="player-location"]',
};

/** Mapa open_screen → selektor (zgodnie z action_executor / UI) */
const OPEN_SCREEN_TO_SELECTOR = {
  inventory: SELECTORS.inventoryBtn,
  character: SELECTORS.characterBtn,
  map: SELECTORS.mapBtn,
};

class GameUI {
  /**
   * @param {import('playwright').Page} page
   * @param {string} text
   */
  async sendMessage(page, text) {
    await page.locator(SELECTORS.chatInput).first().fill(text);
    const streamPromise = page.waitForResponse(
      (r) =>
        r.url().includes("/turns/stream") && r.request().method() === "POST" && r.status() < 500,
      { timeout: 90_000 }
    );
    await page.locator(SELECTORS.sendBtn).first().click();
    await streamPromise.catch(() => {});
  }

  /**
   * @param {import('playwright').Page} page
   * @returns {Promise<string|null>}
   */
  async getLastGmMessage(page) {
    const loc = page.locator(`${SELECTORS.chatRoot} .message.assistant`);
    const n = await loc.count();
    if (n === 0) {
      return null;
    }
    return loc.nth(n - 1).innerText();
  }

  /**
   * @param {import('playwright').Page} page
   * @returns {Promise<string|null>}
   */
  async getPlayerLocation(page) {
    const el = page.locator(SELECTORS.playerLocation).first();
    if ((await el.count()) === 0) {
      return null;
    }
    return el.innerText();
  }

  /**
   * @param {import('playwright').Page} page
   * @returns {Promise<string>}
   */
  async getVisibleText(page) {
    return page.evaluate(() => document.body.innerText);
  }
}

module.exports = {
  GameUI,
  SELECTORS,
  OPEN_SCREEN_TO_SELECTOR,
  resolveGmWaitTimeoutMs,
};
