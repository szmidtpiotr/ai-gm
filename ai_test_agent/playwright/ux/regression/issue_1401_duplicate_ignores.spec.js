/**
 * REGRESSION #1401 — «to nie duplikat»: ignore/list/restore w detektorze duplikatów.
 * Acceptance: POST /ignore zapisuje parę, GET /ignores ją listuje, DELETE /ignore/{id}
 * przywraca; walidacja tabeli daje 400. Test używa sztucznych kluczy spec1401_* —
 * nie dotyka realnych danych.
 */
const { test, expect } = require("@playwright/test");

async function adminAuth(page) {
  const resp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(resp.ok(), "dev-login nie działa (#1401)").toBeTruthy();
  const { token } = await resp.json();
  return { Authorization: `Bearer ${token}` };
}

test("REGRESSION #1401 — ignore → list → restore", async ({ page }) => {
  const headers = await adminAuth(page);

  const ign = await page.request.post("/api/admin/duplicates/ignore", {
    headers,
    data: { table: "items", keys: ["spec1401_a", "spec1401_b"] },
  });
  expect(ign.ok(), "POST /ignore nie odpowiada 200 (#1401)").toBeTruthy();

  const list = await page.request.get("/api/admin/duplicates/ignores", { headers });
  expect(list.ok()).toBeTruthy();
  const rows = (await list.json()).ignores;
  const mine = rows.find((r) => r.key_a === "spec1401_a" && r.key_b === "spec1401_b");
  expect(mine, "zapisana para musi być na liście").toBeTruthy();
  expect(mine.table_name).toBe("items");

  const del = await page.request.delete(`/api/admin/duplicates/ignore/${mine.id}`, { headers });
  expect(del.ok(), "DELETE /ignore/{id} nie odpowiada 200 (#1401)").toBeTruthy();
  const after = (await (await page.request.get("/api/admin/duplicates/ignores", { headers })).json()).ignores;
  expect(after.find((r) => r.id === mine.id), "para musi zniknąć po przywróceniu").toBeFalsy();
});

test("REGRESSION #1401 — walidacja: zła tabela i za mało kluczy → 400", async ({ page }) => {
  const headers = await adminAuth(page);
  const badTable = await page.request.post("/api/admin/duplicates/ignore", {
    headers,
    data: { table: "enemies", keys: ["a", "b"] },
  });
  expect(badTable.status()).toBe(400);
  const oneKey = await page.request.post("/api/admin/duplicates/ignore", {
    headers,
    data: { table: "items", keys: ["solo"] },
  });
  expect(oneKey.status()).toBe(400);
});
