/**
 * REGRESSION #376 (D1) — Pending flow przedmiotów.
 * Nieznany "Grant Item <label>" → rekord pending_review w game_config_items,
 * widoczny w kolejce recenzji admina (Świat → Pending review).
 * Acceptance: endpoint /api/admin/world/pending/items zwraca listę, a licznik
 * /pending/counts zawiera klucz `items` — to dane, z których panel admin3 rysuje
 * sekcję "Przedmiot" w kolejce recenzji.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #376 — kolejka pending items odpowiada poprawnym kontraktem", async ({ page }) => {
  // 1) Lista pending items — kształt {items: []}
  const list = await page.request.get("/api/admin/world/pending/items");
  expect(list.ok(), "GET /pending/items nie odpowiada 200 (#376)").toBeTruthy();
  const listBody = await list.json();
  expect(Array.isArray(listBody.items), "/pending/items.items musi być tablicą (#376)").toBeTruthy();

  // Każdy rekord (jeśli są) musi mieć review_status=pending_review i klucz.
  for (const it of listBody.items) {
    expect(it.key, "pending item bez klucza (#376)").toBeTruthy();
    expect(it.review_status, "pending item musi mieć review_status=pending_review (#376)").toBe("pending_review");
  }

  // 2) Licznik kolejki zawiera `items` — badge w panelu admina liczy na ten klucz.
  const counts = await page.request.get("/api/admin/world/pending/counts");
  expect(counts.ok(), "GET /pending/counts nie odpowiada 200 (#376)").toBeTruthy();
  const countsBody = await counts.json();
  expect(typeof countsBody.items, "pending/counts musi mieć numeryczny klucz items (#376)").toBe("number");
  expect(countsBody.items, "licznik items musi być >= długości listy (#376)").toBeGreaterThanOrEqual(listBody.items.length);
});
