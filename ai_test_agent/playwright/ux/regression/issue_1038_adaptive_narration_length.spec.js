/**
 * REGRESSION #1038 — Adaptacyjna długość narracji (resolver [DŁUGOŚĆ], zdjęty floor 4-6 zdań).
 * Acceptance: pipeline tury działa z nowym blokiem dyrektywy długości w kontekście narratora;
 * gracz dostaje odpowiedź GM (silnik wstrzyknął [DŁUGOŚĆ: ...] bez crasha).
 */
const { test, expect } = require("@playwright/test");
const { enterGame, sendTurnAndWaitForGm } = require("../../helpers/player_flow");

test("REGRESSION #1038 — turn pipeline OK z dyrektywą długości", async ({ page }) => {
  test.setTimeout(150000);
  await enterGame(page);
  const reply = await sendTurnAndWaitForGm(page, "Rozglądam się dokoła.");
  expect(reply, "brak odpowiedzi GM po turze (#1038 — blok [DŁUGOŚĆ] mógł wysypać pipeline)").toBeTruthy();
  expect(String(reply).trim().length, "odpowiedź GM pusta (#1038)").toBeGreaterThan(0);
});
