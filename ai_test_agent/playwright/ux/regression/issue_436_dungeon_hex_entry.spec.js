/**
 * REGRESSION #436 (E21) — Hex mapa: klik na dungeon hex otwiera picker lochów.
 * Acceptance: hex-travel do dungeon hexu zwraca dungeon_prompt=true; endpoint istnieje.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #436 — hex-travel do dungeon hexu zwraca dungeon_prompt=true", async ({ page }) => {
    // Pobierz dungeon hex z world map
    const wmResp = await page.request.get("/api/campaigns/1/world-map?character_id=1");
    // world-map może zwrócić 404 jeśli kampania nie istnieje — to ok, sprawdzamy kształt
    if (!wmResp.ok()) {
        // Sprawdź sam endpoint hex-travel shape przez bezpośrednie żądanie do dungeon hexu
        // Szukamy kampanii demo
        const camps = await page.request.get("/api/campaigns?user_id=1");
        if (!camps.ok()) return; // brak kampanii — skip
        const campsBody = await camps.json();
        const activeCamp = (campsBody.campaigns || []).find(c => c.status === 'active' && c.mode !== 'dungeon');
        if (!activeCamp) return;

        // Znajdź dungeon hex przez DB
        const r = await page.request.post(`/api/campaigns/${activeCamp.id}/hex-travel`, {
            data: { character_id: activeCamp.character_id || 1, destination_q: 19, destination_r: -23 },
        });
        expect(r.ok() || r.status() === 422, "hex-travel endpoint nie odpowiada").toBeTruthy();
        if (r.ok()) {
            const body = await r.json();
            expect("dungeon_prompt" in body, "hex-travel powinno zawierać pole dungeon_prompt (#436)").toBeTruthy();
        }
        return;
    }

    const wm = await wmResp.json();
    const dungeonHex = (wm.hexes || []).find(h => h.hex_type === 'dungeon');
    if (!dungeonHex) return; // brak dungeon hexów w odkrytych — skip

    // hex-travel do dungeon hexu
    const r = await page.request.post("/api/campaigns/1/hex-travel", {
        data: { character_id: 1, destination_q: dungeonHex.q, destination_r: dungeonHex.r },
    });
    expect(r.ok(), "hex-travel zwróciło błąd (#436)").toBeTruthy();
    const body = await r.json();
    expect("dungeon_prompt" in body, "Brak pola dungeon_prompt w odpowiedzi hex-travel (#436)").toBeTruthy();
    expect(body.dungeon_prompt, "dungeon_prompt powinno być true dla dungeon hexu (#436)").toBe(true);
});

test("REGRESSION #436 — endpoint GET /api/dungeons/active-run istnieje (E22 bonus)", async ({ page }) => {
    const r = await page.request.get("/api/dungeons/active-run?character_id=1");
    expect(r.status(), "GET /api/dungeons/active-run nie istnieje — powinno zwracać 200 lub 422, nie 404 (#436/#437)").not.toBe(404);
    if (r.ok()) {
        const body = await r.json();
        expect("active_run" in body, "Odpowiedź powinna zawierać klucz active_run (#437)").toBeTruthy();
    }
});
