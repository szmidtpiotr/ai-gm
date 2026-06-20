/**
 * REGRESSION #727 — Combat Sandbox w aktywnym panelu /admin/ faktycznie zadaje obrażenia.
 * Bug: /admin/ → Narzędzia → ⚔ Combat Sandbox klikał TYLKO /api/admin/sandbox/advance-turn
 *      (przesunięcie wskaźnika tury), nigdy /combat/resolve-attack — HP nikomu nie spadało,
 *      walka była no-opem ("sandbox nie działa wcale z pozycji admin panelu").
 * Acceptance: po Setup → Start → kilku turach Atak/Tura wroga suma HP combatantów < HP startowe
 *             (ktoś oberwał) — silnik walki realnie się wykonuje z poziomu /admin/.
 */
const { test, expect } = require("@playwright/test");

const ADMIN_USER = process.env.AI_TEST_ADMIN_USER || "demo";
const ADMIN_PASS = process.env.AI_TEST_ADMIN_PASS || "demo";
// [SMOKE] Wojownik — idle, bezpieczny do klonowania w sandboxie.
const SOURCE_HERO_ID = 999409;

async function adminLogin(page) {
  const res = await page.request.post("/api/admin/dev-login", {
    data: { username: ADMIN_USER, password: ADMIN_PASS },
  });
  expect(res.ok(), "dev-login nie zwrócił 200 (#727)").toBeTruthy();
  const { token } = await res.json();
  expect(token, "dev-login bez tokenu (#727)").toBeTruthy();
  await page.addInitScript((t) => localStorage.setItem("aigm_admin_token", t), token);
}

test("REGRESSION #727 — Combat Sandbox w /admin/ zadaje obrażenia (HP spada)", async ({ page }) => {
  await adminLogin(page);
  await page.goto("/admin/#tools");

  // Otwórz zakładkę Combat Sandbox.
  const combatTab = page.locator('.stab[data-toolstab="combat"]');
  await combatTab.waitFor({ state: "visible", timeout: 20000 });
  await combatTab.click();

  // Pickery muszą się zaludnić (bohaterowie + wrogowie z backendu).
  await page.locator("#cs-hero-picker button[data-hero-id]").first().waitFor({ timeout: 20000 });
  await page.locator(`#cs-hero-picker button[data-hero-id="${SOURCE_HERO_ID}"]`).click();

  // Wybierz słabego wroga (goblin) — gwarantuje trafienia w kilku rundach.
  const gob = page.locator('#cs-enemy-picker input[data-enemy-key="goblin"]');
  await gob.waitFor({ timeout: 10000 });
  await gob.check();

  // Setup (klon bohatera) → Start walki.
  await page.locator("#cs-setup-btn").click();
  const startBtn = page.locator("#cs-start-btn");
  await expect(startBtn, "Start nie odblokował się po Setup (#727)").toBeEnabled({ timeout: 15000 });
  await startBtn.click();

  // Odczytaj sumę HP wszystkich combatantów ze stanu walki.
  const sumHp = async () =>
    page.evaluate(() => {
      const el = document.getElementById("cs-combat-state");
      if (!el) return null;
      const txt = el.innerText || "";
      // Wiersze "HP x/y" — zsumuj bieżące HP.
      const m = [...txt.matchAll(/HP\s+(\d+)\s*\/\s*(\d+)/g)];
      if (!m.length) return null;
      return m.reduce((acc, g) => acc + Number(g[1]), 0);
    });

  await expect.poll(sumHp, { timeout: 10000 }).not.toBeNull();
  const startTotal = await sumHp();
  expect(startTotal, "Brak combatantów w stanie walki (#727)").toBeGreaterThan(0);

  // Rozegraj do ~14 akcji: jeśli tura gracza → Atak, jeśli wroga → Tura wroga.
  for (let i = 0; i < 14; i++) {
    const state = (await page.locator("#cs-combat-state").innerText().catch(() => "")) || "";
    if (/w akcji/.test(state) && !/Goblin\s+w akcji/i.test(state)) {
      // tura gracza (combatant aktywny to nie goblin)
      await page.locator("#cs-attack-btn").click().catch(() => {});
    } else {
      await page.locator("#cs-enemy-turn-btn").click().catch(() => {});
    }
    await page.waitForTimeout(700);
    const cur = await sumHp();
    if (cur != null && cur < startTotal) break; // ktoś oberwał — silnik działa
  }

  const endTotal = await sumHp();
  expect(
    endTotal,
    `HP nie spadło po ${14} akcjach — sandbox /admin/ nie zadaje obrażeń (start=${startTotal}, end=${endTotal}) (#727)`
  ).toBeLessThan(startTotal);
});
