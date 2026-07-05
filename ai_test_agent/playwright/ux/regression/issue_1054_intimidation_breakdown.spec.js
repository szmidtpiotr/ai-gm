/**
 * REGRESSION #1054 (część 2) — bonus przewagi widoczny w rozbiciu rzutu.
 * Acceptance: sf8SkillBreakdown pokazuje wiersz "Przewaga" gdy modifier_breakdown
 * zawiera advantage_bonus (gate po Skradaniu: +2 sukces / +4 kryt); bez bonusu
 * wiersz nie występuje (backward compat).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1054 — rozbicie rzutu zawiera wiersz Przewaga dla advantage_bonus", async ({ page }) => {
  await page.goto("/");
  await page.waitForFunction(() => typeof window.sf8SkillBreakdown === "function");

  const withBonus = await page.evaluate(() =>
    window.sf8SkillBreakdown({ governing_stat: "CHA", stat_mod: 1, skill_rank: 0, proficiency: 0, advantage_bonus: 2 })
  );
  const advRow = withBonus.find((p) => p.label === "Przewaga");
  expect(advRow, "brak wiersza Przewaga w rozbiciu (#1054)").toBeTruthy();
  expect(advRow.value).toBe(2);

  const critBonus = await page.evaluate(() =>
    window.sf8SkillBreakdown({ governing_stat: "CHA", stat_mod: 1, advantage_bonus: 4 })
  );
  expect(critBonus.find((p) => p.label === "Przewaga").value).toBe(4);

  const noBonus = await page.evaluate(() =>
    window.sf8SkillBreakdown({ governing_stat: "CHA", stat_mod: 1, skill_rank: 2 })
  );
  expect(noBonus.find((p) => p.label === "Przewaga"), "wiersz Przewaga nie może występować bez bonusu").toBeFalsy();
});
