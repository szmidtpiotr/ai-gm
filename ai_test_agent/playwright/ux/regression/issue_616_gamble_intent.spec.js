/**
 * REGRESSION #616 (FAZA S S20) — hazard deterministycznie odpala mechanikę stawki.
 * Gdy gracz deklaruje stawkę ("stawiam N złota i gram w kości"), pre-LLM most intent→tag
 * syntetyzuje [GAMBLE] PRZED skanerem skilli/U7 → tura wraca route=skill_test_keyword
 * z pending skill_key=gamble i zapisaną stawką (zamiast generycznego testu bez ruchu złota).
 * Acceptance: turn z deklaracją stawki → skill_test_keyword + pending.gamble.stake = stawka.
 * Self-cleaning: rozwiązuje stworzony pending, by zostawić sesję czystą dla kolejnego runu.
 */
const { test, expect } = require("@playwright/test");

const CAMPAIGN_ID = 78; // kampania testowa #615 (warrior id 2) na DEV
const CHARACTER_ID = 2;

test("REGRESSION #616 — deklaracja stawki hazardu tworzy pending gamble (skill_test_keyword)", async ({ page }) => {
  const turn = await page.request.post(`/api/campaigns/${CAMPAIGN_ID}/turns`, {
    data: { character_id: CHARACTER_ID, text: "Siadam przy stole, stawiam 3 sztuki złota i gram w kości." },
  });
  expect(turn.ok(), "endpoint /turns nie odpowiada 200 (#616)").toBeTruthy();
  const body = await turn.json();

  expect(body.route, "tura hazardu powinna iść route=skill_test_keyword, nie generyczny test").toBe("skill_test_keyword");
  const pending = body.skill_test_pending || {};
  expect(pending.skill_key, "pending musi być testem gamble").toBe("gamble");
  expect(pending.gamble && pending.gamble.stake, "pending musi nieść zwalidowaną stawkę").toBe(3);

  // Self-clean: rozwiąż pending, żeby sesja wróciła do NARRATIVE (kolejny run nie flake'uje).
  if (pending.skill_test_id) {
    const res = await page.request.post(`/api/campaigns/${CAMPAIGN_ID}/skill-test/resolve`, {
      data: { character_id: CHARACTER_ID, skill_test_id: pending.skill_test_id, d20_roll: 12 },
    });
    expect(res.ok(), "resolve gamble nie odpowiada 200").toBeTruthy();
  }
});
