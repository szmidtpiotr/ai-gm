/**
 * REGRESSION #818 (H4) — admin content-gen (Smart Entry / AI Kreator) routes to the
 * offline/local LLM profile (.170) separate from the live-gameplay preset.
 * Acceptance: smart-entry router loads + responds after the content-profile wiring
 * (regresja importu/wpięcia generate_chat(llm_config=...) nie wywala routera).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #818 — smart-entry router loads + enforces auth after content-profile wiring", async ({ page }) => {
  // Endpoint admina (auth wymagana). Po wpięciu profilu treści (#818) — nowy import
  // resolve_content_llm_config/content_llm_enabled + generate_chat(llm_config=...) —
  // router MUSI dalej się ładować i odpowiadać 401 (auth), NIE 404/500 (zepsuty import).
  const r = await page.request.get("/api/admin/smart-entry/schema?table=game_config_weapons");
  expect(
    r.status(),
    `smart-entry/schema zwróciło ${r.status()} — router się nie załadował po #818 (import/wiring)?`
  ).toBe(401);
});
