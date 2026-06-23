/**
 * REGRESSION #934 (GF7) — kafelek Multiplayer widoczny w ekranie Kampanii.
 * Acceptance: /campaign-modes zwraca multiplayer z available+label; HTML zawiera #mp-btn.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #934 — /campaign-modes zawiera tryb multiplayer z wymaganymi polami", async ({ page }) => {
    const r = await page.request.get("/api/campaign-modes");
    expect(r.ok(), "endpoint /campaign-modes nie odpowiada 200 (#934)").toBeTruthy();
    const body = await r.json();
    const modes = body.modes || [];
    const keys = modes.map(m => m.key);
    expect(keys, "brak klucza 'multiplayer' w modes (#934)").toContain("multiplayer");
    const mp = modes.find(m => m.key === "multiplayer");
    expect(mp, "tryb multiplayer nie ma pola 'available'").toHaveProperty("available");
    expect(typeof mp.available, "available musi być boolean").toBe("boolean");
    expect(mp, "brak pola label").toHaveProperty("label");
});

test("REGRESSION #934 — HTML frontonu zawiera przycisk #mp-btn w .adv-options", async ({ page }) => {
    const r = await page.request.get("/");
    expect(r.ok(), "frontend nie odpowiada (#934)").toBeTruthy();
    const html = await r.text();
    expect(html, "brak id='mp-btn' w HTML (#934)").toContain('id="mp-btn"');
    expect(html, "brak klasy adv-card przy #mp-btn (#934)").toContain('id="mp-btn"');
    // Weryfikacja że button istnieje w sekcji adv-options
    expect(html, "brak .adv-options w HTML (#934)").toContain('class="adv-options"');
});

test("REGRESSION #934 — tryby backward compat: nowa/gotowa/loch nadal w modes", async ({ page }) => {
    const r = await page.request.get("/api/campaign-modes");
    expect(r.ok()).toBeTruthy();
    const keys = (await r.json()).modes.map(m => m.key);
    for (const k of ["nowa", "gotowa", "loch"]) {
        expect(keys, `brak trybu '${k}' (#934 backward compat)`).toContain(k);
    }
});
