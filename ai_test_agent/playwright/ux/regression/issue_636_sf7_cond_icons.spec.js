/**
 * REGRESSION #636 (SF7) — ikony 8 kondycji FAZY S w COND_BADGE_MAP.
 * Acceptance:
 *  - COND_BADGE_MAP zawiera 8 kluczy FAZY S z własnym glifem (nie generyczne „•").
 *  - Klucze = kanoniczne klucze katalogu game_config_conditions (on_fire, exhausted,
 *    hidden, rage, blessed, hasted, hemorrhage, inspired).
 * Kontrakt JS (deterministyczny, bez LLM) — czysta kosmetyka, front NIC nie liczy.
 */
const { test, expect } = require("@playwright/test");

// Mapa glif → klucz wg SF7 (game_mechanics.md CZĘŚĆ AI).
const EXPECTED = {
  on_fire: "🔥",
  exhausted: "😓",
  hidden: "🌫",
  rage: "😤",
  blessed: "✨",
  hasted: "⚡",
  hemorrhage: "🩸",
  inspired: "🌟",
};

// Front gracza ładuje app.js jako zwykły <script>; mapę wystawiamy na window do testu kontraktu.
async function loadPlayerApp(page) {
  await page.goto("/");
  await page.waitForFunction(() => typeof window.COND_BADGE_MAP === "object" && window.COND_BADGE_MAP !== null, null, {
    timeout: 15000,
  });
}

test("REGRESSION #636 — 8 kondycji FAZY S mają własny glif w COND_BADGE_MAP", async ({ page }) => {
  await loadPlayerApp(page);

  for (const [key, glyph] of Object.entries(EXPECTED)) {
    const info = await page.evaluate((k) => window.COND_BADGE_MAP[k], key);
    expect(info, `klucz „${key}" istnieje w COND_BADGE_MAP`).toBeTruthy();
    expect(info.glyph, `glif kondycji „${key}"`).toBe(glyph);
    // nie może zostać generyczna kropka
    expect(info.glyph, `kondycja „${key}" nie jest generyczna •`).not.toBe("•");
  }
});

test("REGRESSION #636 — app.js zawiera 8 kluczy SF7 w źródle", async ({ page }) => {
  const src = await page.request.get("/js/app.js");
  expect(src.ok(), "app.js dostępny").toBeTruthy();
  const body = await src.text();
  for (const key of Object.keys(EXPECTED)) {
    expect(body.includes(`${key}:`), `app.js definiuje klucz „${key}" w mapie`).toBeTruthy();
  }
  expect(body.includes("window.COND_BADGE_MAP"), "mapa wystawiona na window dla testu").toBeTruthy();
});
