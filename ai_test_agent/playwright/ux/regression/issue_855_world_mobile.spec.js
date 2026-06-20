/**
 * REGRESSION #855 (M2-2) — Sekcja Świat: tabele NPC/Wrogowie/Łupy/Oczekujące renderują się poprawnie na mobile @390px.
 * Acceptance: data-table--cards na NPC/Wrogowie/Oczekujące; data-table--scroll na Tabelach Łupów.
 */
const { test, expect } = require("@playwright/test");

const ADMIN_URL = "http://frontend:80/admin/";

async function adminLogin(page) {
  await page.goto(ADMIN_URL);
  await page.waitForSelector('input[type="text"]', { timeout: 10000 });
  await page.fill('input[type="text"]', "demo");
  await page.fill('input[type="password"]', "demo");
  await page.click("button.btn-primary");
  await page.waitForTimeout(2000);
}

test("REGRESSION #855 — NPC table wrapper uses data-table--cards on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await adminLogin(page);

  // Navigate to world section
  await page.evaluate(() => {
    document.querySelectorAll("[data-section]").forEach(el => {
      if (el.dataset.section === "world") el.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
  });
  await page.waitForTimeout(2000);

  // NPC table wrapper must have cards modifier
  const npcWrapper = await page.$(".data-table--cards #npcs-table, .data-table--cards table#npcs-table");
  expect(npcWrapper, "#855: NPC table must be inside .data-table--cards wrapper").toBeTruthy();
});

test("REGRESSION #855 — Enemies table wrapper uses data-table--cards on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await adminLogin(page);

  await page.evaluate(() => {
    document.querySelectorAll("[data-section]").forEach(el => {
      if (el.dataset.section === "world") el.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
  });
  await page.waitForTimeout(2000);

  // Click enemies tab
  await page.evaluate(() => {
    document.querySelectorAll(".stab[data-wtab]").forEach(t => {
      if (t.dataset.wtab === "enemies") t.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
  });
  await page.waitForTimeout(2000);

  const enemyWrapper = await page.$(".data-table--cards #world-enemies-table, .data-table--cards table#world-enemies-table");
  expect(enemyWrapper, "#855: Enemies table must be inside .data-table--cards wrapper").toBeTruthy();
});

test("REGRESSION #855 — no horizontal page overflow at 390px in world section", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await adminLogin(page);

  await page.evaluate(() => {
    document.querySelectorAll("[data-section]").forEach(el => {
      if (el.dataset.section === "world") el.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
  });
  await page.waitForTimeout(2000);

  const overflow = await page.evaluate(() => {
    return document.documentElement.scrollWidth > document.documentElement.clientWidth;
  });
  expect(overflow, "#855: page must not overflow horizontally at 390px").toBeFalsy();
});
