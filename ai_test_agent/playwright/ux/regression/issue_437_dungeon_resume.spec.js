/**
 * REGRESSION #437 (E22) — Resume niedokończonego runu lochu.
 * Acceptance: GET /api/dungeons/active-run zwraca {active_run: null|{campaign_id,...}}.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #437 — active-run zwraca null gdy brak aktywnego runu", async ({ page }) => {
    // character_id=0 na pewno nie ma aktywnego runu
    const r = await page.request.get("/api/dungeons/active-run?character_id=0");
    expect(r.status(), "Endpoint active-run powinien istnieć (nie 404) (#437)").not.toBe(404);
    expect(r.ok(), "Endpoint active-run powinien zwracać 200 (#437)").toBeTruthy();
    const body = await r.json();
    expect("active_run" in body, "Odpowiedź musi zawierać klucz active_run (#437)").toBeTruthy();
    expect(body.active_run, "Dla nieistniejącego bohatera active_run powinno być null (#437)").toBeNull();
});

test("REGRESSION #437 — active-run endpoint ma prawidłowy kształt odpowiedzi", async ({ page }) => {
    // Sprawdź kształt endpointu dla zwykłego bohatera
    const r = await page.request.get("/api/dungeons/active-run?character_id=1");
    expect(r.status()).not.toBe(404);

    if (r.ok()) {
        const body = await r.json();
        expect(typeof body).toBe("object");
        expect("active_run" in body, "Odpowiedź musi zawierać klucz active_run (#437)").toBeTruthy();

        if (body.active_run !== null) {
            // Jeśli jest aktywny run — sprawdź że ma wymagane pola
            expect("campaign_id" in body.active_run, "active_run musi zawierać campaign_id (#437)").toBeTruthy();
            expect("dungeon_key" in body.active_run, "active_run musi zawierać dungeon_key (#437)").toBeTruthy();
            expect("current_room" in body.active_run, "active_run musi zawierać current_room (#437)").toBeTruthy();
        }
    }
});
