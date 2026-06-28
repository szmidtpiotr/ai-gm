/**
 * REGRESSION #1012 (anti-stall + autopilot) — autopilot gate (AI_TEST_MODE) stays exposed.
 *
 * #1012 dodaje detektor utknięcia + tryb autopilot. Autopilot (ochrona [TEST]
 * bohatera, deterministyczny gate-choice, skrócona narracja) jest BRAMKOWANY na
 * fladze AI_TEST_MODE, którą frontend/automaty czytają z
 * /api/debug/settings/feature_flags. Ten test deterministycznie pilnuje, że ta
 * bramka nadal odpowiada i zwraca poprawny kształt — bez niej autopilot #1012 by
 * się nie włączył.
 *
 * Pełny przejazd do victory overlay (Acceptance #4) jest niedeterministyczny
 * (żywy LLM, dziesiątki tur) → weryfikuje go skill /game-smoke-pw, nie ten spec.
 *
 * Acceptance (ten spec): GET /api/debug/settings/feature_flags → 200, body ma
 * boolowe pole `ai_test_mode`.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1012 — autopilot gate (AI_TEST_MODE) exposed via feature_flags", async ({ page }) => {
  const r = await page.request.get("/api/debug/settings/feature_flags");
  expect(r.ok(), "feature_flags endpoint nie odpowiada 200 (#1012 autopilot gate)").toBeTruthy();
  const body = await r.json();
  expect(
    typeof body.ai_test_mode === "boolean",
    "feature_flags musi zwracać boolowe pole ai_test_mode (bramka autopilota #1012)"
  ).toBeTruthy();
});
