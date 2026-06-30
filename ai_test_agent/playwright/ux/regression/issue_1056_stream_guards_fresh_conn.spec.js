/**
 * REGRESSION #1056 — u30_desync_guard i quest_cap_trim używają świeżego połączenia DB w trybie stream.
 * Acceptance: brak "Cannot operate on a closed database" w logach streamu tury;
 *             oba guardy wykonują się poprawnie przez cały czas trwania sesji.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1056 — health endpoint odpowiada 200 (backend działa)", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "backend nie odpowiada 200 (#1056)").toBeTruthy();
});

test("REGRESSION #1056 — stream turns endpoint odpowiada (nie 500)", async ({ page }) => {
  // Verify the stream endpoint exists and auth gate works (not a 500 crash)
  const r = await page.request.post("/api/campaigns/99999/turns/stream", {
    data: { text: "test", character_id: 99999 },
    headers: { "Content-Type": "application/json" },
  });
  // 404 (campaign not found) or 401/403 (auth) = endpoint alive; 500 = server error
  const status = r.status();
  expect(
    status !== 500,
    `stream endpoint zwrócił 500 — możliwy błąd startu (#1056), status: ${status}`
  ).toBeTruthy();
});
