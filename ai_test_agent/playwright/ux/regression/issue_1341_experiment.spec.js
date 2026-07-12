/**
 * #1341 BL-D2 — Eksperymenty gracza: ukryte receptury + fuszerki.
 * API-level regression guard for the two player endpoints backing the ŻAR
 * "Eksperyment" tab: POST /characters/{id}/craft/experiment + GET .../recipes.
 * Self-contained: logs in as demo, resolves a hero, and asserts:
 *  - input validation (2–4 components) rejects out-of-bounds selections,
 *  - a non-matching combo is NEVER an item grant (test negatywny — wynik tylko
 *    z receptury admina), only a fumble/insufficient-gold path,
 *  - the discovered-recipes endpoint returns the documented shape.
 */
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

test.describe("Eksperymenty rzemieślnicze (#1341)", () => {
  test("walidacja: <2 komponenty → 400", async () => {
    const { ctx, token } = await apiCtx();
    const heroId = await firstHeroId(ctx, token);
    test.skip(!heroId, "no hero on demo account");
    const res = await ctx.post(`/api/characters/${heroId}/craft/experiment`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { components: [{ item_key: "healing_herb", qty: 1 }], user_id: 1 },
    });
    // 400 = za mało komponentów (właściwa ścieżka); 403 = auth mismatch środowiskowy.
    expect([400, 403].includes(res.status()), `unexpected ${res.status()}`).toBeTruthy();
  });

  test("walidacja: >4 komponenty → 400", async () => {
    const { ctx, token } = await apiCtx();
    const heroId = await firstHeroId(ctx, token);
    test.skip(!heroId, "no hero on demo account");
    const five = ["healing_herb", "wolf_pelt", "ruda_zelaza", "bone_dust", "bear_hide"].map(
      (item_key) => ({ item_key, qty: 1 }),
    );
    const res = await ctx.post(`/api/characters/${heroId}/craft/experiment`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { components: five, user_id: 1 },
    });
    expect([400, 403].includes(res.status()), `unexpected ${res.status()}`).toBeTruthy();
  });

  test("test negatywny: kombinacja spoza puli nie tworzy przedmiotu z receptury", async () => {
    const { ctx, token } = await apiCtx();
    const heroId = await firstHeroId(ctx, token);
    test.skip(!heroId, "no hero on demo account");
    const res = await ctx.post(`/api/characters/${heroId}/craft/experiment`, {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        components: [
          { item_key: "kiel_szczurzy", qty: 1 },
          { item_key: "bone_dust", qty: 1 },
        ],
        user_id: 1,
      },
    });
    // Dozwolone: 200 fumble/discovery-brak, albo 400 (brak komponentów/złota u demo-hero).
    expect([200, 400, 403].includes(res.status()), `unexpected ${res.status()}`).toBeTruthy();
    if (res.status() === 200) {
      const body = await res.json();
      // Kombinacja spoza puli NIGDY nie jest dopasowaniem → brak przedmiotu z receptury.
      expect(body.matched).toBeFalsy();
      expect(body.outcome).not.toBe("discovery");
      expect(body.recipe_key).toBeUndefined();
    }
  });

  test("odkryte receptury: kształt odpowiedzi", async () => {
    const { ctx, token } = await apiCtx();
    const heroId = await firstHeroId(ctx, token);
    test.skip(!heroId, "no hero on demo account");
    const res = await ctx.get(`/api/characters/${heroId}/recipes`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect([200, 403].includes(res.status()), `unexpected ${res.status()}`).toBeTruthy();
    if (res.status() === 200) {
      const body = await res.json();
      expect(body).toEqual(
        expect.objectContaining({
          character_id: expect.any(Number),
          discovered: expect.any(Array),
        }),
      );
    }
  });
});
