/**
 * REGRESSION #649 (B6a) — atak czarem nie zawiesza tury wroga i animuje kość.
 * Bug był control-flow w JS: handleCombatSpellAttack resetowało combatBusy tylko w catch,
 * więc po udanym czarze flaga zostawała true i watcher tury wroga (!combatBusy) nie odpalał
 * (tura wisi do F5). Brakowało też animacji kości (playCombatDiceRoll).
 * Acceptance: handleCombatSpellAttack ma blok `finally` zerujący combatBusy + woła
 * playCombatDiceRoll; serwowany app.js jest świeży (bump ?v=).
 */
const { test, expect } = require("@playwright/test");

// Wytnij ciało funkcji handleCombatSpellAttack ze źródła app.js.
function extractFn(src, name) {
  const start = src.indexOf(`async function ${name}(`);
  if (start === -1) return null;
  // Znajdź pierwszą '{' po nagłówku i dopasuj nawiasy klamrowe.
  let i = src.indexOf("{", start);
  if (i === -1) return null;
  let depth = 0;
  for (let j = i; j < src.length; j++) {
    const c = src[j];
    if (c === "{") depth++;
    else if (c === "}") {
      depth--;
      if (depth === 0) return src.slice(start, j + 1);
    }
  }
  return null;
}

test("REGRESSION #649 — handleCombatSpellAttack ma finally(reset combatBusy) + animację kości", async ({ page }) => {
  const r = await page.request.get("/js/app.js");
  expect(r.ok(), "app.js nie serwuje się (200)").toBeTruthy();
  const src = await r.text();

  const fn = extractFn(src, "handleCombatSpellAttack");
  expect(fn, "brak funkcji handleCombatSpellAttack w app.js").toBeTruthy();

  // 1) Blok finally istnieje i zeruje combatBusy (naprawa zawisu tury).
  expect(/\}\s*finally\s*\{/.test(fn), "handleCombatSpellAttack nie ma bloku finally (#649)").toBeTruthy();
  const finallyIdx = fn.search(/\}\s*finally\s*\{/);
  const finallyBody = fn.slice(finallyIdx);
  expect(/combatBusy\s*=\s*false/.test(finallyBody),
    "finally nie resetuje combatBusy=false → tura wroga zawiśnie (#649)").toBeTruthy();

  // 2) Animacja kości (parytet ze zwykłym atakiem).
  expect(/playCombatDiceRoll\s*\(/.test(fn),
    "handleCombatSpellAttack nie woła playCombatDiceRoll (brak animacji kości #649)").toBeTruthy();
});

test("REGRESSION #649 — index.html ładuje app.js z wersjonowanym importem (cache-bust)", async ({ page }) => {
  const r = await page.request.get("/");
  expect(r.ok()).toBeTruthy();
  const html = await r.text();
  const m = html.match(/app\.js\?v=([^"']+)/);
  // Wersja rośnie z każdym taskiem — sprawdzamy tylko, że import jest wersjonowany.
  // Świeżość samego fixu pokrywa test treści app.js powyżej.
  expect(m, "brak wersjonowanego importu app.js w index.html").toBeTruthy();
});
