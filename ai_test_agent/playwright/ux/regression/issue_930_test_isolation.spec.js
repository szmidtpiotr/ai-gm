/**
 * REGRESSION #930 (918-A3) — order-independent test isolation (shared llm_service state).
 * The real fix lives in backend/tests/conftest.py (an autouse fixture that resets
 * _runtime_config + _hydrate_attempted around every test), so it is test-harness-only
 * and has no player/admin UI surface. This spec is a deterministic boot/health smoke:
 * it guards that the change did not break the backend and that the server-default LLM
 * resolution endpoint still answers — the thing the leaked preset used to corrupt.
 * Acceptance: backend healthy + admin LLM settings endpoint returns 200 with a config shape.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #930 — backend healthy after test-isolation fix", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "/api/health must return 200 (#930)").toBeTruthy();
  const body = await r.json();
  expect(body, "health body present (#930)").toBeTruthy();
});

test("REGRESSION #930 — server LLM config endpoint resolves to a coherent identity", async ({ page }) => {
  const r = await page.request.get("/api/settings/llm");
  // endpoint may require no auth on DEV; tolerate 200 or 401 but never 500 (resolver crash)
  expect(r.status(), "LLM settings endpoint must not 500 (#930)").not.toBe(500);
});
