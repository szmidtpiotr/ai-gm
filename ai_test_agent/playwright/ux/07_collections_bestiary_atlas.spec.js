// #1191 — Bestiariusz + Atlas Kresów. API-level regression guard for the two
// player endpoints backing the ŻAR "Kolekcje" tab. Self-contained: logs in as
// demo, resolves a hero, asserts response shape + the locked-entry invariant
// (a locked bestiary entry must NEVER leak the enemy name or key).
const { test, expect, request } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

async function apiCtx() {
  const ctx = await request.newContext({ baseURL: BASE });
  const login = await ctx.post("/api/auth/login", { data: { username: "demo", password: "demo" } });
  expect(login.ok()).toBeTruthy();
  const { access_token } = await login.json();
  return { ctx, token: access_token };
}

async function firstHeroId(ctx, token) {
  const res = await ctx.get("/api/heroes", { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok()) return undefined;
  const body = await res.json();
  const list = Array.isArray(body) ? body : body.heroes || body.data || [];
  return list[0]?.id;
}

test.describe("Kolekcje: Bestiariusz + Atlas (#1191)", () => {
  test("bestiary: summary shape + locked entries never leak name/key", async () => {
    const { ctx, token } = await apiCtx();
    const heroId = await firstHeroId(ctx, token);
    test.skip(!heroId, "no hero on demo account");

    const res = await ctx.get(`/api/characters/${heroId}/bestiary`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty("entries");
    expect(body.summary).toEqual(
      expect.objectContaining({ unlocked: expect.any(Number), total: expect.any(Number), pct: expect.any(Number) }),
    );
    for (const e of body.entries) {
      if (e.locked) {
        expect(e.name).toBeUndefined();
        expect(e.enemy_key).toBeUndefined();
      } else {
        expect(e.enemy_key).toBeTruthy();
        expect(e.name).toBeTruthy();
      }
    }
  });

  test("atlas: hex/location/rumor aggregation shape", async () => {
    const { ctx, token } = await apiCtx();
    const heroId = await firstHeroId(ctx, token);
    test.skip(!heroId, "no hero on demo account");

    const res = await ctx.get(`/api/characters/${heroId}/atlas`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.hexes).toEqual(
      expect.objectContaining({ discovered: expect.any(Number), total: expect.any(Number), pct: expect.any(Number) }),
    );
    expect(Array.isArray(body.hexes.regions)).toBeTruthy();
    expect(body.rumors).toEqual(
      expect.objectContaining({ heard: expect.any(Number), confirmed: expect.any(Number) }),
    );
  });
});
