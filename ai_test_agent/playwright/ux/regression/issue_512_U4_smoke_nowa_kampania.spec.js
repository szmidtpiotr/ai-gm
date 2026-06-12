/**
 * SMOKE #512 (U4) — Nowa Kampania: weryfikacja end-to-end flow.
 *
 * Design: z wybranym bohaterem klik "Nowa Kampania" → handleNewCampaignWithHero()
 * → kampania tworzona natychmiast → enterGame() → showScreen('game') + opening turn
 * (__AI_GM_OPEN). Dopiero po opening turn btn-send jest re-enabled.
 * GM messages: .chat-bubble.chat-bubble--gm (in #chat-messages).
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://192.168.1.61:3002";
const DEMO_USER = "demo";
const DEMO_PASS = "demo";
const LLM_TIMEOUT = 240_000; // 4 min na LLM (opening + tura)

async function loginDemo(page) {
  await page.goto(BASE);
  await page.waitForSelector("#login-screen.screen--active", { timeout: 15_000 });
  await page.fill("#login-username", DEMO_USER);
  await page.fill("#login-password", DEMO_PASS);
  await page.locator("#login-form button[type='submit']").click();
  await page.waitForFunction(
    () => {
      const ids = ["onboarding-screen", "heroes-screen", "campaigns-screen", "game-screen"];
      return ids.some((id) => document.getElementById(id)?.classList.contains("screen--active"));
    },
    null,
    { timeout: 30_000 }
  );
  // Onboarding CTA pojawia się po 5s animacji CSS
  const cta = page.locator("#onboarding-cta");
  if (await cta.isVisible({ timeout: 8_000 }).catch(() => false)) {
    await cta.click();
  }
  await page.waitForFunction(
    () => {
      const ids = ["heroes-screen", "campaigns-screen", "game-screen"];
      return ids.some((id) => document.getElementById(id)?.classList.contains("screen--active"));
    },
    null,
    { timeout: 20_000 }
  );
}

async function gotoCampaigns(page) {
  const onCampaigns = await page.evaluate(
    () => document.getElementById("campaigns-screen")?.classList.contains("screen--active")
  );
  if (onCampaigns) return;
  const firstHero = page.locator(".hero-card").first();
  if (await firstHero.isVisible({ timeout: 5_000 }).catch(() => false)) {
    await firstHero.click();
  }
  await page.waitForSelector("#campaigns-screen.screen--active", { timeout: 15_000 });
}

// ─── TEST 1: API ───────────────────────────────────────────────────────────────

test("SMOKE #512 — API: /campaign-modes zwraca nowa.available=true", async ({ page }) => {
  const r = await page.request.get(`${BASE}/api/campaign-modes`);
  expect(r.ok(), "/api/campaign-modes musi odpowiadać 200").toBeTruthy();
  const body = await r.json();
  const nowa = (body.modes || []).find((m) => m.key === "nowa");
  expect(nowa, "brak trybu 'nowa'").toBeTruthy();
  expect(nowa.available, "tryb 'nowa' musi być available=true").toBeTruthy();
});

// ─── TEST 2: Przycisk Nowa Kampania ───────────────────────────────────────────

test("SMOKE #512 — UI: przycisk Nowa Kampania aktywny na campaigns-screen", async ({ page }) => {
  test.setTimeout(90_000);
  await loginDemo(page);
  await gotoCampaigns(page);
  const btn = page.locator("#new-campaign-btn");
  await expect(btn).toBeVisible({ timeout: 10_000 });
  await expect(btn, "#new-campaign-btn nie może być disabled").toBeEnabled({ timeout: 5_000 });
});

// ─── TEST 3: Klik → game-screen (kampania tworzy się od razu) ─────────────────

test("SMOKE #512 — UI: klik Nowa Kampania z wybranym bohaterem → game-screen lub loading", async ({ page }) => {
  test.setTimeout(5 * 60_000);
  await loginDemo(page);
  await gotoCampaigns(page);
  await page.click("#new-campaign-btn");
  await page.waitForFunction(
    () => {
      const ids = ["game-screen", "new-campaign-screen"];
      return ids.some((id) => document.getElementById(id)?.classList.contains("screen--active"));
    },
    null,
    { timeout: LLM_TIMEOUT }
  );
  const onGame = await page.evaluate(
    () => document.getElementById("game-screen")?.classList.contains("screen--active")
  );
  const onNewCampaign = await page.evaluate(
    () => document.getElementById("new-campaign-screen")?.classList.contains("screen--active")
  );
  expect(onGame || onNewCampaign, "P0: po kliknięciu Nowa Kampania nie trafiliśmy ani na game-screen ani na new-campaign-screen").toBeTruthy();
});

// ─── TEST 4: E2E pełna tura ────────────────────────────────────────────────────

test("SMOKE #512 — E2E: Nowa Kampania → game-screen → pierwsza tura GM", async ({ page }) => {
  test.setTimeout(8 * 60_000);
  await loginDemo(page);
  await gotoCampaigns(page);
  await page.click("#new-campaign-btn");

  // Jeśli pojawi się formularz nazwy — wpisz i wyślij
  const onNewCampaignScreen = await page.waitForSelector(
    "#new-campaign-screen.screen--active",
    { timeout: 3_000 }
  ).catch(() => null);
  if (onNewCampaignScreen) {
    const nameInput = page.locator("#new-campaign-screen input[type='text']").first();
    if (await nameInput.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await nameInput.fill("Smoke Test Nowa Kampania");
    }
    const submitBtn = page.locator("#new-campaign-screen button[type='submit'], #new-campaign-screen .btn--primary").first();
    await submitBtn.click();
  }

  // Czekaj na game-screen
  await page.waitForSelector("#game-screen.screen--active", { timeout: LLM_TIMEOUT });

  // Poczekaj aż opening turn (__AI_GM_OPEN) się skończy → pojawi się ≥1 GM message
  // i btn-send będzie re-enabled.
  await page.waitForFunction(
    () => document.querySelectorAll(".chat-bubble.chat-bubble--gm").length >= 1,
    null,
    { timeout: LLM_TIMEOUT }
  );

  const sendBtn = page.locator("#send-btn");
  // Czekaj aż send btn jest enabled (opening turn skończony)
  await expect(sendBtn, "P0: przycisk Wyślij zablokowany po opening turn").toBeEnabled({ timeout: LLM_TIMEOUT });

  // Wyślij pierwszą turę gracza
  const composer = page.locator("#chat-input");
  await composer.fill("Gdzie jestem? Opisz mi to miejsce.");
  await sendBtn.click();

  // Jeśli pojawi się dice popup (skill_test_pending) — kliknij roll i poczekaj na wynik
  const diceOverlay = page.locator("#dice-overlay");
  if (await diceOverlay.isVisible({ timeout: 5_000 }).catch(() => false)) {
    await page.locator("#dice-roll-btn").click().catch(() => {});
    await diceOverlay.waitFor({ state: 'hidden', timeout: 30_000 }).catch(() => {});
  }

  // Czekaj na drugą odpowiedź GM (po naszej turze lub po dice)
  await page.waitForFunction(
    () => document.querySelectorAll(".chat-bubble.chat-bubble--gm").length >= 2,
    null,
    { timeout: LLM_TIMEOUT }
  );

  await expect(page.locator("#game-screen.screen--active"), "P0: game-screen zniknął po turze").toBeVisible();
  // send-btn może być disabled jeśli kolejny dice popup odpalił - to normalne UX
  // Smoke: weryfikujemy że gra żyje, nie że jesteśmy w idle
  const finalState = await page.evaluate(() => ({
    gameActive: document.getElementById('game-screen')?.classList.contains('screen--active'),
    gmMsgCount: document.querySelectorAll('.chat-bubble.chat-bubble--gm').length,
  }));
  expect(finalState.gameActive, 'P0: game-screen nieaktywny po turach').toBeTruthy();
  expect(finalState.gmMsgCount, 'P0: brak co najmniej 2 wiadomości GM').toBeGreaterThanOrEqual(2);
});
