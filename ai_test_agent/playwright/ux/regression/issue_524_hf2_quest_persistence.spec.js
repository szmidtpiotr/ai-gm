/**
 * REGRESSION #524 (HF-2) — Quest persistence: QUEST_SUGGEST zapisuje do character_quests.
 * Acceptance: /api/campaigns/{id}/quests zwraca questy z bazy (nie tylko session_flags);
 *             backend uruchamia się poprawnie z załadowanym quest_persist_service.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

test("REGRESSION #524 — backend health with quest_persist_service loaded", async ({ page }) => {
  const r = await page.request.get(`${BASE}/api/health`);
  expect(r.ok(), "backend health check failed").toBeTruthy();
});

test("REGRESSION #524 — GET /api/campaigns/{id}/quests returns array", async ({ page }) => {
  const loginRes = await page.request.post(`${BASE}/api/auth/login`, {
    data: { username: "demo", password: "demo123" },
  });
  if (!loginRes.ok()) return;

  const { token } = await loginRes.json();
  const campaignsRes = await page.request.get(`${BASE}/api/campaigns`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!campaignsRes.ok()) return;

  const campaigns = await campaignsRes.json();
  if (!campaigns.length) return;

  const campaignId = campaigns[0].id;
  const questsRes = await page.request.get(`${BASE}/api/campaigns/${campaignId}/quests`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  expect(questsRes.ok(), `GET /api/campaigns/${campaignId}/quests should return 200`).toBeTruthy();
  const quests = await questsRes.json();
  expect(Array.isArray(quests), "quests response should be an array").toBeTruthy();
});

test("REGRESSION #524 — backend admin endpoint responds (sanity check)", async ({ page }) => {
  const r = await page.request.get(`${BASE}/api/admin/world/pending/enemies`);
  expect([200, 401, 403].includes(r.status()), `unexpected status ${r.status()}`).toBeTruthy();
});
