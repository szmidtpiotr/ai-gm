/**
 * REGRESSION #571 (U19) — Recap "Poprzednio w Twojej przygodzie…" endpoint contract.
 * Acceptance: GET /api/campaigns/{id}/recap zwraca decyzję should_show + skomponowane
 * pola (summary / recent_turns / active_quests); trigger >24h liczy backend.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #571 — recap endpoint zwraca poprawny kontrakt", async ({ page }) => {
  // Use an existing campaign id range; pick the lowest valid campaign via list, fallback to 1.
  let cid = 1;
  try {
    const lr = await page.request.get("/api/campaigns?user_id=1");
    if (lr.ok()) {
      const body = await lr.json();
      const arr = Array.isArray(body) ? body : (body.campaigns || []);
      if (arr.length && arr[0].id) cid = arr[0].id;
    }
  } catch (_e) { /* fallback to 1 */ }

  const r = await page.request.get(`/api/campaigns/${cid}/recap`);
  expect(r.ok(), "endpoint /recap nie odpowiada 200 (#571)").toBeTruthy();
  const data = await r.json();

  // Kontrakt pól — kształt karty recap.
  expect(typeof data.should_show, "should_show musi być boolean").toBe("boolean");
  expect("turn_count" in data, "brak turn_count").toBeTruthy();
  expect(Array.isArray(data.recent_turns), "recent_turns musi być tablicą").toBeTruthy();
  expect(Array.isArray(data.active_quests), "active_quests musi być tablicą").toBeTruthy();
  expect("threshold_hours" in data, "brak threshold_hours").toBeTruthy();

  // Trigger jest mechaniczny: jeśli kampania ma 0 tur → karta się NIE pokazuje.
  if (data.turn_count === 0) {
    expect(data.should_show, "0 tur → should_show=false").toBeFalsy();
  }
});

test("REGRESSION #571 — nieistniejąca kampania zwraca 404", async ({ page }) => {
  const r = await page.request.get("/api/campaigns/99999999/recap");
  expect(r.status(), "brak kampanii → 404").toBe(404);
});
