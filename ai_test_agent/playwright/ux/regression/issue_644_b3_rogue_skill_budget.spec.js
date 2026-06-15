/**
 * REGRESSION #644 (B3) — Łotrzyk dostaje własny budżet skilli przy tworzeniu postaci.
 * Tożsamość: rogue = NAJWIĘCEJ skilli. Tworzenie hero-first (POST /characters)
 * losuje 9 aktywnych skilli (rank ≥ 1) z biasem złodzieja, NIE fallback warrior (7).
 * Acceptance: świeżo utworzony łotrzyk ma ≥9 aktywnych skilli i > niż wojownik.
 */
const { test, expect } = require("@playwright/test");

const DEMO_USER = 1;

async function createHero(page, archetype) {
  const r = await page.request.post("/api/characters", {
    data: {
      user_id: DEMO_USER,
      name: `[B3test] ${archetype}`,
      system_id: "fantasy",
      sheet_json: { archetype },
    },
  });
  expect(r.ok(), `POST /characters (${archetype}) nie zwrócił 200 (#644)`).toBeTruthy();
  const body = await r.json();
  return body;
}

function activeSkillCount(sheet) {
  const skills = (sheet && sheet.skills) || {};
  return Object.values(skills).filter((v) => Number(v) > 0).length;
}

test("REGRESSION #644 — łotrzyk ma własny budżet skilli (9 aktywnych, > wojownik)", async ({ page }) => {
  const rogue = await createHero(page, "rogue");
  const warrior = await createHero(page, "warrior");

  const rogueSheet = rogue.sheet_json || rogue.sheet || rogue;
  const warriorSheet = warrior.sheet_json || warrior.sheet || warrior;

  const rogueActive = activeSkillCount(rogueSheet);
  const warriorActive = activeSkillCount(warriorSheet);

  // Cleanup utworzonych bohaterów testowych zanim asercje (best-effort).
  for (const c of [rogue, warrior]) {
    const cid = c.id || c.character_id;
    if (cid) {
      await page.request.delete(`/api/characters/${cid}?user_id=${DEMO_USER}`).catch(() => {});
    }
  }

  expect(rogueActive, `łotrzyk powinien mieć 9 aktywnych skilli, ma ${rogueActive} (#644)`).toBe(9);
  expect(rogueActive, `łotrzyk (${rogueActive}) > wojownik (${warriorActive}) (#644)`).toBeGreaterThan(
    warriorActive
  );
});
