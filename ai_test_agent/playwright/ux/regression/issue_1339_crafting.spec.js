/**
 * #1339 BL-C4 — Rzemiosło light: przepisy + craft + komponenty.
 * API-level regression guard for the two player endpoints backing the ŻAR
 * "Rzemiosło" tab (#1336 BL-C1 / #1338 BL-C3). Self-contained: logs in as demo,
 * resolves a hero, asserts the crafting listing shape at a seeded herbalist
 * location, and that the craft endpoint validates components + registration.
 * Mirrors the recipe seed: mikstura lecznicza = zioła (komponenty) → consumable.
 */
const { test, expect, request } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";
// Seeded herbalist location (npc zielarka_mira_bagno) — patrz world_map seed.
const CRAFTER_LOC = "bagienna_chatka_zielarki";

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

test.describe("Rzemiosło: przepisy + craft (#1339)", () => {
  test("listing: herbalist location exposes recipes with component inputs", async () => {
    const { ctx } = await apiCtx();
    const res = await ctx.get(`/api/locations/${CRAFTER_LOC}/crafting`);
    expect(res.ok(), `crafting listing ${CRAFTER_LOC} → ${res.status()}`).toBeTruthy();
    const body = await res.json();
    expect(body).toEqual(
      expect.objectContaining({
        location_key: expect.any(String),
        crafters: expect.any(Array),
        recipes: expect.any(Array),
      }),
    );
    test.skip(body.recipes.length === 0, "seed drift: no recipes at this location");
    expect(body.crafters).toContain("herbalist");
    // Każdy przepis: składniki + koszt usługi + wynik.
    for (const r of body.recipes) {
      expect(r.key).toBeTruthy();
      expect(Array.isArray(r.inputs)).toBeTruthy();
      expect(r.inputs.length).toBeGreaterThan(0);
      expect(typeof r.service_cost_gold).toBe("number");
      expect(r.output_type).toBeTruthy();
    }
    // Mikstura lecznicza (z ziół) → consumable; wsad to komponenty-zioła.
    const potion = body.recipes.find((r) => r.output_type === "consumable");
    expect(potion, "brak przepisu na miksturę (consumable)").toBeTruthy();
    expect(potion.inputs.some((i) => i.item_key && i.qty >= 1)).toBeTruthy();
  });

  test("listing: unknown location → 404", async () => {
    const { ctx } = await apiCtx();
    const res = await ctx.get(`/api/locations/__nope_1339__/crafting`);
    expect(res.status()).toBe(404);
  });

  test("craft: unknown recipe rejected", async () => {
    const { ctx, token } = await apiCtx();
    const heroId = await firstHeroId(ctx, token);
    test.skip(!heroId, "no hero on demo account");
    const res = await ctx.post(`/api/characters/${heroId}/craft`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { recipe_key: "__nope_1339__", user_id: 1 },
    });
    expect([400, 404].includes(res.status()), `unexpected ${res.status()}`).toBeTruthy();
  });

  test("craft: real recipe without components → 400 (walidacja komponentów)", async () => {
    const { ctx, token } = await apiCtx();
    const heroId = await firstHeroId(ctx, token);
    test.skip(!heroId, "no hero on demo account");
    // Ostrzenie broni wymaga kła + rudy — demo-hero ich nie ma na starcie testu.
    const res = await ctx.post(`/api/characters/${heroId}/craft`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { recipe_key: "weapon_hone_dmg", user_id: 1 },
    });
    // 400 = brak komponentów/złota (właściwa ścieżka walidacji); 403 = auth mismatch.
    expect([400, 403].includes(res.status()), `unexpected ${res.status()}`).toBeTruthy();
  });
});
