/**
 * REGRESSION #843 (M2-4) — Lochy: card-view tabel na mobile @390px.
 * Acceptance: dungeons-table, riddles-table, tilecats-table renderują
 * card-view @390px (wrapper data-table--cards, data-label na <td>).
 * Brak regresji desktop @1280px.
 */
const { test, expect } = require("@playwright/test");

const ADMIN_URL = "http://frontend:80/admin/";

async function adminLogin(page) {
  await page.goto(ADMIN_URL);
  await page.waitForSelector('#login-user', { timeout: 10000 });
  await page.fill('#login-user', 'demo');
  await page.fill('#login-pass', 'demo');
  await page.click('#login-submit');
  await page.waitForTimeout(2000);
}

async function goToDungeons(page) {
  await page.evaluate(() => {
    document.querySelectorAll("[data-section]").forEach(el => {
      if (el.dataset.section === "dungeons") el.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
  });
  await page.waitForTimeout(2500);
  try {
    await page.waitForSelector('#dungeons-table', { timeout: 5000 });
  } catch {}
  await page.waitForTimeout(500);
}

test("REGRESSION #843 — dungeons-table ma wrapper data-table--cards @390px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await adminLogin(page);
  await goToDungeons(page);

  const wrapper = await page.$(".data-table--cards #dungeons-table, .data-table--cards table#dungeons-table");
  expect(wrapper, "#843: dungeons-table musi być w .data-table--cards").toBeTruthy();
});

test("REGRESSION #843 — <td> w dungeons-table mają data-label @390px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await adminLogin(page);
  await goToDungeons(page);

  const hasLabels = await page.evaluate(() => {
    const tds = document.querySelectorAll('#dungeons-table tbody tr:first-child td[data-label]');
    return tds.length > 0;
  });
  expect(hasLabels, "#843: <td> w dungeons-table muszą mieć data-label").toBeTruthy();
});

test("REGRESSION #843 — riddles-table ma wrapper data-table--cards", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await adminLogin(page);
  await goToDungeons(page);
  // Click Zagadki tab
  await page.evaluate(() => {
    document.querySelectorAll('.stab[data-dtab]').forEach(t => {
      if (t.dataset.dtab === 'riddles') t.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
  });
  await page.waitForTimeout(2000);

  const wrapper = await page.$(".data-table--cards #riddles-table, .data-table--cards table#riddles-table");
  expect(wrapper, "#843: riddles-table musi być w .data-table--cards").toBeTruthy();
});

test("REGRESSION #843 — tilecats-table ma wrapper data-table--cards", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await adminLogin(page);
  await goToDungeons(page);
  // Click Kategorie tab
  await page.evaluate(() => {
    document.querySelectorAll('.stab[data-dtab]').forEach(t => {
      if (t.dataset.dtab === 'tilecats') t.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
  });
  await page.waitForTimeout(2000);

  const wrapper = await page.$(".data-table--cards #tilecats-table, .data-table--cards table#tilecats-table");
  expect(wrapper, "#843: tilecats-table musi być w .data-table--cards").toBeTruthy();
});

test("REGRESSION #843 — desktop @1280px: tabela widoczna (brak regresji)", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await adminLogin(page);
  await goToDungeons(page);

  const table = await page.$('#dungeons-table');
  expect(table, "#843: dungeons-table musi istnieć na desktop").toBeTruthy();
  const display = await page.evaluate(() => {
    const t = document.querySelector('#dungeons-table');
    return t ? getComputedStyle(t).display : null;
  });
  expect(display, "#843: tabela musi być widoczna na desktop").toBe('table');
});
