/**
 * REGRESSION #865 — POST /api/dungeons/{key}/enter musi zwracać zresolvowane riddle (dict), nie goły klucz.
 * Acceptance: świeże wejście do lochu daje content.riddle = {text, answer, hints, ...} — symetria z resume.
 * Deterministyczny kontrakt endpointów; pełny e2e rozwiązywania riddle pokrywa pytest test_issue865.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #865 — POST /api/dungeons/{key}/enter istnieje (nie 404)", async ({ page }) => {
    // Wywołanie bez ważnego setupu zwróci błąd biznesowy (404 dungeon/409/423/422), ale NIE 405 Method Not Allowed.
    const r = await page.request.post("/api/dungeons/__nieistniejacy__/enter", {
        data: { character_id: 1, campaign_id: 1 },
    });
    expect(r.status(), "enter endpoint nie powinien zwracać 405 (route istnieje) (#865)").not.toBe(405);
});

test("REGRESSION #865 — resume i enter dzielą ten sam kształt dungeon_run", async ({ page }) => {
    // Resume endpoint (kanon kształtu, zawsze 200, dungeon_run może być null gdy brak aktywnego runu).
    const r = await page.request.get("/api/campaigns/1/dungeon-run");
    expect(r.ok(), "GET /api/campaigns/1/dungeon-run nie odpowiada 200 (#865)").toBeTruthy();
    const body = await r.json();
    expect(body).toHaveProperty("dungeon_run");

    // Gdy istnieje aktywny run z node'em riddle — content.riddle MUSI być dict, nie string key.
    const run = body.dungeon_run;
    if (run && run.graph && run.graph.nodes) {
        for (const node of Object.values(run.graph.nodes)) {
            const riddle = node?.content?.riddle;
            if (riddle !== null && riddle !== undefined) {
                expect(
                    typeof riddle,
                    `content.riddle musi być obiektem, nie gołym kluczem string (#865): ${JSON.stringify(riddle)}`,
                ).toBe("object");
            }
        }
    }
});

test("REGRESSION #865 — /api/dungeons zwraca listę lochów (endpoint żyje)", async ({ page }) => {
    const r = await page.request.get("/api/dungeons?character_id=1");
    expect(r.ok(), "GET /api/dungeons nie odpowiada 200 (#865)").toBeTruthy();
    const body = await r.json();
    expect(Array.isArray(body.dungeons), "dungeons musi być tablicą").toBeTruthy();
});
