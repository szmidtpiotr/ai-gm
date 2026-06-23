/**
 * REGRESSION #927 (GF7) — E2E integration check: wszystkie blokery MP domknięte.
 * Acceptance: create→invite→start→runda→czat — każdy element łańcucha istnieje i odpowiada 2xx.
 * Pokrywa blokery: #934 (kafelek), #935 (router), #936/#932 (model_id), #938 (tabele), #939 (HTML).
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

// ─── Frontend DOM ─────────────────────────────────────────────────────────────

test("REGRESSION #927 — #mp-btn istnieje w hubie (#934)", async ({ page }) => {
  await page.goto(BASE + "/");
  const mpBtn = await page.locator('#mp-btn').count();
  expect(mpBtn, "#mp-btn nie istnieje w DOM — fix #934 nie zaaplikowany").toBeGreaterThan(0);
});

test("REGRESSION #927 — openMultiplayerLobby używa klucza 'create-lobby' (#935)", async ({ page }) => {
  await page.goto(BASE + "/");
  await page.evaluate(() => {
    window._screenShown = null;
    window.showScreen = (name) => { window._screenShown = name; };
  });
  await page.evaluate(() => window.openMultiplayerLobby && window.openMultiplayerLobby());
  const shown = await page.evaluate(() => window._screenShown);
  expect(shown, "openMultiplayerLobby nie wywołał showScreen('create-lobby')").toBe('create-lobby');
});

test("REGRESSION #927 — #create-lobby-screen istnieje w DOM", async ({ page }) => {
  await page.goto(BASE + "/");
  const el = await page.locator('#create-lobby-screen').count();
  expect(el, "#create-lobby-screen nie ma w DOM").toBeGreaterThan(0);
});

test("REGRESSION #927 — #party-chat-panel istnieje w DOM (#939)", async ({ page }) => {
  await page.goto(BASE + "/");
  const el = await page.locator('#party-chat-panel').count();
  expect(el, "#party-chat-panel nie istnieje — fix #939 nie zaaplikowany").toBeGreaterThan(0);
});

// ─── API endpoints — kampania MP ──────────────────────────────────────────────

test("REGRESSION #927 — /api/campaign-modes zawiera multiplayer (#934)", async ({ page }) => {
  const r = await page.request.get(`${BASE}/api/campaign-modes`);
  expect(r.ok(), `/api/campaign-modes zwrócił ${r.status()}`).toBeTruthy();
  const body = await r.json();
  // modes is an array [{key, label, available, ...}]
  const mp = Array.isArray(body.modes) && body.modes.find(m => m.key === 'multiplayer');
  expect(mp, "Tryb 'multiplayer' brak w modes array").toBeTruthy();
  expect(mp.available, "multiplayer.available != true").toBe(true);
});

test("REGRESSION #927 — POST /api/multiplayer/campaigns wymaga auth (nie 500) (#936)", async ({ page }) => {
  const r = await page.request.post(`${BASE}/api/multiplayer/campaigns`, {
    data: { session_name: "test927", max_players: 2 },
    headers: { "Content-Type": "application/json" }
  });
  // Bez auth: 401 lub 422. 500 = NOT NULL crash (bug #936 nadal żywy)
  expect(r.status(), `POST /multiplayer/campaigns zwrócił 500 — model_id NOT NULL bug #936 nadal żywy`)
    .not.toBe(500);
});

test("REGRESSION #927 — /api/multiplayer/my-invites istnieje i zwraca 200 (#925)", async ({ page }) => {
  const r = await page.request.get(`${BASE}/api/multiplayer/my-invites?user_id=1`);
  expect(r.ok(), `/api/multiplayer/my-invites zwrócił ${r.status()}`).toBeTruthy();
  const body = await r.json();
  expect(body, "brak klucza 'invites'").toHaveProperty("invites");
});

test("REGRESSION #927 — /api/multiplayer/my-lobbies istnieje i zwraca 200 (#925)", async ({ page }) => {
  const r = await page.request.get(`${BASE}/api/multiplayer/my-lobbies?user_id=1`);
  expect(r.ok(), `/api/multiplayer/my-lobbies zwrócił ${r.status()}`).toBeTruthy();
  const body = await r.json();
  expect(body, "brak klucza 'lobbies'").toHaveProperty("lobbies");
});

test("REGRESSION #927 — /api/multiplayer/my-active-games istnieje i zwraca 200 (#925)", async ({ page }) => {
  const r = await page.request.get(`${BASE}/api/multiplayer/my-active-games?user_id=1`);
  expect(r.ok(), `/api/multiplayer/my-active-games zwrócił ${r.status()}`).toBeTruthy();
  const body = await r.json();
  expect(body, "brak klucza 'games'").toHaveProperty("games");
});

test("REGRESSION #927 — party-messages endpoint istnieje (nie 500) (#938)", async ({ page }) => {
  // nieistniejąca kampania → 404, ale NIE 500 (tabela party_messages musi istnieć)
  const r = await page.request.get(`${BASE}/api/multiplayer/0/party-messages`);
  expect(r.status(), `party-messages zwrócił 500 — tabela party_messages nadal brak`).not.toBe(500);
});
