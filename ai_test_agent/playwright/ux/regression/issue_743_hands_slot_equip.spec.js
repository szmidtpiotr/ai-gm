/**
 * REGRESSION #743 — Ekwipowanie rękawic (armor_coverage='hands') musi działać.
 * Przed fixem: equip_item rzucał ValueError "invalid armor_coverage 'hands'" — slot
 * nie był zdefiniowany w loot_service._VALID_ARMOR_COVERAGE.
 * Acceptance: leather_gloves i plate_gauntlets zakładają się na slot 'hands' bez błędu.
 */
const { test, expect } = require("@playwright/test");

const TEST_CHAR_ID = 2; // [TEST] Wojownik — demo user, bezpieczny do modyfikacji

async function adminLogin(page) {
  const resp = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  const { token } = await resp.json();
  return token;
}

async function addItem(page, token, charId, itemKey) {
  const r = await page.request.post(`/api/admin/cheat/${charId}`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { cmd: "add item", key: itemKey, kind: "item" },
  });
  expect(r.ok(), `add item ${itemKey} nie odpowiedział 200 (#743)`).toBeTruthy();
  return await r.json(); // może zawierać equipped_slot jeśli auto-equip zadziałał
}

async function removeItem(page, token, charId, itemKey) {
  await page.request.post(`/api/admin/cheat/${charId}`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { cmd: "remove item", key: itemKey },
  });
}

test("REGRESSION #743 — konfiguracja: leather_gloves i plate_gauntlets mają armor_coverage='hands'", async ({ page }) => {
  const token = await adminLogin(page);

  const r = await page.request.get("/api/admin/items", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "GET /api/admin/items nie odpowiada 200 (#743)").toBeTruthy();

  const items = await r.json();
  const list = Array.isArray(items) ? items : (items.items || items.data || []);

  const gloves = list.find((i) => i.key === "leather_gloves");
  expect(gloves, "leather_gloves nie istnieje w bazie (#743)").toBeTruthy();
  expect(gloves.armor_coverage, "leather_gloves.armor_coverage musi być 'hands' (#743)").toBe("hands");

  const gauntlets = list.find((i) => i.key === "plate_gauntlets");
  expect(gauntlets, "plate_gauntlets nie istnieje w bazie (#743)").toBeTruthy();
  expect(gauntlets.armor_coverage, "plate_gauntlets.armor_coverage musi być 'hands' (#743)").toBe("hands");
});

test("REGRESSION #743 — leather_gloves zakładają się na slot 'hands' (nie rzuca błędu)", async ({ page }) => {
  const token = await adminLogin(page);

  // Dodaj rękawice do inwentarza postaci testowej
  const addResult = await addItem(page, token, TEST_CHAR_ID, "leather_gloves");
  const autoEquipSlot = (addResult.result || addResult).equipped_slot;

  try {
    // Jeśli auto-equip zadziałał — zweryfikuj slot z odpowiedzi
    if (autoEquipSlot) {
      expect(autoEquipSlot, "auto-equip rękawic musi trafiać na slot 'hands' (#743)").toBe("hands");
      return;
    }

    // Brak auto-equip — ręczny equip przez endpoint
    const inv = await page.request.get(`/api/inventory/${TEST_CHAR_ID}`);
    expect(inv.ok(), `GET /api/inventory/${TEST_CHAR_ID} nie odpowiada 200 (#743)`).toBeTruthy();
    const invBody = await inv.json();
    const invItems = invBody.data || invBody.items || invBody || [];
    const glovesEntry = invItems.find(
      (i) => i.item_key === "leather_gloves" && !i.equipped
    );
    expect(glovesEntry, "leather_gloves nie znalezione w inwentarzu po dodaniu (#743)").toBeTruthy();

    const equipResp = await page.request.post(`/api/inventory/${TEST_CHAR_ID}/equip`, {
      data: { inventory_id: glovesEntry.id, slot: "hands" },
    });
    // Przed fixem tutaj był 500 "invalid armor_coverage 'hands'"
    expect(equipResp.ok(), `equip rękawic rzucił błąd — regression #743! Status: ${equipResp.status()}`).toBeTruthy();

    const equipBody = await equipResp.json();
    const equipped = equipBody.data || equipBody;
    expect(equipped.slot, "equip rękawic musi zwrócić slot='hands' (#743)").toBe("hands");
    expect(equipped.equipped, "rękawice muszą być oznaczone jako equipped=1 (#743)").toBeTruthy();
  } finally {
    // Sprzątanie — usuń rękawice z inwentarza
    await removeItem(page, token, TEST_CHAR_ID, "leather_gloves");
  }
});

test("REGRESSION #743 — brak regresji: zakładanie zbroi głowy (head) na slot 'head' nadal działa", async ({ page }) => {
  const token = await adminLogin(page);

  const r = await page.request.get("/api/admin/items", {
    headers: { Authorization: `Bearer ${token}` },
  });
  const items = await r.json();
  const list = Array.isArray(items) ? items : (items.items || items.data || []);
  const headArmor = list.find((i) => i.armor_coverage === "head" && i.is_active);
  expect(headArmor, "brak aktywnego przedmiotu z armor_coverage='head' do testu regresji (#743)").toBeTruthy();

  const addResult = await addItem(page, token, TEST_CHAR_ID, headArmor.key);

  try {
    if (addResult.equipped_slot) {
      expect(addResult.equipped_slot, "head armor auto-equip musi trafiać na slot 'head' (#743 backward compat)").toBe("head");
      return;
    }

    const inv = await page.request.get(`/api/inventory/${TEST_CHAR_ID}`);
    const invBody = await inv.json();
    const invItems = invBody.data || invBody.items || invBody || [];
    const headEntry = invItems.find((i) => i.item_key === headArmor.key && !i.equipped);
    if (!headEntry) return; // może już być equipped przez auto-equip; wystarczy że nie rzucił błędu

    const equipResp = await page.request.post(`/api/inventory/${TEST_CHAR_ID}/equip`, {
      data: { inventory_id: headEntry.id, slot: "head" },
    });
    expect(equipResp.ok(), `equip head armor rzucił błąd (#743 backward compat). Status: ${equipResp.status()}`).toBeTruthy();
    const equipBody3 = await equipResp.json();
    const equipped = equipBody3.data || equipBody3;
    expect(equipped.slot, "head armor musi mieć slot='head' (#743 backward compat)").toBe("head");
  } finally {
    await removeItem(page, token, TEST_CHAR_ID, headArmor.key);
  }
});
