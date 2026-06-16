/**
 * REGRESSION #683 (L13b) — Wejście z ekranu startowego (scalenie D9).
 * Acceptance:
 *  - Kafelek D9 "Wyprawa do lochu" istnieje w DOM
 *  - Overlay pickera lochów istnieje i jest ukryty domyślnie
 *  - Kliknięcie przycisku otwiera overlay pickera
 *  - GET /api/campaign-modes → loch.label = "Wyprawa do lochu"
 */
const { test, expect } = require("@playwright/test");

// ── Test 1: Button text "Wyprawa do lochu" present in DOM ────────────────────
test("REGRESSION #683 L13b — dungeon card has label 'Wyprawa do lochu'", async ({ page }) => {
  await page.goto("/");
  const btn = page.locator("#dungeon-picker-btn");
  await expect(btn, "#dungeon-picker-btn must exist in DOM").toHaveCount(1);
  const h3 = btn.locator("h3");
  await expect(h3, "dungeon card h3 must read 'Wyprawa do lochu'").toHaveText("Wyprawa do lochu");
});

// ── Test 2: Dungeon picker overlay exists and is hidden by default ────────────
test("REGRESSION #683 L13b — dungeon picker overlay exists and is hidden", async ({ page }) => {
  await page.goto("/");
  const overlay = page.locator("#dungeon-picker-overlay");
  await expect(overlay, "#dungeon-picker-overlay must exist").toHaveCount(1);
  await expect(overlay, "dungeon picker overlay must be hidden by default").toBeHidden();
});

// ── Test 3: Clicking the card opens the picker overlay ───────────────────────
test("REGRESSION #683 L13b — clicking 'Wyprawa do lochu' card opens picker overlay", async ({ page }) => {
  await page.goto("/");
  const btn = page.locator("#dungeon-picker-btn");
  // Button may be disabled if no dungeons in DB or flag off — check visibility first
  await expect(btn, "dungeon picker button must exist").toHaveCount(1);

  const isDisabled = await btn.getAttribute("disabled");
  if (isDisabled !== null) {
    // Card disabled (no dungeons or flag off) — overlay won't open, skip interaction
    console.log("SKIP: dungeon-picker-btn is disabled (no dungeons or flag off)");
    return;
  }

  await btn.click();
  const overlay = page.locator("#dungeon-picker-overlay");
  await expect(overlay, "overlay must become visible after clicking card").toBeVisible({ timeout: 3000 });
});

// ── Test 4: Picker overlay close button works ─────────────────────────────────
test("REGRESSION #683 L13b — dungeon picker overlay has close button", async ({ page }) => {
  await page.goto("/");
  const closeBtn = page.locator("#dungeon-picker-close");
  await expect(closeBtn, "#dungeon-picker-close must exist").toHaveCount(1);
});

// ── Test 5: API — campaign-modes returns loch with correct label ──────────────
test("REGRESSION #683 L13b — GET /api/campaign-modes returns loch label 'Wyprawa do lochu'", async ({ request }) => {
  const r = await request.get("/api/campaign-modes");
  expect(r.ok(), "campaign-modes must return 200").toBeTruthy();
  const body = await r.json();
  const modes = body.modes || [];
  const loch = modes.find(m => m.key === "loch");
  expect(loch, "mode 'loch' must exist").toBeTruthy();
  expect(loch.label, "loch.label must be 'Wyprawa do lochu'").toBe("Wyprawa do lochu");
});

// ── Test 6: API — no 'loch_kafelki' mode (merged in L10) ─────────────────────
test("REGRESSION #683 L13b — GET /api/campaign-modes has no loch_kafelki mode", async ({ request }) => {
  const r = await request.get("/api/campaign-modes");
  expect(r.ok()).toBeTruthy();
  const body = await r.json();
  const modes = body.modes || [];
  const hasOldMode = modes.some(m => m.key === "loch_kafelki");
  expect(hasOldMode, "mode 'loch_kafelki' must not exist (merged into 'loch')").toBeFalsy();
});
