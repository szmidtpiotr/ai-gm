/**
 * REGRESSION #937 (GF7) — campaign_invites table must exist: /invite-link endpoint not 500.
 * Acceptance: POST /api/multiplayer/campaigns/{id}/invite-link → nie 500 (brak tabeli).
 * Weryfikacja: endpoint lobby istnieje i odpowiada (404/403/400 są OK — brak tabeli daje 500).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #937 — campaign_invites table exists (invite-link not 500)", async ({ page }) => {
  // POST do nieistniejącej kampanii → 404 (nie 500 brak tabeli)
  const r = await page.request.post("/api/multiplayer/campaigns/999999/invite-link", {
    params: { user_id: 1 },
  });
  // 500 = tabela nie istnieje; 404 = tabela jest, kampania nie — oba są OK poza 500
  expect(r.status(), "500 = campaign_invites missing (#937)").not.toBe(500);
  expect([400, 401, 403, 404]).toContain(r.status());
});

test("REGRESSION #937 — join via unknown token gives 404 not 500", async ({ page }) => {
  const r = await page.request.get("/api/multiplayer/join/nonexistent-token-abc123", {
    params: { user_id: 1 },
  });
  expect(r.status(), "500 = campaign_invites missing (#937)").not.toBe(500);
  expect([400, 401, 403, 404]).toContain(r.status());
});
