/**
 * REGRESSION #924 (GF4) — openMultiplayerLobby() router z huba do create-lobby-screen.
 * Acceptance: klik kafelka "Multiplayer" w hubie trybów → otwiera create-lobby-screen,
 * zamyka overlay campaign-modes-hub, brak fallback-toastu.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

test("REGRESSION #924 — openMultiplayerLobby jest globalną funkcją", async ({ page }) => {
  await page.goto(BASE + "/");

  const isDefined = await page.evaluate(() => typeof window.openMultiplayerLobby === 'function');
  expect(isDefined, "openMultiplayerLobby nie jest globalną funkcją").toBe(true);
});

test("REGRESSION #924 — openMultiplayerLobby pokazuje create-lobby-screen", async ({ page }) => {
  await page.goto(BASE + "/");

  // Inject mock showScreen so we can track calls without full auth
  await page.evaluate(() => {
    window._screenShown = null;
    window.showScreen = (name) => {
      window._screenShown = name;
      // Also toggle screen visibility for DOM check
      document.querySelectorAll('.screen').forEach(s => s.classList.remove('screen--active'));
      const el = document.getElementById(name);
      if (el) el.classList.add('screen--active');
    };
  });

  // Call openMultiplayerLobby — should navigate to create-lobby-screen
  await page.evaluate(() => window.openMultiplayerLobby());

  const screenShown = await page.evaluate(() => window._screenShown);
  expect(screenShown, "openMultiplayerLobby nie wywołał showScreen('create-lobby') — fix #935 zmienił klucz z 'create-lobby-screen' na 'create-lobby'")
    .toBe('create-lobby');
});

test("REGRESSION #924 — openMultiplayerLobby usuwa overlay campaign-modes-hub", async ({ page }) => {
  await page.goto(BASE + "/");

  // Create fake hub overlay
  await page.evaluate(() => {
    const overlay = document.createElement('div');
    overlay.id = 'campaign-modes-hub';
    document.body.appendChild(overlay);
  });

  const beforeCall = await page.evaluate(() => !!document.getElementById('campaign-modes-hub'));
  expect(beforeCall, "overlay nie istnieje przed testem").toBe(true);

  await page.evaluate(() => {
    window.showScreen = () => {}; // mock
    window.openMultiplayerLobby();
  });

  const afterCall = await page.evaluate(() => !!document.getElementById('campaign-modes-hub'));
  expect(afterCall, "overlay campaign-modes-hub powinien być usunięty po openMultiplayerLobby()").toBe(false);
});

test("REGRESSION #924 — hub multiplayer route nie pokazuje fallback-toastu", async ({ page }) => {
  await page.goto(BASE + "/");

  // Track if showToast was called with fallback message
  const toastFired = await page.evaluate(() => {
    let toastMsg = null;
    const origToast = window.showToast;
    window.showToast = (msg, ...rest) => { toastMsg = msg; if (origToast) origToast(msg, ...rest); };
    window.showScreen = () => {};
    window.openMultiplayerLobby();
    return toastMsg;
  });

  expect(
    toastFired,
    `Fallback toast pojawił się: "${toastFired}" — openMultiplayerLobby() nie jest zdefiniowane?`
  ).toBeNull();
});
