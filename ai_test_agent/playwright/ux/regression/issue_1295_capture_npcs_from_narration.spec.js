/**
 * REGRESSION #1295 (NPC-SEED-2) — znane encje z narracji trafiają do rostera
 * bez zależności od tagów LLM.
 * Acceptance: lista known-npcs kampanii #9998881 jest NIEPUSTA i zawiera wpisy
 * source=memory (roster zapełniony deterministycznie, nie przez opcjonalny [NPC_MEMORY]).
 */
const { test, expect } = require("@playwright/test");

const CAMPAIGN_ID = 9998881;

async function adminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), "dev-login nie zwrócił 200").toBeTruthy();
  const b = await r.json();
  return b.token || b.access_token;
}

test("REGRESSION #1295 — roster niepusty, wpisy source=memory", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.get(
    `/api/admin/campaigns/${CAMPAIGN_ID}/known-npcs`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  expect(r.ok(), "known-npcs endpoint nie odpowiada 200 (#1295)").toBeTruthy();
  const body = await r.json();
  const npcs = body.npcs || [];

  expect(npcs.length, "lista znanych NPC jest pusta (#1295)").toBeGreaterThan(0);
  const memoryEntries = npcs.filter((n) => n.source === "memory");
  expect(memoryEntries.length, "brak wpisów source=memory — roster nie został zapełniony").toBeGreaterThan(0);
});
