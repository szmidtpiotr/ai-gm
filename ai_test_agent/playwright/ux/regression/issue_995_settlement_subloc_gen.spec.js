/**
 * REGRESSION #995 (Faza ML) — Auto-generacja pod-lokacji osady przy zatwierdzaniu.
 * Acceptance: subloc-defaults endpoint zwraca checklistę dla osady (village/city/etc);
 * pole generate_sublocs akceptowane przez review endpoint; safe_for_rest poprawny per typ.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #995 — subloc-defaults returns checklist for village location", async ({ page }) => {
  const r = await page.request.get("/api/admin/world/locations/cieszowice/subloc-defaults");
  expect(r.ok(), "subloc-defaults endpoint failed (#995)").toBeTruthy();
  const body = await r.json();
  expect(body.is_settlement, "cieszowice (village) should be settlement type").toBe(true);
  expect(body.checklist.length, "village checklist should have ≥2 items").toBeGreaterThanOrEqual(2);
  const hasKarczma = body.checklist.some(c => c.subtype === "tavern");
  expect(hasKarczma, "village checklist must include tavern (#995)").toBe(true);
});

test("REGRESSION #995 — subloc-defaults returns is_settlement=false for non-settlement", async ({ page }) => {
  const r = await page.request.get("/api/admin/world/locations/brzezino/subloc-defaults");
  expect(r.ok(), "subloc-defaults must not 404 for non-settlement (#995)").toBeTruthy();
  const body = await r.json();
  expect(body.is_settlement, "lumber-village should not be treated as settlement").toBe(false);
  expect(body.checklist.length, "non-settlement should have empty checklist").toBe(0);
});

test("REGRESSION #995 — subloc-defaults checklist has safe_for_rest per type", async ({ page }) => {
  const r = await page.request.get("/api/admin/world/locations/cieszowice/subloc-defaults");
  expect(r.ok(), "endpoint failed (#995)").toBeTruthy();
  const body = await r.json();
  const safeTypes = ["tavern", "inn", "temple", "shrine", "barracks", "infirmary", "civic", "garden", "library", "cells", "armory", "smithy", "shop"];
  const unsafeTypes = ["market", "slum", "port", "tomb", "tower", "work", "guild"];
  for (const item of body.checklist) {
    if (safeTypes.includes(item.subtype)) {
      expect(item.safe_for_rest, `${item.subtype} should be safe_for_rest=1 (#995)`).toBe(1);
    }
    if (unsafeTypes.includes(item.subtype)) {
      expect(item.safe_for_rest, `${item.subtype} should be safe_for_rest=0 (#995)`).toBe(0);
    }
  }
});

test("REGRESSION #995 — review endpoint accepts generate_sublocs field", async ({ page }) => {
  // Verify the API contract: field is accepted without 422 validation error.
  // We use cieszowice (already approved) — the call will 404 (not found in pending),
  // but NOT 422 (field rejected). 422 = backward compat broken.
  const r = await page.request.post("/api/admin/world/review/location/cieszowice", {
    data: JSON.stringify({ action: "approve", generate_sublocs: ["tavern"] }),
    headers: { "Content-Type": "application/json" },
  });
  const status = r.status();
  expect(status !== 422, `generate_sublocs field must be accepted by review endpoint (got 422 = schema rejection) (#995)`).toBe(true);
});
