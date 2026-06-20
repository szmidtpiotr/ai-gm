/**
 * REGRESSION #772/#774 — LLM-authored [COMBAT_START] trusted after friendly-NPC gate.
 *
 * Bug: _validate_combat_start_target(source='llm') required the enemy key to exist in
 * game_config_enemies catalog. LLM-invented keys (e.g. 'nozownik_testowy') were
 * rejected → "*(Cel ataku okazuje się nieosiągalny — walka nie wybucha.)*" appended.
 *
 * Fix: after the friendly-NPC gate, source='llm' returns (True,'') unconditionally.
 * initiate_combat() handles unknown keys via INSERT OR IGNORE with pending_review.
 *
 * Uses /api/debug/stub_llm (AI_TEST_MODE only) to inject a deterministic LLM response
 * containing [COMBAT_START:invented_key] without hitting the real LLM.
 */
const { test, expect } = require("@playwright/test");
const { enterGame, sendTurnAndWaitForGm } = require("../../helpers/player_flow");

const BACKEND = process.env.BACKEND_URL || "http://192.168.1.61:8100";
const TURN = 60_000;

async function setLlmStub(text) {
  const res = await fetch(`${BACKEND}/api/debug/stub_llm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error(`stub_llm failed: ${res.status}`);
}

async function clearLlmStub() {
  await fetch(`${BACKEND}/api/debug/stub_llm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: null }),
  }).catch(() => {});
}

test("REGRESSION #772 — LLM invented key starts combat (nie: nieosiągalny)", async ({ page }) => {
  test.setTimeout(3 * TURN);

  // Inject stub LLM text with an invented enemy key (not in game_config_enemies catalog).
  // Before fix: _validate_combat_start_target(source='llm') returned
  //   (False, 'combat_target_unknown') → combat blocked → "nieosiągalny" appended.
  // After fix: returns (True,'') → initiate_combat() called → combat banner appears.
  await setLlmStub(
    '{"narrative":"Nożownik rzuca się na ciebie z wyciągniętym ostrzem!","roll_cue":"Roll Initiative d20"} [COMBAT_START:nozownik_testowy]',
  );

  try {
    await enterGame(page);
    await sendTurnAndWaitForGm(page, "Atakuję napastnika!", { timeout: TURN });

    const combatVisible = await page
      .locator("#combat-banner")
      .isVisible({ timeout: 5000 })
      .catch(() => false);

    expect(
      combatVisible,
      "#772 regresja: LLM-invented key 'nozownik_testowy' powinien uruchomić walkę (brak #combat-banner — fix cofnięty?)",
    ).toBeTruthy();
  } finally {
    await clearLlmStub();
  }
});

test("REGRESSION #772 — nieosiągalny NIE pojawia się przy LLM COMBAT_START", async ({ page }) => {
  test.setTimeout(3 * TURN);

  await setLlmStub(
    '{"narrative":"Bandyta wyskakuje zza rogu!","roll_cue":"Roll Initiative d20"} [COMBAT_START:bandyta_uliczny]',
  );

  try {
    await enterGame(page);
    const bubble = await sendTurnAndWaitForGm(page, "Dobywam broni i atakuję!", { timeout: TURN });
    const text = ((await bubble.textContent()) || "").toLowerCase();

    expect(
      text.includes("nieosiągalny"),
      "#772: tekst 'nieosiągalny' nie powinien się pojawić gdy LLM emituje COMBAT_START",
    ).toBeFalsy();
  } finally {
    await clearLlmStub();
  }
});
