/**
 * SMOKE #513 (U4) — Gotowa Kampania: weryfikacja end-to-end flow.
 * GM messages: .chat-bubble.chat-bubble--gm (in #chat-messages).
 * Opening turn __AI_GM_OPEN wysyłane automatycznie przy starcie nowej kampanii.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://192.168.1.61:3002";
const DEMO_USER = "demo";
const DEMO_PASS = "demo";
const LLM_TIMEOUT = 240_000;

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

// ─── TEST 1: API templates ─────────────────────────────────────────────────────

test("SMOKE #513 — API: /campaign-templates zwraca opublikowane szablony", async ({ page }) => {
  const r = await page.request.get(`${BASE}/api/campaign-templates`);
  expect(r.ok(), "P0: /api/campaign-templates musi odpowiadać 200").toBeTruthy();
  const body = await r.json();
  expect(Array.isArray(body.items), "body.items musi być tablicą").toBeTruthy();
  expect(body.items.length, "P0: brak opublikowanych szablonów").toBeGreaterThan(0);
  for (const t of body.items) {
    expect(t.status, `szablon ${t.id} nie jest published`).toBe("published");
    expect(t.id, "szablon bez id").toBeTruthy();
  }
});

// ─── TEST 2: API modes ─────────────────────────────────────────────────────────

test("SMOKE #513 — API: /campaign-modes zwraca gotowa.available=true", async ({ page }) => {
  const r = await page.request.get(`${BASE}/api/campaign-modes`);
  expect(r.ok()).toBeTruthy();
  const body = await r.json();
  const gotowa = (body.modes || []).find((m) => m.key === "gotowa");
  expect(gotowa, "brak trybu 'gotowa'").toBeTruthy();
  expect(gotowa.available, "P0: gotowa.available=false mimo że szablony istnieją").toBeTruthy();
  expect(gotowa.count, "P1: gotowa.count=0 mimo szablonów").toBeGreaterThan(0);
});

// ─── TEST 3: Przycisk Gotowa Kampania włącza się ──────────────────────────────

test("SMOKE #513 — UI: przycisk Gotowa Kampania aktywny gdy szablony dostępne", async ({ page }) => {
  test.setTimeout(90_000);
  await loginDemo(page);
  await gotoCampaigns(page);
  await page.waitForFunction(
    () => { const btn = document.getElementById("ready-campaign-btn"); return btn && !btn.disabled; },
    null,
    { timeout: 15_000 }
  );
  const btn = page.locator("#ready-campaign-btn");
  await expect(btn, "P0: #ready-campaign-btn disabled mimo szablonów").toBeEnabled({ timeout: 5_000 });
  const tag = btn.locator(".adv-card__tag");
  if (await tag.isVisible({ timeout: 2_000 }).catch(() => false)) {
    const tagText = await tag.textContent();
    expect(tagText, "P1: tag nadal 'Wkrótce' mimo dostępnych szablonów").not.toBe("Wkrótce");
  }
});

// ─── TEST 4: Picker szablonów ─────────────────────────────────────────────────

test("SMOKE #513 — UI: klik Gotowa Kampania → picker szablonów z listą", async ({ page }) => {
  test.setTimeout(90_000);
  await loginDemo(page);
  await gotoCampaigns(page);
  await page.waitForFunction(
    () => { const btn = document.getElementById("ready-campaign-btn"); return btn && !btn.disabled; },
    null,
    { timeout: 15_000 }
  );
  await page.click("#ready-campaign-btn");
  await expect(page.locator("#ready-campaign-picker"), "P0: picker nie pojawił się").toBeVisible({ timeout: 10_000 });
  const templateBtns = page.locator("#ready-campaign-picker [data-tpl]");
  await expect(templateBtns.first(), "P0: brak szablonów w pickerze").toBeVisible({ timeout: 5_000 });
  expect(await templateBtns.count(), "P0: picker pusty").toBeGreaterThan(0);
  await page.click("#rcp-close");
  await expect(page.locator("#ready-campaign-picker"), "P1: picker nie zamknął się").not.toBeVisible({ timeout: 5_000 });
});

// ─── TEST 5: E2E wybór szablonu + tura ────────────────────────────────────────

test("SMOKE #513 — E2E: wybierz szablon i zagraj pierwszą turę Gotowej Kampanii", async ({ page }) => {
  test.setTimeout(8 * 60_000);
  await loginDemo(page);
  await gotoCampaigns(page);
  await page.waitForFunction(
    () => { const btn = document.getElementById("ready-campaign-btn"); return btn && !btn.disabled; },
    null,
    { timeout: 15_000 }
  );
  await page.click("#ready-campaign-btn");
  await page.waitForSelector("#ready-campaign-picker", { timeout: 10_000 });
  await page.locator("#ready-campaign-picker [data-tpl]").first().click();
  await expect(page.locator("#ready-campaign-picker"), "P1: picker nie zamknął się po wyborze").not.toBeVisible({ timeout: 5_000 });

  // Kampania tworzona przez LLM — czekaj na game-screen
  await page.waitForSelector("#game-screen.screen--active", { timeout: LLM_TIMEOUT });

  // Czekaj na opening turn GM (≥1 .chat-bubble--gm w #chat-messages)
  await page.waitForFunction(
    () => document.querySelectorAll(".chat-bubble.chat-bubble--gm").length >= 1,
    null,
    { timeout: LLM_TIMEOUT }
  );

  // send button musi być enabled po opening turn
  const sendBtn = page.locator("#send-btn");
  await expect(sendBtn, "P0: przycisk Wyślij zablokowany po opening turn (Gotowa Kampania)").toBeEnabled({ timeout: LLM_TIMEOUT });

  // Wyślij pierwszą turę gracza
  const composer = page.locator("#chat-input");
  await composer.fill("Gdzie jestem? Opisz mi to miejsce.");
  await sendBtn.click();

  const diceOverlay = page.locator("#dice-overlay");
  if (await diceOverlay.isVisible({ timeout: 5_000 }).catch(() => false)) {
    await page.locator("#dice-roll-btn").click().catch(() => {});
    await diceOverlay.waitFor({ state: 'hidden', timeout: 30_000 }).catch(() => {});
  }

  await page.waitForFunction(
    () => document.querySelectorAll(".chat-bubble.chat-bubble--gm").length >= 2,
    null,
    { timeout: LLM_TIMEOUT }
  );

  const finalState = await page.evaluate(() => ({
    gameActive: document.getElementById('game-screen')?.classList.contains('screen--active'),
    gmMsgCount: document.querySelectorAll('.chat-bubble.chat-bubble--gm').length,
  }));
  expect(finalState.gameActive, 'P0: game-screen nieaktywny po turach').toBeTruthy();
  expect(finalState.gmMsgCount, 'P0: brak co najmniej 2 wiadomości GM (Gotowa Kampania)').toBeGreaterThanOrEqual(2);
});
