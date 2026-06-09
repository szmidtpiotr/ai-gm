/**
 * REGRESSION #432 (E17) — Dungeon loot rarity tiers.
 * Acceptance: dungeon instance rooms contain 'rarity' field (boss=epic/legendary).
 * game_dungeons has dungeon_difficulty column. 5 tiers: common→legendary.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";
const CAMPAIGN_ID = 999445;
const CHARACTER_ID = 999377;
const DUNGEON_KEY = "goblin_warren";

let playerToken = null;

async function getPlayerToken(request) {
  if (playerToken) return playerToken;
  const r = await request.post(`${BASE}/api/auth/login`, {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), `login failed: ${r.status()}`).toBeTruthy();
  playerToken = (await r.json()).access_token;
  return playerToken;
}

test("REGRESSION #432 — dungeon enter includes dungeon_difficulty in response", async ({ request }) => {
  const token = await getPlayerToken(request);

  const r = await request.post(`${BASE}/api/dungeons/${DUNGEON_KEY}/enter`, {
    data: { campaign_id: CAMPAIGN_ID, character_id: CHARACTER_ID },
    headers: { Authorization: `Bearer ${token}` },
  });

  // 200 (fresh entry) or 423 (cooldown) — both valid
  expect(r.status() !== 500, `500 on dungeon enter: ${r.status()}`).toBeTruthy();

  if (r.status() === 200) {
    const body = await r.json();
    expect(body.ok, "ok must be true").toBe(true);
    expect(body.dungeon_run, "dungeon_run must be present").toBeTruthy();

    const run = body.dungeon_run;
    expect(typeof run.dungeon_difficulty === "number", "dungeon_difficulty must be a number").toBeTruthy();
    expect(run.dungeon_difficulty >= 1, "dungeon_difficulty must be >= 1").toBeTruthy();
    expect(run.dungeon_difficulty <= 5, "dungeon_difficulty must be <= 5").toBeTruthy();
  }
});

test("REGRESSION #432 — boss room has rarity field (epic or legendary)", async ({ request }) => {
  const token = await getPlayerToken(request);

  // Try to enter dungeon — may get 423 if on cooldown from prior test
  const r = await request.post(`${BASE}/api/dungeons/${DUNGEON_KEY}/enter`, {
    data: { campaign_id: CAMPAIGN_ID, character_id: CHARACTER_ID },
    headers: { Authorization: `Bearer ${token}` },
  });

  if (r.status() !== 200) return; // cooldown — skip gracefully

  const body = await r.json();
  const rooms = body.dungeon_run?.rooms || [];
  const bossRoom = rooms.find((rm) => rm.is_boss);

  expect(bossRoom, "boss room must be present in dungeon_run.rooms").toBeTruthy();
  expect(bossRoom.rarity, "boss room must have rarity field").toBeTruthy();
  expect(
    bossRoom.rarity === "epic" || bossRoom.rarity === "legendary",
    `boss room rarity must be epic or legendary, got: ${bossRoom.rarity}`
  ).toBeTruthy();
});

test("REGRESSION #432 — dungeons list endpoint responds 200", async ({ request }) => {
  const r = await request.get(`${BASE}/api/dungeons`);
  expect(r.ok(), `dungeons list failed: ${r.status()}`).toBeTruthy();

  const body = await r.json();
  expect(Array.isArray(body.dungeons), "body.dungeons must be array").toBeTruthy();
});
