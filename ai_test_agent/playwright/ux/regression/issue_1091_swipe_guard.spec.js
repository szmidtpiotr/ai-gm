/**
 * REGRESSION #1091 (MOBILE-SWIPE) — Scroll ekwipunku nie zamyka modala na mobile.
 * Acceptance: initPanelSwipeDown ma guard scrollTop; .sheet-panel__content ma overscroll-behavior:contain.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1091 — CSS: .sheet-panel__content ma overscroll-behavior:contain", async ({ page }) => {
    const r = await page.request.get("/css/styles.css");
    expect(r.ok(), "styles.css nie odpowiada 200 (#1091)").toBeTruthy();
    const body = await r.text();
    const idx = body.indexOf(".sheet-panel__content");
    expect(idx, ".sheet-panel__content nie znaleziono w CSS (#1091)").toBeGreaterThan(-1);
    const block = body.slice(idx, idx + 300);
    expect(block, ".sheet-panel__content brak overscroll-behavior:contain (#1091)").toContain("overscroll-behavior");
});

test("REGRESSION #1091 — JS: initPanelSwipeDown ma guard scrollTop", async ({ page }) => {
    const r = await page.request.get("/js/screens/game.js");
    expect(r.ok(), "game.js nie odpowiada 200 (#1091)").toBeTruthy();
    const body = await r.text();
    const fnIdx = body.indexOf("function initPanelSwipeDown");
    expect(fnIdx, "initPanelSwipeDown nie znaleziono w game.js (#1091)").toBeGreaterThan(-1);
    const fn = body.slice(fnIdx, fnIdx + 1500);
    expect(fn, "initPanelSwipeDown brak scrollTop guard (#1091)").toContain("scrollTop");
    expect(fn, "initPanelSwipeDown brak closeFn() (#1091)").toContain("closeFn()");
});
