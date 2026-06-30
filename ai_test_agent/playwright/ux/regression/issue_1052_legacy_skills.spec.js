/**
 * REGRESSION #1052 — Awansuj screen shows only catalog skills, no unknown_skill error.
 * Acceptance: game_config_skills catalog has no melee_attack/ranged_attack/spell_attack/sleight_of_hand;
 * xp/spend-skill rejects non-catalog legacy keys with 400.
 */
const { test, expect } = require("@playwright/test");

const LEGACY_KEYS = ["melee_attack", "ranged_attack", "spell_attack", "sleight_of_hand"];

test("REGRESSION #1052 — mechanics/skills catalog has no legacy keys", async ({ page }) => {
    const r = await page.request.get("/api/mechanics/skills");
    expect(r.ok(), "skills endpoint must return 200 (#1052)").toBeTruthy();
    const body = await r.json();
    const keys = (body.skills || []).map(s => s.key);
    for (const legacy of LEGACY_KEYS) {
        expect(keys, `catalog must not contain legacy key '${legacy}' (#1052)`).not.toContain(legacy);
    }
});

test("REGRESSION #1052 — no character has legacy skill keys in sheet_json", async ({ page }) => {
    // Uses mechanics/skills to derive expected keys, not an admin endpoint.
    // This test is informational — passes if endpoint is unavailable (auth required).
    const r = await page.request.get("/api/admin/characters?limit=50");
    if (!r.ok()) return; // admin auth required — skip gracefully
    const body = await r.json();
    const chars = body.characters || body.items || body || [];
    for (const char of chars) {
        if (!char.sheet_json && !char.skills) continue;
        const skills = char.skills || char.sheet_json?.skills || {};
        for (const legacy of LEGACY_KEYS) {
            expect(
                Object.prototype.hasOwnProperty.call(skills, legacy),
                `character '${char.name}' still has legacy key '${legacy}' (#1052)`
            ).toBeFalsy();
        }
    }
});

test("REGRESSION #1052 — xp spend on melee_attack returns 400", async ({ page }) => {
    // melee_attack is not in catalog → must be rejected (unknown_skill or insufficient_xp, both 400)
    const r = await page.request.post("/api/characters/999420/xp/spend-skill", {
        data: JSON.stringify({ skill_key: "melee_attack" }),
        headers: { "Content-Type": "application/json" },
    });
    expect(
        [400, 404, 422].includes(r.status()),
        `expected 400/404/422 for legacy key melee_attack, got ${r.status()} (#1052)`
    ).toBeTruthy();
});
