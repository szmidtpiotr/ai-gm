/**
 * REGRESSION #961 — MP combat start endpoint must route to start_mp_combat, not solo router.
 * Acceptance: POST /api/campaigns/{mp_id}/combat/start returns 200 with turn_order containing
 * both players (not 400 "character not found" from the dead solo router path).
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

const ADMIN = { username: "demo", password: "demo" };

async function adminToken(request) {
  const r = await request.post(`${BASE}/api/admin/dev-login`, { data: ADMIN });
  expect(r.ok(), `admin login failed: ${await r.text()}`).toBeTruthy();
  return (await r.json()).token;
}

async function createUser(request, token, suffix) {
  const uname = `pw961_${suffix}`;
  await request.post(`${BASE}/api/admin/accounts/create`, {
    data: { username: uname, password: "pw_961_reg!", display_name: `PW961 ${suffix}`, is_admin: 0 },
    headers: { Authorization: `Bearer ${token}` },
  });
  const r = await request.get(`${BASE}/api/admin/accounts`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const body = await r.json();
  const accounts = Array.isArray(body) ? body : body.items ?? body.accounts ?? [];
  const user = accounts.find((a) => a.username === uname);
  if (!user) throw new Error(`user ${uname} not found after create`);
  return { id: user.id, username: uname };
}

async function createHero(request, uid, suffix) {
  const r = await request.post(`${BASE}/api/characters`, {
    data: { user_id: uid, name: `[PW961]${suffix}`, system_id: "fantasy", sheet_json: { archetype: "warrior" } },
  });
  expect(r.ok(), `createHero: ${await r.text()}`).toBeTruthy();
  return (await r.json()).id;
}

async function setupLobby(request, hId, gId, hHero, gHero, gUsername) {
  let r = await request.post(`${BASE}/api/multiplayer/campaigns`, {
    params: { user_id: hId },
    data: { title: "[PW961]", system_id: "fantasy", round_timer_minutes: 1, max_players: 2 },
  });
  expect(r.ok(), `create lobby: ${await r.text()}`).toBeTruthy();
  const cid = (await r.json()).campaign_id;

  r = await request.post(`${BASE}/api/multiplayer/campaigns/${cid}/accept`, {
    params: { user_id: hId }, data: { character_id: hHero },
  });
  expect(r.ok(), `host accept: ${await r.text()}`).toBeTruthy();

  r = await request.post(`${BASE}/api/multiplayer/campaigns/${cid}/invite/username`, {
    params: { user_id: hId }, data: { username: gUsername },
  });
  expect(r.ok(), `invite: ${await r.text()}`).toBeTruthy();

  r = await request.post(`${BASE}/api/multiplayer/campaigns/${cid}/accept`, {
    params: { user_id: gId }, data: { character_id: gHero },
  });
  expect(r.ok(), `guest accept: ${await r.text()}`).toBeTruthy();
  return cid;
}

test("REGRESSION #961 — MP combat start routes to start_mp_combat (turn_order has both players)", async ({ request }) => {
  const token = await adminToken(request);
  const host = await createUser(request, token, "host");
  const guest = await createUser(request, token, "guest");
  const hHero = await createHero(request, host.id, "H");
  const gHero = await createHero(request, guest.id, "G");
  const cid = await setupLobby(request, host.id, guest.id, hHero, gHero, guest.username);

  const r = await request.post(`${BASE}/api/campaigns/${cid}/combat/start`, {
    params: { user_id: host.id },
    data: { enemy_keys: ["goblin"] },
  });

  expect(r.status(), `MP combat start must be 200, got ${r.status()}: ${await r.text()}`).toBe(200);
  const body = await r.json();
  expect(body.turn_order, "turn_order must exist").toBeTruthy();
  const playerSlots = (body.turn_order || []).filter((t) => String(t).startsWith("player:"));
  expect(playerSlots.length, `must have ≥2 players in turn_order, got: ${JSON.stringify(body.turn_order)}`).toBeGreaterThanOrEqual(2);
});

test("REGRESSION #961 — solo combat start still works (no regression)", async ({ request }) => {
  // Campaign 1 is the persistent demo solo campaign
  const r = await request.post(`${BASE}/api/campaigns/1/combat/start`, {
    data: { enemy_keys: ["goblin"] },
  });
  // 200 = started, 409 = already active — both acceptable; NOT 400 "character not found"
  expect([200, 409, 400].includes(r.status()), `unexpected status ${r.status()}: ${await r.text()}`).toBeTruthy();
  if (r.status() === 400) {
    const body = await r.json();
    expect((body.detail || "").toLowerCase(), "solo must not fail with 'character not found'").not.toContain("character not found");
  }
});
