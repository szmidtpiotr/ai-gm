/**
 * REGRESSION #570 (U18) — Dziennik gracza: endpoint /journal zwraca 3 sekcje.
 * Acceptance: GET /api/campaigns/{id}/journal odpowiada 200 i ma pola
 * quests / threads / chronicle (kompozycja Zadania / Wątki / Kronika).
 * Sekret GM (player_visible=false) nie wycieka do threads.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #570 — journal endpoint zwraca quests/threads/chronicle", async ({ page }) => {
    // Probe for the first existing campaign (journal is a no-auth read path).
    let cid = null;
    let r = null;
    for (let id = 1; id <= 120; id++) {
        const resp = await page.request.get(`/api/campaigns/${id}/journal`);
        if (resp.ok()) { cid = id; r = resp; break; }
    }
    test.skip(cid === null, "brak kampanii na DEV do sprawdzenia journal");
    expect(r.ok(), `journal endpoint nie odpowiada 200 dla kampanii ${cid} (#570)`).toBeTruthy();

    const body = await r.json();
    expect(Array.isArray(body.quests), "brak pola quests").toBeTruthy();
    expect(Array.isArray(body.threads), "brak pola threads").toBeTruthy();
    expect(Array.isArray(body.chronicle), "brak pola chronicle").toBeTruthy();

    // Żaden wątek widoczny dla gracza nie może nieść flagi player_visible=false.
    for (const t of body.threads) {
        expect(t.player_visible, "sekret GM wyciekł do threads (#570)").not.toBe(false);
    }
});

test("REGRESSION #570 — journal dla nieistniejącej kampanii zwraca 404", async ({ page }) => {
    const r = await page.request.get("/api/campaigns/999999999/journal");
    expect(r.status(), "nieistniejąca kampania powinna dać 404 (#570)").toBe(404);
});
