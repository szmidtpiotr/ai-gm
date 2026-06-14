/**
 * REGRESSION #585 (S5) — Seed 18 skilli kategorii A (czyste testy) w katalogu skilli.
 * Acceptance: publiczny katalog /api/mechanics/skills zwraca nowe skille z poprawnym
 * linked_stat (riding/DEX, charm/CHA, tracking/WIS, pickpocket/DEX, swim/STR...),
 * a istniejące skille rdzenne pozostają nietknięte.
 */
const { test, expect } = require("@playwright/test");

const EXPECTED = {
  riding: "DEX",
  endurance: "CON",
  swim: "STR",
  climb: "STR",
  charm: "CHA",
  gossip: "CHA",
  bribe: "CHA",
  trade_craft: "INT",
  language: "INT",
  theology: "WIS",
  nature: "WIS",
  alchemy: "INT",
  magic_sense: "WIS",
  tracking: "WIS",
  sailing: "INT",
  pickpocket: "DEX",
  disguise: "CHA",
  torture: "CHA",
};

test("REGRESSION #585 — katalog skilli zawiera 18 nowych skilli kategorii A", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/skills");
  expect(r.ok(), "/api/mechanics/skills nie odpowiada 200 (#585)").toBeTruthy();

  const body = await r.json();
  const skills = body.skills || [];
  const byKey = Object.fromEntries(skills.map((s) => [s.key, s.linked_stat]));

  // Wszystkie nowe skille obecne z poprawnym linked_stat
  for (const [key, stat] of Object.entries(EXPECTED)) {
    expect(byKey[key], `brak skilla ${key} w katalogu (#585)`).toBe(stat);
  }

  // Istniejące skille rdzenne nietknięte (brak regresji)
  expect(byKey.stealth).toBe("DEX");
  expect(byKey.persuasion).toBe("CHA");

  // Katalog urósł do ~35 skilli (17 rdzennych + 18 nowych)
  expect(skills.length, "katalog skilli powinien mieć >= 35 wierszy").toBeGreaterThanOrEqual(35);
});
