/**
 * REGRESSION #1352 (WALKA-T6) — gwarantowany drop minimalny po zwycięstwie.
 * Acceptance: pula consolation `loot_trash_common` jest zaseedowana i niepusta,
 * więc silnik ma z czego wziąć drobiazg, gdy losowanie łupu wroga daje zero —
 * loot modal po victory nigdy nie jest pusty.
 *
 * Kontrakt API (deterministyczny, bez LLM). Właściwy modal 3-wariantowy w ŻAR
 * pokrywa pytest + weryfikacja wizualna; tu pilnujemy fundamentu danych.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const resp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(resp.ok(), "dev-login nie zwrócił 200").toBeTruthy();
  const { token } = await resp.json();
  expect(token, "brak tokenu admina").toBeTruthy();
  return token;
}

test("REGRESSION #1352 — tabela loot_trash_common istnieje i jest aktywna", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.get("/api/admin/loot-tables", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "GET /admin/loot-tables != 200 (#1352)").toBeTruthy();
  const body = await r.json();
  const items = body.items || [];
  const trash = items.find((t) => t.key === "loot_trash_common");
  expect(trash, "brak tabeli loot_trash_common — pula consolation niezaseedowana (#1352)").toBeTruthy();
  expect(Number(trash.is_active)).toBe(1);
});

test("REGRESSION #1352 — pula consolation ma ≥1 grantowalny drobiazg", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.get("/api/admin/loot-tables/loot_trash_common/entries", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "GET entries != 200 (#1352)").toBeTruthy();
  const body = await r.json();
  const entries = body.items || [];
  expect(entries.length, "pula consolation pusta — gracz dostałby puste ręce (#1352)").toBeGreaterThan(0);
  // Każdy wpis musi wskazywać realny klucz katalogu (item/consumable/weapon).
  for (const e of entries) {
    expect(Boolean(e.item_key || e.consumable_key || e.weapon_key)).toBeTruthy();
  }
});
