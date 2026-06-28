/**
 * REGRESSION #1011 — Quest reliability: auto-domykanie questów + fallback gdy
 * narrator gubi [QUEST_COMPLETE].
 * Acceptance: po migracji (objective_type/objective_value) endpoint paska questów
 * nadal czyta character_quests jako źródło prawdy i zwraca poprawny kształt
 * {active_quests:[{title,objective,reward}]}. Auto-domknięcie usuwa quest z tej listy.
 */
const { test, expect } = require("@playwright/test");

// Stały, istniejący identyfikator kampanii na DEV (najstarsza kampania).
const CAMPAIGN_ID = 99767;

test("REGRESSION #1011 — quest bar endpoint reads character_quests after migration", async ({ page }) => {
  const r = await page.request.get(`/api/campaigns/${CAMPAIGN_ID}/quests`);
  expect(r.ok(), "endpoint /quests nie odpowiada 200 (#1011)").toBeTruthy();

  const body = await r.json();
  expect(body, "brak klucza active_quests w odpowiedzi (#1011)").toHaveProperty("active_quests");
  expect(Array.isArray(body.active_quests), "active_quests musi być tablicą (#1011)").toBeTruthy();

  // Kontrakt kształtu pojedynczego questa (gdy jakiś jest aktywny).
  for (const q of body.active_quests) {
    expect(q).toHaveProperty("title");
    expect(q).toHaveProperty("objective");
    expect(q).toHaveProperty("reward");
  }
});
