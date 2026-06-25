/**
 * REGRESSION #981 — Kresy: kanoniczne miejsca mają przypisanych NPC + (miejsca grozy) wrogów.
 * Po dosianiu obsady (scripts/seed_kresy_obsada.py) gracz wchodzący na lokację
 * spotyka opisaną postać, a nie generyka improwizowanego przez LLM.
 * Acceptance: nowe canon NPC istnieją; Bór Zmarłych → Wiedźma Jaga + nieumarli;
 * Most: Komora Celna → Pius; Gospoda Pod Złamanym Rogiem → Marta.
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

test("REGRESSION #981 — nowe canon NPC Kresów istnieją w bazie", async ({ page }) => {
  const r = await page.request.get("/api/npcs");
  expect(r.ok(), "/api/npcs nie odpowiada 200 (#981)").toBeTruthy();
  const body = await r.json();
  const rows = Array.isArray(body) ? body : body.data || body.items || [];
  const keys = new Set(rows.map((n) => n.key));
  for (const k of [
    "wiedzma_jaga",
    "ocalaly_zgliszcza",
    "zielarka_mira_bagno",
    "tartacznik_brzezino",
    "karczmarz_most",
    "karczmarz_cieszowice",
  ]) {
    expect(keys.has(k), `brak NPC ${k} w bazie (#981)`).toBeTruthy();
  }
});

test("REGRESSION #981 — Bór Zmarłych ma NPC-hak + wrogów-nieumarłych", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { Authorization: `Bearer ${token}` };
  const r = await page.request.get("/api/locations/bor_zmarlych", { headers: auth });
  expect(r.ok(), "GET /api/locations/bor_zmarlych != 200 (#981)").toBeTruthy();
  const loc = await r.json();
  const npcKeys = loc.npc_keys || [];
  const enemyKeys = loc.enemy_keys || [];
  expect(npcKeys, "Bór Zmarłych bez NPC-haka (Wiedźma Jaga) (#981)").toContain("wiedzma_jaga");
  // miejsce grozy → wrogowie (przeciek Rdzenia)
  expect(enemyKeys.length, "Bór Zmarłych bez encounter-wrogów (#981)").toBeGreaterThan(0);
  expect(enemyKeys.some((k) => ["zombie", "skeleton", "ghoul", "ghost"].includes(k))).toBeTruthy();
});

test("REGRESSION #981 — pod-lokacje hubów obsadzone istniejącymi NPC", async ({ page }) => {
  const token = await adminToken(page);
  const auth = { Authorization: `Bearer ${token}` };
  const cases = [
    ["most_komora_celna", "celnik_pius"],
    ["gospoda_pod_z_amanym_rogiem", "innkeeper_marta"],
    ["brzezino_tartak", "tartacznik_brzezino"],
  ];
  for (const [locKey, npcKey] of cases) {
    const r = await page.request.get(`/api/locations/${locKey}`, { headers: auth });
    expect(r.ok(), `GET ${locKey} != 200 (#981)`).toBeTruthy();
    const loc = await r.json();
    expect(loc.npc_keys || [], `${locKey} bez ${npcKey} (#981)`).toContain(npcKey);
  }
});
