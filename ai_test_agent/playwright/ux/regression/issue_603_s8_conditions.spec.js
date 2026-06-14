/**
 * REGRESSION #603 (S8) — batch kondycji FAZY S + prymityw `dot` w katalogu.
 * Acceptance: 7 nowych kondycji (on_fire/frozen/confused/insane/panicked/charmed/cursed)
 * jest zaseedowanych i widocznych w publicznym katalogu kondycji; on_fire opisuje
 * obrażenia od ognia (dot). Kontrakt endpointu — bez LLM, deterministyczny.
 */
const { test, expect } = require("@playwright/test");

const S8_KEYS = ["on_fire", "frozen", "confused", "insane", "panicked", "charmed", "cursed"];

test("REGRESSION #603 — 7 kondycji S8 w katalogu /api/mechanics/conditions", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/conditions");
  expect(r.ok(), "endpoint /api/mechanics/conditions nie odpowiada 200 (#603)").toBeTruthy();
  const body = await r.json();
  const keys = (body.conditions || []).map((c) => c.key);
  for (const k of S8_KEYS) {
    expect(keys, `brak kondycji ${k} w katalogu (#603)`).toContain(k);
  }
});

test("REGRESSION #603 — on_fire opisuje obrażenia od ognia (dot)", async ({ page }) => {
  const r = await page.request.get("/api/mechanics/conditions");
  expect(r.ok()).toBeTruthy();
  const body = await r.json();
  const on_fire = (body.conditions || []).find((c) => c.key === "on_fire");
  expect(on_fire, "on_fire nie istnieje (#603)").toBeTruthy();
  expect(on_fire.label).toBe("Podpalony");
  expect((on_fire.description || "").toLowerCase()).toMatch(/ogni|2k6|płon/);
});
