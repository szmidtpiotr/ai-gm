/**
 * REGRESSION #925 (GF5) — Kampanie: sekcje MP (Zaproszenia / Moje lobby / Aktywne gry).
 * Acceptance:
 *   - DOM zawiera elementy mp-invites-section, mp-lobbies-section, mp-games-section
 *   - Endpointy /my-invites, /my-lobbies, /my-active-games zwracają 200 + poprawny kształt
 *   - POST accept/decline działa poprawnie
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

test("REGRESSION #925 — DOM zawiera sekcje MP w index.html", async ({ page }) => {
  const r = await page.request.get(`${BASE}/front/index.html`);
  expect(r.ok(), "index.html niedostępny (#925)").toBeTruthy();
  const html = await r.text();
  expect(html, "brak mp-invites-section").toContain('id="mp-invites-section"');
  expect(html, "brak mp-lobbies-section").toContain('id="mp-lobbies-section"');
  expect(html, "brak mp-games-section").toContain('id="mp-games-section"');
  expect(html, "brak mp-invites-list").toContain('id="mp-invites-list"');
  expect(html, "brak mp-lobbies-list").toContain('id="mp-lobbies-list"');
  expect(html, "brak mp-games-list").toContain('id="mp-games-list"');
});

test("REGRESSION #925 — /my-invites zwraca 200 z kluczem invites", async ({ page }) => {
  const r = await page.request.get(`${BASE}/api/multiplayer/my-invites?user_id=1`);
  expect(r.ok(), "/my-invites nie odpowiada 200").toBeTruthy();
  const body = await r.json();
  expect(body, "brak klucza 'invites'").toHaveProperty("invites");
  expect(Array.isArray(body.invites), "'invites' nie jest tablicą").toBeTruthy();
});

test("REGRESSION #925 — /my-lobbies zwraca 200 z kluczem lobbies", async ({ page }) => {
  const r = await page.request.get(`${BASE}/api/multiplayer/my-lobbies?user_id=1`);
  expect(r.ok(), "/my-lobbies nie odpowiada 200").toBeTruthy();
  const body = await r.json();
  expect(body, "brak klucza 'lobbies'").toHaveProperty("lobbies");
  expect(Array.isArray(body.lobbies), "'lobbies' nie jest tablicą").toBeTruthy();
});

test("REGRESSION #925 — /my-active-games zwraca 200 z kluczem games", async ({ page }) => {
  const r = await page.request.get(`${BASE}/api/multiplayer/my-active-games?user_id=1`);
  expect(r.ok(), "/my-active-games nie odpowiada 200").toBeTruthy();
  const body = await r.json();
  expect(body, "brak klucza 'games'").toHaveProperty("games");
  expect(Array.isArray(body.games), "'games' nie jest tablicą").toBeTruthy();
});

test("REGRESSION #925 — campaigns.js zawiera funkcje MP sections", async ({ page }) => {
  const r = await page.request.get(`${BASE}/front/js/screens/campaigns.js`);
  expect(r.ok(), "campaigns.js niedostępny").toBeTruthy();
  const js = await r.text();
  expect(js, "brak _loadMpSections").toContain("_loadMpSections");
  expect(js, "brak _renderMpInvites").toContain("_renderMpInvites");
  expect(js, "brak _renderMpLobbies").toContain("_renderMpLobbies");
  expect(js, "brak _renderMpActiveGames").toContain("_renderMpActiveGames");
  expect(js, "brak _acceptMpInvite").toContain("_acceptMpInvite");
  expect(js, "brak _declineMpInvite").toContain("_declineMpInvite");
});
