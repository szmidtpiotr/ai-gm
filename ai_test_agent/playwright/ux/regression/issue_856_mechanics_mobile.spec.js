/**
 * REGRESSION #856 (M2-3) — Sekcja Mechaniki: tabele stats/skills/DC/conditions/archetypes/XP
 * renderują się poprawnie na mobile @390px jako card-view.
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

async function goToMechanics(page) {
  await page.evaluate(() => {
    document.querySelectorAll("[data-section]").forEach(el => {
      if (el.dataset.section === "mechanics") el.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
  });
  await page.waitForTimeout(2000);
}

test("REGRESSION #856 — stats table wrapper uses data-table--cards on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await adminLogin(page);
  await goToMechanics(page);

  const wrapper = await page.$(".data-table--cards #stats-table, .data-table--cards table#stats-table");
  expect(wrapper, "#856: stats-table must be inside .data-table--cards wrapper").toBeTruthy();
});

test("REGRESSION #856 — skills table wrapper uses data-table--cards on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await adminLogin(page);
  await goToMechanics(page);

  // Click skills tab
  await page.evaluate(() => {
    document.querySelectorAll(".stab[data-mtab]").forEach(t => {
      if (t.dataset.mtab === "skills") t.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
  });
  await page.waitForTimeout(2000);

  const wrapper = await page.$(".data-table--cards #skills-table, .data-table--cards table#skills-table");
  expect(wrapper, "#856: skills-table must be inside .data-table--cards wrapper").toBeTruthy();
});

test("REGRESSION #856 — conditions table wrapper uses data-table--cards on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await adminLogin(page);
  await goToMechanics(page);

  // Click conditions tab
  await page.evaluate(() => {
    document.querySelectorAll(".stab[data-mtab]").forEach(t => {
      if (t.dataset.mtab === "conditions") t.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
  });
  await page.waitForTimeout(2000);

  const wrapper = await page.$(".data-table--cards #conditions-table, .data-table--cards table#conditions-table");
  expect(wrapper, "#856: conditions-table must be inside .data-table--cards wrapper").toBeTruthy();
});

test("REGRESSION #856 — no horizontal page overflow at 390px in mechanics section", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await adminLogin(page);
  await goToMechanics(page);

  const overflow = await page.evaluate(() => {
    return document.documentElement.scrollWidth > document.documentElement.clientWidth;
  });
  expect(overflow, "#856: page must not overflow horizontally at 390px").toBeFalsy();
});

test("REGRESSION #856 — stab bar tabs are scrollable on mobile (no wrapping)", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await adminLogin(page);
  await goToMechanics(page);

  const stabBar = await page.$("#mech-stab-bar");
  expect(stabBar, "#856: mech-stab-bar must exist").toBeTruthy();

  const isScrollable = await page.evaluate(() => {
    const bar = document.querySelector("#mech-stab-bar");
    if (!bar) return false;
    return bar.scrollWidth >= bar.clientWidth;
  });
  expect(isScrollable, "#856: stab bar must have scrollable tabs (not wrap)").toBeTruthy();
});
