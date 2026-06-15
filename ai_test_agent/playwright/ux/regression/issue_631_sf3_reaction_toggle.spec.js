/**
 * REGRESSION #631 (SF3) — reakcje (Unik/Blok) jako toggle „uzbrojony".
 * Acceptance: przyciski reakcji w arkuszu mają linijkę stanu „uzbrojony" (.combat-btn__armed),
 * domyślnie ukrytą; helper renderReactionToggle przełącza stan (klasa .is-armed + odsłonięcie
 * linijki + etykieta „✓"), a po rozładowaniu gaśnie. Akcje zużywające turę armed-linijki NIE mają.
 * Stan czytany z combat snapshot (reaction_declared) — front nic nie liczy sam.
 */
const { test, expect } = require("@playwright/test");

const REACTION_BTNS = ["combat-dodge-btn", "combat-block-btn"]; // ↺ reakcja (toggle)
const ACTION_BTNS = ["combat-spell-btn", "combat-move-btn", "combat-wrestle-btn"]; // ⏳ tura

test("REGRESSION #631 — reakcje maja linijke uzbrojony, domyslnie ukryta", async ({ page }) => {
  await page.goto("/");
  for (const id of REACTION_BTNS) {
    const armed = page.locator(`#combat-action-sheet #${id} .combat-btn__armed`);
    await expect(armed, `#${id} — brak linijki stanu „uzbrojony" (#631 SF3)`).toHaveCount(1);
    await expect(armed, `#${id} — linijka „uzbrojony" musi być domyślnie ukryta (#631)`).toBeHidden();
  }
});

test("REGRESSION #631 — akcje zuzywajace ture NIE maja linijki uzbrojony", async ({ page }) => {
  await page.goto("/");
  for (const id of ACTION_BTNS) {
    await expect(
      page.locator(`#${id} .combat-btn__armed`),
      `#${id} to akcja — nie powinna mieć linijki „uzbrojony" (#631)`
    ).toHaveCount(0);
  }
});

test("REGRESSION #631 — renderReactionToggle uzbraja i rozładowuje stan", async ({ page }) => {
  await page.goto("/");
  // Helper musi być wystawiony na window (kontrakt SF3) — render czyta reaction_declared ze snapshotu.
  await expect
    .poll(() => page.evaluate(() => typeof window.__sfRenderReactionToggle), {
      message: "window.__sfRenderReactionToggle musi istnieć (#631 SF3)",
    })
    .toBe("function");

  const states = await page.evaluate(() => {
    const btn = document.getElementById("combat-dodge-btn");
    const label = document.getElementById("combat-dodge-label");
    const armedEl = btn.querySelector(".combat-btn__armed");
    // uzbrojony (reaction_declared == 'dodge')
    window.__sfRenderReactionToggle(btn, label, true, "Unik");
    const on = { armed: btn.classList.contains("is-armed"), armedVisible: !armedEl.hidden, label: label.textContent };
    // rozładowany (snapshot bez reaction_declared) → gaśnie
    window.__sfRenderReactionToggle(btn, label, false, "Unik");
    const off = { armed: btn.classList.contains("is-armed"), armedVisible: !armedEl.hidden, label: label.textContent };
    return { on, off };
  });

  expect(states.on.armed, "uzbrojony → klasa .is-armed (#631)").toBeTruthy();
  expect(states.on.armedVisible, "uzbrojony → linijka widoczna (#631)").toBeTruthy();
  expect(states.on.label, "uzbrojony → etykieta z ✓ (#631)").toContain("✓");
  expect(states.off.armed, "rozładowany → bez .is-armed (#631)").toBeFalsy();
  expect(states.off.armedVisible, "rozładowany → linijka ukryta (#631)").toBeFalsy();
  expect(states.off.label, "rozładowany → etykieta bazowa bez ✓ (#631)").not.toContain("✓");
});
