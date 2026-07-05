/**
 * REGRESSION #1211 — Sandbox scenariuszy: prepare tworzy izolowaną sesję
 * ([SBX-SCN] kampania + klon [SCN], oryginalny bohater nietknięty),
 * /state zwraca log mechaniki, /list pokazuje scenariusz.
 * Acceptance: setup deterministyczny od pierwszej tury, scena (wrogowie/
 * godzina/flagi) ustawiona zgodnie z payloadem, narracja otwierająca obecna.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "admin", password: "admin" },
  });
  if (r.ok()) return (await r.json()).token;
  const r2 = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  return (await r2.json()).token;
}

test("REGRESSION #1211 — scenario prepare/state/list contract", async ({ page }) => {
  const token = await adminToken(page);
  const H = { Authorization: `Bearer ${token}` };

  // hero source — reuse combat-sandbox lookup (filters out clones)
  const heroesR = await page.request.get("/api/admin/sandbox/heroes", { headers: H });
  expect(heroesR.ok(), "sandbox/heroes nie odpowiada (#1211)").toBeTruthy();
  const heroes = (await heroesR.json()).heroes || [];
  test.skip(heroes.length === 0, "brak bohaterów na DEV do sklonowania");
  // demo user (id=1) preferred — never touch real players' accounts in specs
  const hero = heroes.find((h) => h.user_id === 1) || heroes[0];

  const prepR = await page.request.post("/api/admin/scenario/prepare", {
    headers: H,
    data: {
      hero_id: hero.id,
      issue_number: 1211,
      title: "Spec kontraktowy",
      location_name: "Zaułek testowy",
      scene_enemies: ["bandit"],
      ingame_hours: 22,
      opening_narration: "Test: stoisz w zaułku.",
      agent_notes: "spec playwright",
    },
  });
  expect(prepR.ok(), "prepare nie zwraca 200 (#1211)").toBeTruthy();
  const prep = await prepR.json();
  expect(prep.campaign_id).toBeTruthy();
  expect(prep.character_id).toBeTruthy();
  expect(prep.character_id).not.toBe(hero.id);
  expect(prep.title).toContain("[SBX-SCN]");
  expect(prep.title).toContain("#1211");
  expect(prep.hero.name.startsWith("[SCN] ")).toBeTruthy();
  expect(prep.hero.location).toBe("Zaułek testowy");

  // state — scene + opening turn + scenario meta
  const stR = await page.request.get(
    `/api/admin/scenario/${prep.campaign_id}/state`, { headers: H });
  expect(stR.ok(), "state nie zwraca 200 (#1211)").toBeTruthy();
  const st = await stR.json();
  expect(st.session.scene_enemies).toEqual(["bandit"]);
  expect(st.session.ingame_hours).toBe(22);
  expect(st.scenario.issue_number).toBe(1211);
  expect(st.turns.length).toBeGreaterThan(0);
  expect(st.turns[0].assistant_text).toContain("zaułku");
  expect(Array.isArray(st.mechanics)).toBeTruthy();

  // list — scenariusz widoczny z numerem issue
  const listR = await page.request.get("/api/admin/scenario/list", { headers: H });
  expect(listR.ok()).toBeTruthy();
  const rows = (await listR.json()).scenarios || [];
  const mine = rows.find((s) => s.campaign_id === prep.campaign_id);
  expect(mine, "scenariusz nie widnieje na liście (#1211)").toBeTruthy();
  expect(mine.issue_number).toBe(1211);

  // kreator (draft) — kontrakt walidacji: puste wejście = 400 (bez wołania LLM)
  const draftR = await page.request.post("/api/admin/scenario/draft", {
    headers: H, data: {},
  });
  expect(draftR.status(), "draft bez wejścia ma zwracać 400 (#1211)").toBe(400);

  // izolacja — oryginalny bohater nadal na liście źródeł, klon odfiltrowany
  const heroes2R = await page.request.get("/api/admin/sandbox/heroes", { headers: H });
  const heroes2 = (await heroes2R.json()).heroes || [];
  expect(heroes2.some((h) => h.id === hero.id), "oryginał zniknął (#1211)").toBeTruthy();
  expect(heroes2.some((h) => h.id === prep.character_id), "klon [SCN] wyciekł do listy bohaterów").toBeFalsy();
});
