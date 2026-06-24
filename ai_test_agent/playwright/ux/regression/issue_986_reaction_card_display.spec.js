/**
 * REGRESSION #986 (SF10) — karta reakcji nie wyświetla "? vs ?" zamiast wyników rzutów.
 * Acceptance: combat_turns reaction events mają poprawne narrative JSON z polami
 * dodge_total/attack_roll (dla dodge) lub damage (dla take) — brak pól wyświetla "? vs ?".
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #986 — reaction narrative has required fields for display", async ({ page }) => {
    // Get recent reaction events from the API
    const r = await page.request.get("/api/campaigns/999964/combat/turns");
    // If no active combat, fall back to all-turns endpoint
    const allR = await page.request.get("/api/campaigns/999964/combat/history?limit=50");

    // At least one of the endpoints must work
    const ok = r.ok() || allR.ok();
    expect(ok, "combat turns endpoint must be reachable (#986)").toBeTruthy();

    // Check that any reaction events have correct narrative structure
    let rows = [];
    if (r.ok()) {
        try {
            const data = await r.json();
            rows = Array.isArray(data) ? data : (data.turns || []);
        } catch (_) { rows = []; }
    }
    if (!rows.length && allR.ok()) {
        try {
            const data = await allR.json();
            rows = Array.isArray(data) ? data : (data.turns || data.history || []);
        } catch (_) { rows = []; }
    }

    const reactionRows = rows.filter(row => row.event_type === "reaction");
    for (const row of reactionRows) {
        let meta = {};
        try { meta = JSON.parse(row.narrative || "{}"); } catch (_) {}

        const rxType = meta.reaction || "";

        if (rxType === "take") {
            // take: must have damage, must NOT rely on dodge_total/attack_roll
            expect(
                meta.damage != null,
                `take reaction row ${row.id} must have 'damage' field (#986)`
            ).toBeTruthy();
        } else if (rxType === "dodge") {
            // dodge: must have both values for display
            expect(
                meta.dodge_total != null,
                `dodge reaction row ${row.id} must have 'dodge_total' — otherwise shows '?' (#986)`
            ).toBeTruthy();
            expect(
                meta.attack_roll != null,
                `dodge reaction row ${row.id} must have 'attack_roll' — otherwise shows '?' (#986)`
            ).toBeTruthy();
        } else if (rxType === "shield_block") {
            // block: must have both values for display
            expect(
                meta.block_total != null,
                `shield_block reaction row ${row.id} must have 'block_total' — otherwise shows '?' (#986)`
            ).toBeTruthy();
            expect(
                meta.dc != null,
                `shield_block reaction row ${row.id} must have 'dc' — otherwise shows '?' (#986)`
            ).toBeTruthy();
        }
    }
});
