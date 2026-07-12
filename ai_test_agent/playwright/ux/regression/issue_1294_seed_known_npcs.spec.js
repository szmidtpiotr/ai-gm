/**
 * REGRESSION #1294 (NPC-SEED-1) — plan.key_npcs są seedowane do listy „znani NPC".
 * Acceptance: kampania #9998881 „Żar z Gasnącej Kuźni" pokazuje Brunn/Toma/Jorek/Mirek
 * na liście known-npcs (source=memory), mimo że narrator nigdy nie wyemitował tagu.
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

test("REGRESSION #1294 — roster kampanii seedowany z key_npcs", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.get(
    `/api/admin/campaigns/${CAMPAIGN_ID}/known-npcs`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  expect(r.ok(), "known-npcs endpoint nie odpowiada 200 (#1294)").toBeTruthy();
  const body = await r.json();
  const labels = (body.npcs || []).map((n) => (n.label || "").toLowerCase());

  // kluczowe postacie z planu muszą być na liście
  expect(labels.some((l) => l.includes("brunn")), "brak Brunn na liście znanych NPC").toBeTruthy();
  expect(labels.some((l) => l === "jorek"), "brak karczmarza Jorka").toBeTruthy();
  expect(labels.some((l) => l === "toma"), "brak czeladnika Tomy").toBeTruthy();
});
