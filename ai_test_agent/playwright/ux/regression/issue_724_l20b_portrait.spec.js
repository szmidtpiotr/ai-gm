/**
 * REGRESSION #724 (L20b) — Portrait modal + initiative chip thumbnail on combat start.
 * Acceptance: Combat state contains image_url per enemy combatant; portrait-modal
 * element present in player UI; sprite overlay section removed from admin tile editor.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

async function adminLogin(page) {
  const resp = await page.request.post(`${BASE}/api/admin/dev-login`, {
    data: { username: "demo", password: "demo" },
  });
  const { token } = await resp.json();
  await page.addInitScript((t) => {
    localStorage.setItem("aigm_admin_token", t);
    localStorage.setItem("aigm_admin_user", "demo");
  }, token);
  return token;
}

// ── Test 1: backend health ────────────────────────────────────────────────────

test("REGRESSION #724 L20b — backend health ok", async ({ page }) => {
  const healthResp = await page.request.get(`${BASE}/api/health`);
  expect(healthResp.ok(), "Backend health check failed (#724)").toBeTruthy();
  const health = await healthResp.json();
  expect(health.status, "Backend not healthy").toBe("ok");
});

// ── Test 2: enemy catalog API returns image_url column ───────────────────────

test("REGRESSION #724 L20b — enemy catalog returns image_url field", async ({ page }) => {
  const token = await adminLogin(page);
  const r = await page.request.get(`${BASE}/api/admin/enemies`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "GET /api/admin/enemies failed (#724)").toBeTruthy();
  const body = await r.json();
  const enemies = body.items || [];
  expect(enemies.length, "No enemies in catalog").toBeGreaterThan(0);
  // image_url key must exist (can be null if no portrait generated)
  const firstEnemy = enemies[0];
  expect(
    "image_url" in firstEnemy,
    `Enemy ${firstEnemy.key} missing image_url key — L20a migration may not have run`
  ).toBeTruthy();
});

// ── Test 3: portrait modal HTML exists in player UI ──────────────────────────

test("REGRESSION #724 L20b — portrait modal element present in player UI", async ({ page }) => {
  await page.goto(`${BASE}/`);
  // The portrait-modal should be in DOM (hidden by default)
  const modal = page.locator("#portrait-modal");
  await expect(modal, "portrait-modal element missing from player UI — L20b HTML not deployed").toBeAttached();
  // Must be hidden initially
  await expect(modal, "portrait-modal should be hidden on load").toBeHidden();
});

// ── Test 4: admin dungeons tile editor has NO sprite overlay section ──────────

test("REGRESSION #724 L20b — tile editor has no sprite overlay section", async ({ page }) => {
  await adminLogin(page);
  await page.goto(`${BASE}/admin/#dungeons`);
  await page.waitForTimeout(2000); // section load

  // The sprite overlay section element must not exist
  const spriteSection = page.locator("#tf-overlay-section");
  const count = await spriteSection.count();
  expect(count, "#tf-overlay-section still in DOM — sprite editor not removed (#724)").toBe(0);
});
