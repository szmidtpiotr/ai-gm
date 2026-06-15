/**
 * REGRESSION #635 (SF6) — karta rzutu hazardu: stawka + słowny stopień marginesu.
 * Acceptance:
 *  - sf6StakeLabel(pending) czyta pending.gamble.stake (S7/#616) → "🪙 Ryzykujesz X zł"; null gdy brak.
 *  - sf6MarginDegree(margin) mapuje |margines| (S1/#581) na słowo: z nawiązką / na styk / o włos.
 *  - app.js wpina baner stawki (#dice-stake-banner) na overlay rzutu.
 * Kontrakt JS (deterministyczny, bez LLM) — front CZYTA gotowe sygnały z payloadu, NIC nie liczy.
 */
const { test, expect } = require("@playwright/test");

// Front gracza ładuje app.js jako zwykły <script> → top-level funkcje są globalne na window.
async function loadPlayerApp(page) {
  await page.goto("/");
  await page.waitForFunction(() => typeof window.sf6StakeLabel === "function", null, {
    timeout: 15000,
  });
}

test("REGRESSION #635 — sf6StakeLabel czyta pending.gamble.stake", async ({ page }) => {
  await loadPlayerApp(page);

  const ok = await page.evaluate(() => window.sf6StakeLabel({ gamble: { stake: 5 } }));
  expect(ok, "stake 5 → baner").toBe("🪙 Ryzykujesz 5 zł");

  const big = await page.evaluate(() => window.sf6StakeLabel({ gamble: { stake: 100 } }));
  expect(big, "stake 100").toBe("🪙 Ryzykujesz 100 zł");

  // brak stawki / zero / nie-hazard → null (baner nie pokazany)
  const none = await page.evaluate(() => window.sf6StakeLabel({ skill_key: "stealth" }));
  expect(none, "test bez stawki → null").toBeNull();
  const zero = await page.evaluate(() => window.sf6StakeLabel({ gamble: { stake: 0 } }));
  expect(zero, "stawka 0 → null").toBeNull();
  const nullp = await page.evaluate(() => window.sf6StakeLabel(null));
  expect(nullp, "pending null → null").toBeNull();
});

test("REGRESSION #635 — sf6MarginDegree mapuje |margines| na słowo", async ({ page }) => {
  await loadPlayerApp(page);

  const high = await page.evaluate(() => window.sf6MarginDegree(6));
  expect(high, "duży margines → z nawiązką").toBe("z nawiązką");

  const mid = await page.evaluate(() => window.sf6MarginDegree(3));
  expect(mid, "średni → na styk").toBe("na styk");

  const low = await page.evaluate(() => window.sf6MarginDegree(1));
  expect(low, "minimalny → o włos").toBe("o włos");

  // bierze wartość bezwzględną (porażka o -7 też „z nawiązką")
  const neg = await page.evaluate(() => window.sf6MarginDegree(-7));
  expect(neg, "ujemny margines abs").toBe("z nawiązką");

  const nan = await page.evaluate(() => window.sf6MarginDegree("foo"));
  expect(nan, "nie-liczba → null").toBeNull();
});

test("REGRESSION #635 — app.js wpina baner stawki na overlay rzutu", async ({ page }) => {
  const src = await page.request.get("/js/app.js");
  expect(src.ok(), "app.js dostępny").toBeTruthy();
  const body = await src.text();
  expect(body.includes("dice-stake-banner"), "app.js zna #dice-stake-banner").toBeTruthy();
  expect(body.includes("sf6StakeLabel"), "wpięcie sf6StakeLabel").toBeTruthy();
  expect(body.includes("sf6MarginDegree"), "wpięcie sf6MarginDegree").toBeTruthy();
});
