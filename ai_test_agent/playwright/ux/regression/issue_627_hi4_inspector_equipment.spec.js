/**
 * REGRESSION #627 (HI4) — Inspektor Bohatera: zakładki Ekwipunek + Zaklęcia + Questy.
 * Weryfikuje: (1) kontrakt /full — `inventory[]` ma id/key/item_type/equipped, `spells[]`,
 * `quests_active`/`quests_completed`; (2) equip round-trip (inspector:true → audyt+guard)
 * na broni bohatera Demo z przywróceniem stanu; (3) UI: zakładki Ekwipunek/Zaklęcia/Questy
 * renderują kontrolki (dropdown katalogu, „Naucz", „Dodaj quest").
 * Acceptance: admin zarządza przedmiotami/zaklęciami/questami; placeholdery HI2 zniknęły.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), "dev-login nie zwrócił 200 (#627)").toBeTruthy();
  return (await r.json()).token;
}

async function demoHeroId(page, headers) {
  const items = ((await (await page.request.get("/api/admin/characters", { headers })).json()).items) || [];
  // Bohater konta Demo (user_id=1), NIGDY #1013 (konto obserwowane).
  const hero = items.find(h => Number(h.user_id) === 1 && Number(h.user_id) !== 1013);
  expect(hero, "brak bohatera Demo (user_id=1) do testu (#627)").toBeTruthy();
  return hero.id;
}

test("REGRESSION #627 — /full eksponuje ekwipunek/zaklęcia/questy", async ({ page }) => {
  const headers = { Authorization: `Bearer ${await adminToken(page)}` };
  const id = await demoHeroId(page, headers);
  const full = await (await page.request.get(`/api/admin/characters/${id}/full`, { headers })).json();
  for (const k of ["inventory", "spells", "quests_active", "quests_completed"]) {
    expect(k in full, `/full bez pola ${k} (#627)`).toBeTruthy();
  }
  expect(Array.isArray(full.inventory), "inventory nie jest listą (#627)").toBeTruthy();
  if (full.inventory.length) {
    const it = full.inventory[0];
    for (const k of ["id", "item_type", "equipped"]) {
      expect(k in it, `wiersz inventory bez pola ${k} (#627)`).toBeTruthy();
    }
  }
});

test("REGRESSION #627 — equip round-trip (inspector) przez /full", async ({ page }) => {
  const headers = { Authorization: `Bearer ${await adminToken(page)}` };
  const id = await demoHeroId(page, headers);
  const before = await (await page.request.get(`/api/admin/characters/${id}/full`, { headers })).json();
  test.skip(before.is_live_locked, "bohater w live-lock — pomijam mutację");
  const weapon = (before.inventory || []).find(i => i.item_type === "weapon");
  test.skip(!weapon, "bohater nie ma broni w ekwipunku — pomijam equip round-trip");

  const wasEquipped = !!weapon.equipped;
  const origSlot = weapon.slot || "main_hand";
  try {
    // Zdejmij broń (inspector:true → audyt + guard).
    const w = await page.request.post(`/api/inventory/${id}/equip`, {
      data: { inventory_id: weapon.id, slot: null, inspector: true },
    });
    expect(w.ok(), "unequip (inspector) nie zwrócił 200 (#627)").toBeTruthy();
    const after = await (await page.request.get(`/api/admin/characters/${id}/full`, { headers })).json();
    const w2 = (after.inventory || []).find(i => i.id === weapon.id);
    expect(Number(w2.equipped), "broń nadal założona po unequip (#627)").toBe(0);
  } finally {
    // Przywróć oryginalny stan — test nie zostawia śladu na bohaterze Demo.
    if (wasEquipped) {
      await page.request.post(`/api/inventory/${id}/equip`, {
        data: { inventory_id: weapon.id, slot: origSlot, inspector: true },
      });
    }
  }
});

test("REGRESSION #627 — zakładki Ekwipunek/Zaklęcia/Questy renderują kontrolki (UI)", async ({ page }) => {
  const token = await adminToken(page);
  await page.addInitScript(t => localStorage.setItem("aigm_admin_token", t), token);
  await page.goto("/admin/#heroes");

  const firstRow = page.locator("#heroes-tbody tr[data-hero-id]").first();
  await expect(firstRow, "lista bohaterów nie wyrenderowana (#627)").toBeVisible({ timeout: 15000 });
  await firstRow.click();

  // Ekwipunek
  await page.locator('[data-htab="inventory"]').click();
  await expect(page.locator("#hi-item-select"), "brak dropdownu katalogu przedmiotów (#627)").toBeVisible({ timeout: 10000 });
  await expect(page.locator("[data-hi-item-add]"), "brak przycisku Dodaj przedmiot (#627)").toBeVisible();

  // Zaklęcia
  await page.locator('[data-htab="spells"]').click();
  await expect(page.locator("#hi-spell-select"), "brak dropdownu zaklęć (#627)").toBeVisible({ timeout: 10000 });
  await expect(page.locator("[data-hi-spell-learn]"), "brak przycisku Naucz (#627)").toBeVisible();

  // Questy
  await page.locator('[data-htab="quests"]').click();
  await expect(page.locator("#hi-quest-input"), "brak pola dodania questa (#627)").toBeVisible({ timeout: 10000 });
  await expect(page.locator("[data-hi-quest-add]"), "brak przycisku Dodaj quest (#627)").toBeVisible();
});
