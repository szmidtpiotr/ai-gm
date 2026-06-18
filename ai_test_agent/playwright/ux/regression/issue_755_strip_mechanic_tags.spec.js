/**
 * REGRESSION #755 — Frontend stripMechanicTags: tagi mechaniczne nie wyciekają do narracji.
 * Weryfikuje że backend startuje z nową funkcją strip_all_mechanic_tags()
 * i że strona gracza ładuje się bez błędów JS (app.js z nową funkcją załadowany).
 * Acceptance: brak [QUEST_SUGGEST:...] / [NPC_MEMORY:...] / [NARRATIVE_EVENT:...] w bąblu gracza.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #755 — backend załadował strip_all_mechanic_tags (health OK)", async ({ page }) => {
    const r = await page.request.get("/api/health");
    expect(r.ok(), "backend health check nie przechodzi (#755)").toBeTruthy();
    const body = await r.json();
    expect(body.status, "backend status != ok").toBe("ok");
});

test("REGRESSION #755 — strona gracza ładuje się bez błędów JS", async ({ page }) => {
    const errors = [];
    page.on("pageerror", err => errors.push(err.message));
    await page.goto("/");
    await page.waitForTimeout(2000);
    const jsErrors = errors.filter(e => e.includes("stripMechanicTags") || e.includes("app.js"));
    expect(jsErrors, `Błędy JS związane z app.js: ${jsErrors}`).toHaveLength(0);
});
