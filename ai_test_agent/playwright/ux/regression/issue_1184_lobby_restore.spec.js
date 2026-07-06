/**
 * REGRESSION #1184 (code-review) — restore lobby MP po F5: podpięcie tryRestoreLobbySession.
 * Acceptance: serwowany app.js woła tryRestoreLobbySession() gejtowane aigm_lobby_id,
 *   multiplayer_ui.js nadal definiuje funkcję, a import w index.html ma podbite ?v= (1184).
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1184 — app.js wires tryRestoreLobbySession on init", async ({ page }) => {
  const r = await page.request.get("/js/app.js");
  expect(r.ok(), "app.js nie serwowany (#1184)").toBeTruthy();
  const src = await r.text();
  expect(src.includes("tryRestoreLobbySession("), "app.js nie woła tryRestoreLobbySession() (#1184)").toBeTruthy();
  expect(src.includes("aigm_lobby_id"), "brak gejta aigm_lobby_id wokół restore (#1184)").toBeTruthy();
});

test("REGRESSION #1184 — multiplayer_ui.js still defines restore fn + clears stale key", async ({ page }) => {
  const r = await page.request.get("/js/multiplayer_ui.js");
  expect(r.ok(), "multiplayer_ui.js nie serwowany (#1184)").toBeTruthy();
  const src = await r.text();
  expect(src.includes("async function tryRestoreLobbySession("), "funkcja restore usunięta (#1184)").toBeTruthy();
  // edge: zamknięte/nieistniejące lobby → wyczyść klucz (>=2 wywołania: status!=open + catch)
  const fn = src.slice(src.indexOf("async function tryRestoreLobbySession("));
  const clears = (fn.slice(0, 800).match(/_clearLobbySession\(\)/g) || []).length;
  expect(clears >= 2, "restore nie czyści klucza przy zamkniętym lobby / w catch (#1184)").toBeTruthy();
});

test("REGRESSION #1184 — index.html cache-busts multiplayer_ui.js (?v=1184)", async ({ page }) => {
  const r = await page.request.get("/index.html");
  expect(r.ok(), "index.html nie serwowany (#1184)").toBeTruthy();
  const html = await r.text();
  const m = html.match(/multiplayer_ui\.js\?v=([^"'> ]+)/);
  expect(m, "brak zawersjonowanego importu multiplayer_ui.js (#1184)").toBeTruthy();
  expect(m[1].includes("1184"), `?v= nie podbite dla #1184 (jest: ${m ? m[1] : "?"})`).toBeTruthy();
});
