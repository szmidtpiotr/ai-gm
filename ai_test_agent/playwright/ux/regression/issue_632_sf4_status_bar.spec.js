/**
 * REGRESSION #632 (SF4) — pasek statusu gracza (trwała warstwa aktywnych kondycji).
 * Acceptance: nad #combat-composer istnieje kontener #combat-player-status, domyślnie ukryty.
 * Helper renderPlayerStatusBar czyta player.conditions[] (snapshot): renderuje chip na każdą
 * kondycję (glif + nazwa PL); dla kondycji stackowalnej (effect_json.stacking_levels.max_level>1)
 * dokłada odznakę poziomu „N/M" z runtime.level (np. „Wyczerpany 2/2"). Brak kondycji → pasek
 * ukryty. Front nic nie liczy — poziom/etykieta pochodzą ze snapshotu/katalogu.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #632 — pasek statusu istnieje i jest domyslnie ukryty", async ({ page }) => {
  await page.goto("/");
  const bar = page.locator("#combat-player-status");
  await expect(bar, "brak kontenera #combat-player-status (#632 SF4)").toHaveCount(1);
  await expect(bar, "pasek statusu musi być domyślnie ukryty poza walką (#632)").toBeHidden();
});

test("REGRESSION #632 — helper renderPlayerStatusBar wystawiony na window", async ({ page }) => {
  await page.goto("/");
  await expect
    .poll(() => page.evaluate(() => typeof window.__sfRenderPlayerStatusBar), {
      message: "window.__sfRenderPlayerStatusBar musi istnieć (#632 SF4)",
    })
    .toBe("function");
});

test("REGRESSION #632 — exhausted x2 pokazuje chip „Wyczerpany 2/2”", async ({ page }) => {
  await page.goto("/");
  const res = await page.evaluate(() => {
    const player = {
      type: "player",
      conditions: [
        {
          key: "exhausted",
          label: "Wyczerpany",
          runtime: { level: 2 },
          effect_json: JSON.stringify({
            effects: [{ type: "stacking_levels", max_level: 2 }],
          }),
        },
      ],
    };
    window.__sfRenderPlayerStatusBar(player);
    const bar = document.getElementById("combat-player-status");
    const chip = bar.querySelector(".combat-status-chip");
    return {
      barHidden: bar.hidden,
      chipCount: bar.querySelectorAll(".combat-status-chip").length,
      text: chip ? chip.textContent : "",
      hasLevel: !!(chip && chip.querySelector(".combat-status-chip__level")),
    };
  });
  expect(res.barHidden, "pasek widoczny gdy są kondycje (#632)").toBeFalsy();
  expect(res.chipCount, "dokładnie jeden chip dla jednej kondycji (#632)").toBe(1);
  expect(res.text, "chip pokazuje nazwę PL „Wyczerpany” (#632)").toContain("Wyczerpany");
  expect(res.text, "chip pokazuje poziom stackowania „2/2” (#632)").toContain("2/2");
  expect(res.hasLevel, "stackowalna kondycja → odznaka poziomu (#632)").toBeTruthy();
});

test("REGRESSION #632 — kondycja niestackowalna bez odznaki poziomu", async ({ page }) => {
  await page.goto("/");
  const res = await page.evaluate(() => {
    const player = {
      type: "player",
      conditions: [
        {
          key: "on_fire",
          label: "Podpalony",
          runtime: { level: 1 },
          effect_json: JSON.stringify({ effects: [{ type: "dot", value: "2d6" }] }),
        },
      ],
    };
    window.__sfRenderPlayerStatusBar(player);
    const bar = document.getElementById("combat-player-status");
    const chip = bar.querySelector(".combat-status-chip");
    return {
      text: chip ? chip.textContent : "",
      hasLevel: !!(chip && chip.querySelector(".combat-status-chip__level")),
    };
  });
  expect(res.text, "chip pokazuje nazwę PL „Podpalony” (#632)").toContain("Podpalony");
  expect(res.hasLevel, "niestackowalna kondycja → BRAK odznaki poziomu (#632)").toBeFalsy();
});

test("REGRESSION #632 — brak kondycji ukrywa pasek", async ({ page }) => {
  await page.goto("/");
  const hidden = await page.evaluate(() => {
    window.__sfRenderPlayerStatusBar({ type: "player", conditions: [] });
    return document.getElementById("combat-player-status").hidden;
  });
  expect(hidden, "brak kondycji → pasek ukryty (#632)").toBeTruthy();
});
