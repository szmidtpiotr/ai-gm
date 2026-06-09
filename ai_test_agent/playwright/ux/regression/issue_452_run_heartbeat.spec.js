/**
 * REGRESSION #452 (FADM-P16 follow-up) — panel Playwright group-run nie zrywa się ("network error").
 * Group run odpala ~114 testów; Playwright milczy ~90s na starcie. Bez heartbeatu proxy (~60s idle)
 * zrywało SSE → frontend "Błąd: network error". Fix: backend wysyła natychmiastowy hello + keepalive.
 * Acceptance: /api/test_runner/playwright-run zaczyna strumień od eventu hello (od razu, nie po 90s).
 */
const { test, expect } = require("@playwright/test");

async function _token(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  return (await r.json()).token;
}

test("REGRESSION #452 — playwright-run emituje natychmiastowy hello (anty network-error)", async ({ page }) => {
  const token = await _token(page);
  const r = await page.request.post("/api/test_runner/playwright-run", {
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    data: { spec: "regression/__nonexistent__.spec.js" },
  });
  expect(r.ok(), "playwright-run nie 200 (#452)").toBeTruthy();
  expect(r.headers()["content-type"] || "", "musi być SSE (#452)").toContain("text/event-stream");
  const body = await r.text();
  const firstEvent = body.split("\n\n")[0];
  expect(firstEvent, "pierwszy event musi być natychmiastowym hello (#452)").toContain("Uruchamianie");
});

test("REGRESSION #452 — playwright-run wymaga tokenu admina", async ({ page }) => {
  const r = await page.request.post("/api/test_runner/playwright-run", {
    headers: { "Content-Type": "application/json" },
    data: { spec: "x.spec.js" },
  });
  expect(r.status(), "run musi być auth-gated (#452)").toBe(401);
});
