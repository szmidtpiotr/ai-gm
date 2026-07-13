/**
 * REGRESSION #1353 (WALKA-T3) — ActionSheet czarów: data-fix rdzen_shield + opisy end-to-end.
 * Acceptance: katalog /spells serwuje rdzen_shield jako spell_type='defense' (sekcja Ochronne)
 * oraz description (≥30 zn.) dla czarów bojowych — front pokazuje opis, nie surowy enum.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1353 — rdzen_shield jest defense z pełnym opisem", async ({ page }) => {
  const r = await page.request.get("/api/spells");
  expect(r.ok(), "GET /api/spells nie odpowiada 200 (#1353)").toBeTruthy();
  const body = await r.json();
  const spells = body.spells || [];
  expect(spells.length, "katalog czarów pusty").toBeGreaterThan(0);

  const shield = spells.find((s) => s.key === "rdzen_shield");
  expect(shield, "brak rdzen_shield w katalogu").toBeTruthy();
  // data-fix: obronny czar w sekcji Ochronne, nie Atakujące.
  expect(shield.spell_type, "rdzen_shield nie jest 'defense'").toBe("defense");
  // opis rozpisany (≥30 zn.) — front nie musi już spadać na surowy enum.
  expect((shield.description || "").length, "opis rdzen_shield za krótki").toBeGreaterThanOrEqual(30);
});

test("REGRESSION #1353 — spell_type z zamkniętego słownika (bez surowych dziur)", async ({ page }) => {
  const KNOWN = new Set([
    "attack", "attack_aoe", "heal", "defense", "effect",
    "effect_aoe", "narrative", "reaction", "summon",
  ]);
  const r = await page.request.get("/api/spells");
  const body = await r.json();
  for (const s of body.spells || []) {
    expect(KNOWN.has(s.spell_type), `nieznany spell_type '${s.spell_type}' (${s.key})`).toBeTruthy();
  }
});
