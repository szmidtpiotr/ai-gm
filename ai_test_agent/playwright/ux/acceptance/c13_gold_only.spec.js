/**
 * Acceptance — C13 (#367). Part of the C1–C19 FAZA 1 suite.
 * Split from c_series.spec.js so each task runs individually from
 * Admin3 → Narzędzia → 🎭 Playwright.
 */
const { test, expect } = require("@playwright/test");
const { enterGame, sendTurnAndWaitForGm, openCharacterSheet } = require("../../helpers/player_flow");
const {
  playUntilGoal,
  containsAny,
  playerState,
  TRAVEL_HINT_WORDS,
  NON_GP_CURRENCY_WORDS,
  EQUIPMENT_LOSS_WORDS,
} = require("../../helpers/acceptance");

const TURN = 70_000;

test("C13 (#367) — LLM używa tylko złota (GP), brak innych walut", async ({ page }) => {
  test.setTimeout(12 * TURN + 60_000);
  await enterGame(page);
  const res = await playUntilGoal(page, {
    messages: [
      "pytam kupca, ile kosztuje miecz",
      "ile zapłacę za nocleg w karczmie?",
      "chcę kupić miksturę leczniczą, jaka cena?",
      "ile kosztuje porcja jedzenia?",
    ],
    maxTurns: 12,
    turnTimeout: TURN,
    // goal: never resolves early — we want to scan ALL turns; assert after.
    goal: () => false,
  });
  const offenders = res.responses.filter((r) => containsAny(r, NON_GP_CURRENCY_WORDS));
  expect(
    offenders.length,
    `LLM użył innej waluty niż GP w ${offenders.length}/${res.turns} turach (C13): ${offenders
      .slice(0, 2)
      .join(" || ")}`,
  ).toBe(0);
});
