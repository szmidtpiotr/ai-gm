/**
 * REGRESSION #951 (SWIPE) — Swipe lewo/prawo zmienia zakładki karty postaci.
 * Acceptance: initSheetTabSwipe używa dynamicznego odczytu widocznych .sheet-tab
 * (nie hardkodowanej listy z phantomowym 'skills' i bez 'spells').
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #951 — game.js initSheetTabSwipe używa dynamicznych zakładek, nie TAB_ORDER", async ({ page }) => {
    const resp = await page.request.get("/front/js/screens/game.js");
    expect(resp.ok(), "game.js niedostępne (#951)").toBeTruthy();

    const js = await resp.text();
    const fnStart = js.indexOf("function initSheetTabSwipe");
    expect(fnStart, "initSheetTabSwipe nie istnieje w game.js").toBeGreaterThan(-1);

    const snippet = js.slice(fnStart, fnStart + 1400);

    expect(snippet, "Phantom tab 'skills' nadal w initSheetTabSwipe (#951)")
        .not.toContain("'skills'");

    expect(snippet, "Statyczny TAB_ORDER = [ nadal w initSheetTabSwipe (#951)")
        .not.toContain("TAB_ORDER = [");

    const hasDynamic =
        snippet.includes("querySelectorAll('.sheet-tab')") ||
        snippet.includes('querySelectorAll(".sheet-tab")');
    expect(hasDynamic, "Brak dynamicznego querySelectorAll('.sheet-tab') (#951)").toBeTruthy();
});

test("REGRESSION #951 — zakładki HTML karty postaci zawierają spells (nie skills)", async ({ page }) => {
    const resp = await page.request.get("/front/index.html");
    expect(resp.ok(), "index.html niedostępne (#951)").toBeTruthy();

    const html = await resp.text();
    expect(html, "Brak zakładki spells w HTML karty postaci").toContain('data-tab="spells"');
    expect(html, "Phantom tab skills w HTML karty postaci").not.toContain('data-tab="skills"');
});
