/**
 * REGRESSION #390 — in-game clock must tick across turns (was stuck at 09:00
 * because advance_clock was called with an unsupported `minutes=` kwarg).
 * Acceptance: after several narrative turns the in-game time advances.
 */
const { test, expect } = require("@playwright/test");
const { enterGame, sendTurnAndWaitForGm } = require("../../helpers/player_flow");

const TURN = 70_000;

async function readClock(page, campaignId) {
  const r = await page.request.get(`/api/campaigns/${campaignId}/clock`);
  expect(r.ok(), "Endpoint /clock nie odpowiada 200 (#390)").toBeTruthy();
  return r.json(); // { ingame_hours, day, hour, display, period }
}

test("REGRESSION #390 — zegar in-game tyka po turach (nie stoi na 09:00)", async ({ page }) => {
  test.setTimeout(12 * TURN + 60_000);
  const reset = await enterGame(page);
  const cid = reset.campaign_id;

  const before = await readClock(page, cid);
  expect(before.ingame_hours, "Zegar nie startuje od 9 po resecie (#390)").toBe(9);

  // narrative_min = 15 → ~4 tury krzyżują pełną godzinę. Gramy do 8 (margines).
  const messages = [
    "wyruszam ścieżką na północ przez las",
    "idę dalej, rozglądając się po okolicy",
    "wędruję w stronę odległych wzgórz",
    "maszeruję naprzód, nie zwalniając kroku",
    "kontynuuję podróż przez gęstwinę",
    "idę jeszcze dalej wzdłuż ścieżki",
    "ruszam w głąb lasu",
    "podążam dalej naprzód",
  ];
  let after = before;
  for (let i = 0; i < messages.length; i++) {
    await sendTurnAndWaitForGm(page, messages[i], { timeout: TURN });
    after = await readClock(page, cid);
    if (after.ingame_hours > before.ingame_hours) break; // ticked — done early
  }

  expect(
    after.ingame_hours,
    `Zegar nie ruszył z 09:00 po ${messages.length} turach (#390): ${after.display}`,
  ).toBeGreaterThan(before.ingame_hours);
});
