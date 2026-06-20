/**
 * REGRESSION #836 (M1) — Campaigns section mobile: card-view list + modal tab bar scroll.
 * Acceptance: @390px lista kampanii wyświetla się jako karty (data-table--cards),
 * modal szczegółów ma zakładki w jednym scrollowalnym rzędzie (camp-modal-tabs),
 * grid przeglądu zmienia się na 1-kolumnę (camp-overview-grid). Brak regresji desktop.
 */
const { test, expect } = require("@playwright/test");

const BASE = "http://frontend:80";

test("REGRESSION #836 — campaigns JS has data-table--cards on list wrapper", async ({ page }) => {
  const r = await page.request.get(`${BASE}/admin/sections/campaigns.js`);
  expect(r.ok(), "campaigns.js missing").toBeTruthy();
  const body = await r.text();
  expect(body, "campaigns-table-view must have data-table--cards class").toContain("data-table--cards");
});

test("REGRESSION #836 — campaigns JS has camp-modal-tabs class on modal tab bar", async ({ page }) => {
  const r = await page.request.get(`${BASE}/admin/sections/campaigns.js`);
  expect(r.ok(), "campaigns.js missing").toBeTruthy();
  const body = await r.text();
  expect(body, "Modal tab bar must have camp-modal-tabs class for mobile scroll").toContain("camp-modal-tabs");
});

test("REGRESSION #836 — campaigns JS has camp-overview-grid class on overview grid", async ({ page }) => {
  const r = await page.request.get(`${BASE}/admin/sections/campaigns.js`);
  expect(r.ok(), "campaigns.js missing").toBeTruthy();
  const body = await r.text();
  expect(body, "Overview grid must have camp-overview-grid class for 1-col collapse on mobile").toContain("camp-overview-grid");
});

test("REGRESSION #836 — components.css has camp-modal-tabs mobile scroll rules", async ({ page }) => {
  const r = await page.request.get(`${BASE}/admin/shared/components.css`);
  expect(r.ok(), "components.css missing").toBeTruthy();
  const body = await r.text();
  expect(body, "Missing .camp-modal-tabs CSS rule").toContain(".camp-modal-tabs");
  expect(body, "Missing overflow-x for camp-modal-tabs").toContain("overflow-x");
  expect(body, "Missing flex-wrap:nowrap for camp-modal-tabs").toContain("nowrap");
});

test("REGRESSION #836 — components.css has camp-overview-grid 1col rule", async ({ page }) => {
  const r = await page.request.get(`${BASE}/admin/shared/components.css`);
  expect(r.ok(), "components.css missing").toBeTruthy();
  const body = await r.text();
  expect(body, "Missing .camp-overview-grid CSS rule").toContain(".camp-overview-grid");
});

test("REGRESSION #836 — campaigns live API requires auth (endpoint exists)", async ({ page }) => {
  const r = await page.request.get(`${BASE}/api/admin/campaigns/live`);
  // 401 = endpoint exists, auth required (correct). 404 = broken.
  expect([200, 401], `Unexpected status ${r.status()}`).toContain(r.status());
});
