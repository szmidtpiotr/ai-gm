/**
 * REGRESSION #747 — kreator postaci, budżet umiejętności liczony NETTO (Opcja A).
 * Obniżenie wylosowanego skilla (−) zwraca punkt budżetu, zamiast go zużywać jak podniesienie.
 * Acceptance: podniesienie jednego skilla (+1) i obniżenie innego (−1) daje budżet netto 0,
 *             a nie 2 (stary błąd z Math.abs). Gate _canAdjSkill używa tej samej formuły netto.
 */
const { test, expect } = require("@playwright/test");

// app.js to klasyczny <script> — funkcje (declarations) i top-level `let` są dostępne
// po gołej nazwie w page.evaluate (wspólny global lexical scope). Testujemy czyste funkcje
// budżetu bezpośrednio, bez przechodzenia całego kreatora i bez logowania.

test("REGRESSION #747 — budżet skilli liczony netto (raise+lower = 0, nie 2)", async ({ page }) => {
    await page.goto("/");
    // poczekaj aż app.js się załaduje i zarejestruje funkcje budżetu
    await page.waitForFunction(
        () => typeof _skillBudgetUsed === "function" && typeof _canAdjSkill === "function",
        null,
        { timeout: 15000 }
    );

    const r = await page.evaluate(() => {
        // dwa wylosowane skille na poziomie 1
        wizardSkillSnapshot = { melee_attack: 1, awareness: 1 };
        wizardSkillLevels = {};
        const baseline = _skillBudgetUsed();           // 0 — brak zmian

        wizardSkillLevels = { melee_attack: 2 };        // podniesienie +1
        const afterRaise = _skillBudgetUsed();          // 1

        wizardSkillLevels = { melee_attack: 2, awareness: 0 }; // dodatkowe obniżenie −1
        const afterRaiseAndLower = _skillBudgetUsed();  // NETTO: 1 + (-1) = 0 (stary błąd: 2)

        // pojedyncze obniżenie zwraca punkt → budżet ≤ 0
        wizardSkillLevels = { awareness: 0 };
        const afterLowerOnly = _skillBudgetUsed();      // -1 (netto)

        return { baseline, afterRaise, afterRaiseAndLower, afterLowerOnly };
    });

    expect(r.baseline, "brak zmian = 0 punktów (#747)").toBe(0);
    expect(r.afterRaise, "jedno podniesienie = 1 punkt (#747)").toBe(1);
    expect(r.afterRaiseAndLower, "raise+lower netto = 0, nie 2 (#747)").toBe(0);
    expect(r.afterLowerOnly, "samo obniżenie zwraca punkt (netto ≤ 0) (#747)").toBeLessThanOrEqual(0);
});

test("REGRESSION #747 — gate _canAdjSkill zgodny z budżetem netto", async ({ page }) => {
    await page.goto("/");
    await page.waitForFunction(
        () => typeof _skillBudgetUsed === "function" && typeof _canAdjSkill === "function",
        null,
        { timeout: 15000 }
    );

    const r = await page.evaluate(() => {
        // cztery wylosowane skille na poziomie 1 → budżet 4
        wizardSkillSnapshot = { melee_attack: 1, awareness: 1, lore: 1, survival: 1 };
        // wszystkie podniesione do 2 → netto = 4 (pełny budżet)
        wizardSkillLevels = { melee_attack: 2, awareness: 2, lore: 2, survival: 2 };
        const usedAtMax = _skillBudgetUsed();           // 4
        const canRaiseAtMax = _canAdjSkill("melee_attack", 1); // false: 2→? i tak max 2, ale gate

        // obniżenie jednego zwalnia punkt → znów można podnieść inny
        wizardSkillLevels = { melee_attack: 1, awareness: 2, lore: 2, survival: 2 }; // netto 3
        const usedAfterLower = _skillBudgetUsed();      // 3
        const canRaiseAfterLower = _canAdjSkill("melee_attack", 1); // true: 1→2, netto 4 ≤ 4

        return { usedAtMax, canRaiseAtMax, usedAfterLower, canRaiseAfterLower };
    });

    expect(r.usedAtMax, "cztery podniesienia = 4 (#747)").toBe(4);
    expect(r.usedAfterLower, "obniżenie jednego = netto 3 (#747)").toBe(3);
    expect(r.canRaiseAfterLower, "po obniżeniu można znów podnieść inny skill (#747)").toBeTruthy();
});
