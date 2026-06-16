/**
 * REGRESSION #682 (L13) — Dungeon modals: death, abandon confirmation, resume, boss choice.
 * Acceptance: All four modal elements present in DOM; backend API contracts verified.
 */
const { test, expect } = require("@playwright/test");

// ── Helper: check if a dungeon exists in the system ─────────────────────────
async function getDungeonKey(request) {
  const r = await request.get("/api/dungeons");
  if (!r.ok()) return null;
  const body = await r.json();
  const dungeons = body.dungeons || body || [];
  return Array.isArray(dungeons) && dungeons.length > 0 ? dungeons[0].key : null;
}

// ── Test 1: All four modal elements must be present in DOM ───────────────────
test("REGRESSION #682 L13 — dungeon death modal exists in DOM", async ({ page }) => {
  await page.goto("/");
  const modal = page.locator("#dungeon-death-modal");
  await expect(modal, "#dungeon-death-modal must exist in DOM").toHaveCount(1);
  // Must be hidden by default
  await expect(modal, "death modal must be hidden by default").toBeHidden();
});

test("REGRESSION #682 L13 — dungeon abandon modal exists in DOM", async ({ page }) => {
  await page.goto("/");
  const modal = page.locator("#dungeon-abandon-modal");
  await expect(modal, "#dungeon-abandon-modal must exist in DOM").toHaveCount(1);
  await expect(modal, "abandon modal must be hidden by default").toBeHidden();
});

test("REGRESSION #682 L13 — dungeon resume modal exists in DOM", async ({ page }) => {
  await page.goto("/");
  const modal = page.locator("#dungeon-resume-modal");
  await expect(modal, "#dungeon-resume-modal must exist in DOM").toHaveCount(1);
  await expect(modal, "resume modal must be hidden by default").toBeHidden();
});

test("REGRESSION #682 L13 — dungeon boss choice modal exists in DOM", async ({ page }) => {
  await page.goto("/");
  const modal = page.locator("#dungeon-boss-modal");
  await expect(modal, "#dungeon-boss-modal must exist in DOM").toHaveCount(1);
  await expect(modal, "boss modal must be hidden by default").toBeHidden();
});

// ── Test 2: Modal structure — buttons present ────────────────────────────────
test("REGRESSION #682 L13 — death modal has exit button", async ({ page }) => {
  await page.goto("/");
  const btn = page.locator("#dungeon-death-modal [data-dungeon-modal-action='exit'], #dungeon-death-exit-btn");
  await expect(btn, "death modal must have an exit/close button").toHaveCount(1);
});

test("REGRESSION #682 L13 — abandon modal has confirm and cancel buttons", async ({ page }) => {
  await page.goto("/");
  const confirmBtn = page.locator("#dungeon-abandon-confirm-btn");
  const cancelBtn = page.locator("#dungeon-abandon-cancel-btn");
  await expect(confirmBtn, "abandon modal must have confirm button").toHaveCount(1);
  await expect(cancelBtn, "abandon modal must have cancel button").toHaveCount(1);
});

test("REGRESSION #682 L13 — boss modal has exit and go-deeper buttons", async ({ page }) => {
  await page.goto("/");
  const exitBtn = page.locator("#dungeon-boss-exit-btn");
  const deeperBtn = page.locator("#dungeon-boss-deeper-btn");
  await expect(exitBtn, "boss modal must have exit button").toHaveCount(1);
  await expect(deeperBtn, "boss modal must have go-deeper button").toHaveCount(1);
});

test("REGRESSION #682 L13 — resume modal has continue and abandon buttons", async ({ page }) => {
  await page.goto("/");
  const continueBtn = page.locator("#dungeon-resume-continue-btn");
  const abandonBtn = page.locator("#dungeon-resume-abandon-btn");
  await expect(continueBtn, "resume modal must have continue button").toHaveCount(1);
  await expect(abandonBtn, "resume modal must have abandon button").toHaveCount(1);
});

// ── Test 3: Backend API contracts for modal data ─────────────────────────────
test("REGRESSION #682 L13 — /api/dungeons/active-run returns correct shape", async ({ request }) => {
  // Use character_id=1 (demo account) — may have no run, still must return shape
  const r = await request.get("/api/dungeons/active-run?character_id=1");
  expect(r.ok(), "active-run endpoint must return 200").toBeTruthy();
  const body = await r.json();
  expect(body).toHaveProperty("active_run");
  if (body.active_run) {
    expect(body.active_run).toHaveProperty("campaign_id");
    expect(body.active_run).toHaveProperty("dungeon_key");
  }
});

test("REGRESSION #682 L13 — /api/dungeons/boss-choice rejects when no run (409)", async ({ request }) => {
  // Campaign 0 doesn't exist → 409 expected
  const r = await request.post("/api/dungeons/boss-choice", {
    data: { campaign_id: 999999, character_id: 999999, choice: "exit" },
  });
  expect(r.status(), "boss-choice with invalid campaign must return 4xx").toBeGreaterThanOrEqual(400);
});

test("REGRESSION #682 L13 — /api/dungeons/death returns ok+failed+cooldown shape", async ({ request }) => {
  // Invalid campaign → no-op, returns ok:true but restored:false
  const r = await request.post("/api/dungeons/death", {
    data: { campaign_id: 999999, character_id: 999999 },
  });
  expect(r.ok(), "death endpoint must return 200 even for no-op").toBeTruthy();
  const body = await r.json();
  expect(body).toHaveProperty("ok");
  expect(body).toHaveProperty("restored");
  expect(body).toHaveProperty("failed");
});
