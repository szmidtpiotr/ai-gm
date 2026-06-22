/**
 * REGRESSION #811 (G31) — mp_round_completed_total metric visible on /metrics endpoint.
 * Acceptance: Prometheus /metrics page lists mp_round_completed_total counter with correct HELP/TYPE.
 */
const { test, expect } = require("@playwright/test");

const BACKEND_URL = process.env.BACKEND_URL || "http://backend:8100";

test("REGRESSION #811 — mp_round_completed_total metric defined and exposed on /metrics", async ({ page }) => {
  const r = await page.request.get(`${BACKEND_URL}/metrics`);
  expect(r.ok(), `/metrics not accessible (${r.status()}) (#811)`).toBeTruthy();

  const body = await r.text();
  expect(
    body.includes("mp_round_completed_total"),
    "mp_round_completed_total not found in /metrics output (#811)"
  ).toBeTruthy();
  expect(
    body.includes("# TYPE mp_round_completed_total counter"),
    "mp_round_completed_total must be TYPE counter (#811)"
  ).toBeTruthy();
});
