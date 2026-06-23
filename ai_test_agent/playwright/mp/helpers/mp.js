// Multiplayer Playwright helpers.
//
// The core trick for MP is N independent browser contexts (one logged-in player each) inside a
// single test — see browser.newContext() in the specs. These helpers cover the two hard parts:
//   1. loginAs(page, username, password) — parameterized login (auth.js login() is hard-wired to
//      the single ai_test_player account).
//   2. setupMpViaApi(...) — build a started lobby over the API (mirrors the game-smoke-mp python
//      scripts) so specs assert UI wiring, not lobby plumbing.
//
// Backend DB reads must go through the backend container (WAL) — these helpers only read state via
// HTTP endpoints, never the sshfs mount.

const BACKEND = process.env.BACKEND_URL || "http://192.168.1.61:8100";
const MP_PASSWORD = "mp_tester_2026";
const ADMIN = { username: "demo", password: "demo" };
const ARCHES = ["warrior", "scholar", "rogue", "warrior"];
const HERO_NAME = {
  warrior: "[TEST-MP] Wojownik",
  scholar: "[TEST-MP] Uczony",
  rogue: "[TEST-MP] Łotrzyk",
};

async function _json(res) {
  const t = await res.text();
  try {
    return t ? JSON.parse(t) : {};
  } catch {
    return { _raw: t };
  }
}

async function api(method, path, { body, token, userId } = {}) {
  let url = `${BACKEND}${path}`;
  if (userId != null) url += (url.includes("?") ? "&" : "?") + `user_id=${userId}`;
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(url, {
    method,
    headers,
    body: body != null ? JSON.stringify(body) : undefined,
  });
  return { status: res.status, body: await _json(res) };
}

async function adminToken() {
  const { status, body } = await api("POST", "/api/admin/dev-login", { body: ADMIN });
  if (status !== 200 || !body.token) throw new Error(`admin dev-login failed: ${status}`);
  return body.token;
}

// Parameterized login into the FRONT player UI (frontend/front, served at /front/) — this is the
// UI that carries multiplayer. Resolves once the login screen is dismissed (showScreen('campaigns')).
const FRONT_PATH = process.env.MP_FRONT_PATH || "/front/";
async function loginAs(page, username, password = MP_PASSWORD) {
  await page.goto(FRONT_PATH);
  await page.waitForSelector("#login-username", { state: "visible", timeout: 20000 });
  await page.fill("#login-username", username);
  await page.fill("#login-password", password);
  await page.press("#login-password", "Enter");
  // login-screen loses the active class once authenticated (showScreen swaps screens).
  await page.waitForFunction(
    () => !document.getElementById("login-screen")?.classList.contains("screen--active"),
    null,
    { timeout: 20000 }
  );
}

// Ensure tester_mp1..N (+ optional spectator) exist with one hero each. Idempotent.
async function ensureMpUsers(count = 2, spectator = false) {
  const token = await adminToken();
  const specs = [];
  for (let i = 0; i < count; i++) {
    specs.push({ username: `tester_mp${i + 1}`, display: `MP Tester ${i + 1}`,
                 arch: ARCHES[i], role: i === 0 ? "owner" : "player" });
  }
  if (spectator) {
    specs.push({ username: "tester_mp_spec", display: "MP Spectator", arch: null, role: "spectator" });
  }

  // create-account returns the id on first creation; 409 if it already exists.
  for (const s of specs) {
    await api("POST", "/api/admin/accounts/create", {
      token, body: { username: s.username, password: MP_PASSWORD, display_name: s.display, is_admin: 0 },
    });
  }
  const byName = await _accountsByUsername(token);

  const users = [];
  for (const s of specs) {
    const userId = byName[s.username];
    if (!userId) throw new Error(`cannot resolve user_id for ${s.username}`);
    let heroId = null;
    if (s.arch) {
      const heroName = HERO_NAME[s.arch];
      heroId = await _heroId(userId, heroName);
      if (!heroId) {
        const r = await api("POST", "/api/characters", {
          body: { user_id: userId, name: heroName, system_id: "fantasy", sheet_json: { archetype: s.arch } },
        });
        heroId = r.body.id;
      }
    }
    users.push({ username: s.username, userId, heroId, archetype: s.arch, role: s.role });
  }
  return users;
}

// username -> user_id map from the admin accounts list (container-side DB).
async function _accountsByUsername(token) {
  const { body } = await api("GET", "/api/admin/accounts", { token });
  const list = Array.isArray(body) ? body : body.items || body.accounts || [];
  const map = {};
  for (const a of list) map[a.username] = a.id;
  return map;
}

async function _heroId(userId, name) {
  const { body } = await api("GET", `/api/characters?user_id=${userId}`);
  const list = Array.isArray(body) ? body : body.items || body.heroes || [];
  const hit = list.find((c) => c.name === name);
  return hit ? hit.id : null;
}

// Create + invite + accept + start a lobby over the API. Returns { campaignId, members }.
async function setupMpViaApi(users, { title = "#MP-pw", timer = 1 } = {}) {
  const players = users.filter((u) => u.role !== "spectator");
  const spectators = users.filter((u) => u.role === "spectator");
  const host = players[0];

  const created = await api("POST", "/api/multiplayer/campaigns", {
    userId: host.userId,
    body: { title, system_id: "fantasy", round_timer_minutes: timer, max_players: Math.max(players.length, 2) },
  });
  if (created.status !== 200) throw new Error(`create lobby failed: ${created.status} ${JSON.stringify(created.body)}`);
  const campaignId = created.body.campaign_id;

  // Host selects their hero too (owner is auto-accepted without a character).
  if (host.heroId) {
    await api("POST", `/api/multiplayer/campaigns/${campaignId}/accept`, {
      userId: host.userId,
      body: { character_id: host.heroId },
    });
  }
  for (const u of players.slice(1).concat(spectators)) {
    await api("POST", `/api/multiplayer/campaigns/${campaignId}/invite/username`, {
      userId: host.userId,
      body: { username: u.username },
    });
    await api("POST", `/api/multiplayer/campaigns/${campaignId}/accept`, {
      userId: u.userId,
      body: u.role === "spectator" ? { as_spectator: true } : { character_id: u.heroId },
    });
  }
  await api("POST", `/api/multiplayer/campaigns/${campaignId}/start`, { userId: host.userId });
  return { campaignId, members: users };
}

module.exports = { BACKEND, MP_PASSWORD, api, loginAs, ensureMpUsers, setupMpViaApi };
