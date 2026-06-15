/**
 * REGRESSION #626 (HI3) — Inspektor Bohatera: zakładka Arkusz (edycja liczb).
 * Weryfikuje: (1) kontrakt /full ma pola edytowane w Arkuszu (owner_id/campaign_id/
 * stats/skills/hp/max_hp/mana/max_mana/level/conditions/gold_gp/xp), (2) zapis przez
 * admin_cheat z inspector:true round-trip przez /full (na bohaterze Demo, z przywróceniem),
 * (3) UI: zakładka Arkusz renderuje kontrolki edycji (np. „Zapisz HP" / steppery statów).
 * Acceptance: admin widzi i może edytować liczby bohatera; placeholder HI2 zniknął.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), "dev-login nie zwrócił 200 (#626)").toBeTruthy();
  return (await r.json()).token;
}

async function demoHeroId(page, headers) {
  const items = ((await (await page.request.get("/api/admin/characters", { headers })).json()).items) || [];
  // Bohater konta Demo (user_id=1), NIGDY #1013 (konto obserwowane).
  const hero = items.find(h => Number(h.user_id) === 1 && Number(h.user_id) !== 1013);
  expect(hero, "brak bohatera Demo (user_id=1) do testu (#626)").toBeTruthy();
  return hero.id;
}

test("REGRESSION #626 — /full eksponuje pola edytowane w Arkuszu", async ({ page }) => {
  const headers = { Authorization: `Bearer ${await adminToken(page)}` };
  const id = await demoHeroId(page, headers);
  const full = await (await page.request.get(`/api/admin/characters/${id}/full`, { headers })).json();
  for (const k of [
    "owner_id", "campaign_id", "stats", "skills", "hp", "max_hp",
    "mana", "max_mana", "level", "conditions", "gold_gp", "xp", "is_live_locked",
  ]) {
    expect(k in full, `/full bez pola ${k} (#626)`).toBeTruthy();
  }
});

test("REGRESSION #626 — set gold (inspector) round-trip przez /full", async ({ page }) => {
  const headers = { Authorization: `Bearer ${await adminToken(page)}` };
  const id = await demoHeroId(page, headers);
  const before = await (await page.request.get(`/api/admin/characters/${id}/full`, { headers })).json();
  // Pomiń, jeśli bohater akurat w walce (guard live_locked) — to nie regresja HI3.
  test.skip(before.is_live_locked, "bohater w live-lock — pomijam mutację");
  const target = (Number(before.gold_gp) || 0) + 7;
  try {
    const w = await page.request.post(`/api/admin/cheat/${id}`, {
      headers, data: { cmd: "set gold", value: target, inspector: true },
    });
    expect(w.ok(), "set gold (inspector) nie zwrócił 200 (#626)").toBeTruthy();
    const after = await (await page.request.get(`/api/admin/characters/${id}/full`, { headers })).json();
    expect(Number(after.gold_gp), "złoto nie zaktualizowane w /full (#626)").toBe(target);
  } finally {
    // Przywróć oryginalną wartość — test nie zostawia śladu na bohaterze Demo.
    await page.request.post(`/api/admin/cheat/${id}`, {
      headers, data: { cmd: "set gold", value: Number(before.gold_gp) || 0, inspector: true },
    });
  }
});

test("REGRESSION #626 — zakładka Arkusz renderuje kontrolki edycji (UI)", async ({ page }) => {
  const token = await adminToken(page);
  await page.addInitScript(t => localStorage.setItem("aigm_admin_token", t), token);
  await page.goto("/admin/#heroes");

  // Lista bohaterów wczytana
  const firstRow = page.locator("#heroes-tbody tr[data-hero-id]").first();
  await expect(firstRow, "lista bohaterów nie wyrenderowana (#626)").toBeVisible({ timeout: 15000 });
  await firstRow.click();

  // Modal Inspektora + zakładka Arkusz (domyślnie aktywna) z kontrolkami edycji HI3.
  await expect(page.locator("#hero-sheet-edit"), "brak panelu edycji Arkusza (#626)").toBeVisible({ timeout: 10000 });
  await expect(page.locator('[data-hi-save="hp"]'), "brak przycisku zapisu HP (#626)").toBeVisible();
  await expect(page.locator('[data-hi-stat="STR"]').first(), "brak steppera statu STR (#626)").toBeVisible();
});
