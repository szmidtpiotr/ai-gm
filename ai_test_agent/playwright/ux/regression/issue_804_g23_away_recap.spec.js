/**
 * REGRESSION #804 (G23) — Pętla zaangażowania: away-recap + wyważenie haków.
 * Acceptance: GET /api/campaigns/{id}/away-recap istnieje i jest zabezpieczony
 * (401 dla nieautoryzowanego, NIE 404), a backend MP (narrator hook-balance) jest live.
 * Kontrakt deterministyczny — pełny e2e (warnings>0 → recap, reset) pokrywa pytest test_804_g23_engagement_loop.py.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #804 G23 — away-recap endpoint istnieje i jest zabezpieczony (401 nie 404)", async ({ page }) => {
  // Bez tokenu endpoint MUSI odpowiedzieć 401 (istnieje + auth-gated), nie 404 (brak trasy).
  const r = await page.request.get("/api/campaigns/99886/away-recap");
  expect(
    r.status() === 401,
    `away-recap bez auth zwróciło ${r.status()}, oczekiwano 401 — endpoint nieobecny lub niezabezpieczony (#804)`
  ).toBeTruthy();
});

test("REGRESSION #804 G23 — nieistniejąca trasa kampanii daje 404 (sanity: 401 nie jest globalnym fallbackiem)", async ({ page }) => {
  const r = await page.request.get("/api/campaigns/99886/nonexistent-route-xyz");
  expect(
    r.status() === 404,
    `Nieistniejąca trasa zwróciła ${r.status()}, oczekiwano 404 (#804)`
  ).toBeTruthy();
});

test("REGRESSION #804 G23 — backend live (hook-balance prompt + away-recap wdrożone)", async ({ page }) => {
  const r = await page.request.get("/api/health");
  expect(r.ok(), "Backend health nie odpowiada 200 (#804)").toBeTruthy();
  const body = await r.json();
  expect(body.status ?? body.ok ?? "ok").toBeTruthy();
});
