/**
 * Phase 9A-6 — walidacja scenariuszy + obecność data-testid w frontcie.
 * Uruchomienie: node tests/test_scenarios.js  (katalog: ai_test_agent)
 */
const assert = require("assert");
const path = require("path");
const fs = require("fs");
const { validateScenario } = require("../agent/scenario_validator");

const ROOT = path.join(__dirname, "..");
const SCENARIOS_DIR = path.join(ROOT, "scenarios");
const FRONTEND_DIR = path.join(ROOT, "..", "frontend");

const BUNDLED = [
  "cheat_gm_location.json",
  "inventory_exploit.json",
  "honest_player_flow.json",
  "gm_manipulation_gold.json",
];

BUNDLED.forEach((file) => {
  const p = path.join(SCENARIOS_DIR, file);
  assert.ok(fs.existsSync(p), `Brak pliku: ${p}`);
  const sc = JSON.parse(fs.readFileSync(p, "utf8"));
  const errors = validateScenario(sc);
  assert.deepStrictEqual(errors, [], `${file} — błędy walidacji: ${JSON.stringify(errors)}`);
  // eslint-disable-next-line no-console
  console.log(`ok  ${file}`);
});

const noGoal = { name: "x", persona: "y", success_criteria: {}, max_steps: 10 };
assert.ok(
  validateScenario(noGoal).some((e) => e.toLowerCase().includes("goal")),
  "walidator powinien zgłosić brak goal"
);
// eslint-disable-next-line no-console
console.log("ok  walidator odrzuca brak goal");

const zeroSteps = {
  name: "x",
  goal: "y",
  persona: "z",
  success_criteria: {},
  max_steps: 0,
};
assert.ok(
  validateScenario(zeroSteps).some((e) => e.includes("max_steps")),
  "walidator powinien zgłosić max_steps=0"
);
// eslint-disable-next-line no-console
console.log("ok  walidator odrzuca max_steps=0");

const indexHtml = path.join(FRONTEND_DIR, "index.html");
assert.ok(fs.existsSync(indexHtml), `Brak ${indexHtml}`);
const indexContent = fs.readFileSync(indexHtml, "utf8");
["chat-input", "chat-send", "player-location", "chat-messages"].forEach((tid) => {
  assert.ok(
    indexContent.includes(`data-testid="${tid}"`),
    `Brak data-testid="${tid}" w index.html`
  );
});
// eslint-disable-next-line no-console
console.log("ok  data-testid w index.html");

const uiJs = path.join(FRONTEND_DIR, "js", "ui.js");
assert.ok(fs.existsSync(uiJs), `Brak ${uiJs}`);
const uiContent = fs.readFileSync(uiJs, "utf8");
assert.ok(
  uiContent.includes("setAttribute") && uiContent.includes("gm-message"),
  "ui.js powinien ustawiać data-testid gm-message na wiadomościach asystenta"
);
// eslint-disable-next-line no-console
console.log("ok  data-testid gm-message w ui.js");

// eslint-disable-next-line no-console
console.log("\nWszystkie testy 9A-6: OK");
