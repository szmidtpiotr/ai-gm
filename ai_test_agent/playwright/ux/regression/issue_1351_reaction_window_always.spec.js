/**
 * REGRESSION #1351 (WALKA-T5, 5e) — okno reakcji ZAWSZE w single-player.
 * Acceptance: gdy wróg TRAFIA gracza w trybie jednoosobowym, silnik NIE nalicza obrażeń
 * po cichu (auto `player_evasion`) — otwiera okno reakcji (`reaction_window=true`), nawet
 * gdy postać nie ma wyszkolonych reakcji (jedyna opcja „Przyjmij"). HP nie spada do czasu
 * resolve-reaction. Test przez Sandbox (silnik produkcyjny, bez LLM).
 */
const { test, expect } = require("@playwright/test");

// Sandbox `/api/admin/sandbox/*` wymaga tokenu admina (#1187); gameplay `/api/campaigns/*`
// jest otwarte. dev-login demo/demo → Bearer dla wywołań sandboxa.
let ADMIN_HDR = {};

async function postJson(page, url, body, auth) {
  const r = await page.request.post(url, { data: body ?? {}, headers: auth ? ADMIN_HDR : {} });
  return { ok: r.ok(), status: r.status(), body: r.ok() ? await r.json() : null };
}

test("REGRESSION #1351 — enemy hit w SP otwiera okno reakcji (take-only), HP odroczone", async ({ page }) => {
  // 0) token admina do sandboxa
  const login = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(login.ok(), "dev-login demo/demo nie 200 (#1351)").toBeTruthy();
  ADMIN_HDR = { Authorization: `Bearer ${(await login.json()).token}` };

  // 1) wybierz bohatera źródłowego (odfiltruj klony [SBX])
  const heroesRes = await page.request.get("/api/admin/sandbox/heroes", { headers: ADMIN_HDR });
  expect(heroesRes.ok(), "sandbox/heroes nie odpowiada 200 (#1351)").toBeTruthy();
  const heroes = (await heroesRes.json()).heroes || [];
  const hero = heroes.find((h) => !String(h.name || "").startsWith("[SBX] "));
  test.skip(!hero, "brak bohatera do sandboxa — pomiń");

  // 2) setup klona
  const setup = await postJson(page, "/api/admin/sandbox/setup", { hero_id: hero.id }, true);
  expect(setup.ok, "sandbox/setup nie 200 (#1351)").toBeTruthy();
  const campaignId = setup.body.campaign_id;
  const charId = setup.body.character_id;

  // 3) wybierz wroga zwarciowego (nie łucznik/kusznik/mag — żeby atakował od razu)
  const enemiesRes = await page.request.get("/api/admin/sandbox/enemies", { headers: ADMIN_HDR });
  expect(enemiesRes.ok(), "sandbox/enemies nie 200 (#1351)").toBeTruthy();
  const enemies = (await enemiesRes.json()).enemies || [];
  const rangedRe = /łuk|kusz|archer|mag|shaman|czarownik|strzel/i;
  const enemy = enemies.find((e) => !rangedRe.test(`${e.key} ${e.label || ""}`)) || enemies[0];
  test.skip(!enemy, "brak wroga w katalogu — pomiń");

  // 4) start walki
  const start = await postJson(page, "/api/admin/sandbox/start-combat", {
    campaign_id: campaignId, character_id: charId, enemy_keys: [enemy.key],
  }, true);
  expect(start.ok, "sandbox/start-combat nie 200 (#1351)").toBeTruthy();

  // helper: bieżąca tura + HP gracza ze snapshotu
  const snap = async () => {
    const r = await page.request.get(`/api/campaigns/${campaignId}/combat`);
    return r.ok() ? await r.json() : null;
  };
  const playerHp = (s) => {
    const p = (s?.combatants || s?.combat?.combatants || []).find(
      (c) => c.type === "player" || String(c.id).startsWith("player"),
    );
    return p ? Number(p.hp_current) : null;
  };

  // 5) doprowadź do tury wroga i wywołaj atak; toleruj zmianę strefy / Nat 1 (bounded)
  let sawWindow = false;
  let hpBefore = null;
  for (let i = 0; i < 14 && !sawWindow; i++) {
    let s = await snap();
    const cur = String(s?.current_turn || s?.combat?.current_turn || "");
    if (cur.startsWith("player")) {
      await postJson(page, `/api/admin/sandbox/advance-turn`, { campaign_id: campaignId }, true);
      continue;
    }
    hpBefore = playerHp(await snap());
    const et = await postJson(page, `/api/campaigns/${campaignId}/combat/enemy-turn`, {});
    if (!et.ok) break;
    const res = et.body || {};
    if (res.reaction_window === true) {
      sawWindow = true;
      // 5e: opcje mogą być puste (take-only) — flaga okna jest niezależna od opcji
      expect(Array.isArray(res.reaction_options ?? []), "reaction_options nie jest listą").toBeTruthy();
      // HP nie spadło od tego ciosu (obrażenia odroczone do resolve-reaction)
      const hpNow = playerHp(res.combat_state || (await snap()));
      if (hpBefore != null && hpNow != null) {
        expect(hpNow, "HP spadło mimo otwartego okna reakcji (#1351)").toBe(hpBefore);
      }
      // 6) domknij oknem: „Przyjmij cios" → walka wznowiona bez błędu
      const rr = await postJson(page, `/api/campaigns/${campaignId}/combat/resolve-reaction`, { choice: "take" });
      expect(rr.ok, "resolve-reaction(take) nie 200 (#1351)").toBeTruthy();
    } else if (res.zone_change || res.detection) {
      // wróg zbliżył się / wykrywał — nie atakował; następna iteracja
      await postJson(page, `/api/admin/sandbox/advance-turn`, { campaign_id: campaignId }, true);
    } else if (res.hit === false) {
      // Nat 1 wroga = auto-pudło (jedyna ścieżka bez okna w SP) — próbuj dalej
      await postJson(page, `/api/admin/sandbox/advance-turn`, { campaign_id: campaignId }, true);
    }
  }

  expect(sawWindow, "wróg trafił, a okno reakcji się NIE otworzyło — 5e złamane (#1351)").toBeTruthy();

  // sprzątanie
  await postJson(page, `/api/admin/sandbox/end-combat`, { campaign_id: campaignId }, true);
});
