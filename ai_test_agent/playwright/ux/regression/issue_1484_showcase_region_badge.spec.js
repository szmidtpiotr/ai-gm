/**
 * REGRESSION #1484 (Faza RM) — badge krainy na wizytówce idzie za statusem krainy w grze.
 * Acceptance: przełączenie krainy w panelu Mapa zmienia „wkrótce"↔„grywalne" na stronie
 * bez ręcznej edycji swiat.json; `available_override` wygrywa ze stanem gry.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "admin", password: "admin" },
  });
  if (r.ok()) return (await r.json()).token;
  const r2 = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r2.ok(), "dev-login nie odpowiada 200").toBeTruthy();
  return (await r2.json()).token;
}

async function badges(page) {
  // Query-param cache-bust: bez niego kolejne goto na ten sam URL różni się tylko
  // hashem i przeglądarka nie przeładowuje strony — karty zostają z poprzedniego stanu.
  await page.goto(`/?t=${Date.now()}#swiat`);
  await page.waitForFunction(
    () => document.querySelectorAll("#krainy-list .kraina").length > 0,
    null, { timeout: 15000 },
  );
  // Karty renderują się z data/swiat.json + /api/showcase/regions — chwila na merge.
  await page.waitForTimeout(600);
  return page.evaluate(() =>
    Object.fromEntries([...document.querySelectorAll("#krainy-list .kraina")].map((a) => [
      a.querySelector("h3")?.textContent?.trim(),
      a.querySelector(".play-badge, .lock-badge")?.textContent?.trim(),
    ])),
  );
}

test("REGRESSION #1484 — /api/showcase/regions wystawia stan krain", async ({ page }) => {
  const r = await page.request.get("/api/showcase/regions");
  expect(r.ok(), "GET /api/showcase/regions nie odpowiada 200").toBeTruthy();
  const { regions } = await r.json();
  expect(Array.isArray(regions) && regions.length).toBeTruthy();
  for (const reg of regions) {
    expect(typeof reg.available, `kraina ${reg.key} bez flagi available`).toBe("boolean");
  }
  expect(regions.some((x) => x.available), "żadna kraina nie jest grywalna").toBeTruthy();
});

test("REGRESSION #1484 — wizytówka pokazuje krainy live jako grywalne", async ({ page }) => {
  const { regions } = await (await page.request.get("/api/showcase/regions")).json();
  const shown = await badges(page);
  for (const reg of regions) {
    const badge = shown[reg.label];
    if (!badge) continue; // kraina spoza wizytówki — nie nasza sprawa
    expect(badge, `rozjazd dla ${reg.label}: gra=${reg.available ? "live" : "nie-live"}`)
      .toBe(reg.available ? "grywalne" : "wkrótce");
  }
});

test("REGRESSION #1484 — przełącznik krainy zmienia badge na wizytówce", async ({ page }) => {
  const ah = { Authorization: `Bearer ${await adminToken(page)}` };
  const { regions } = await (await page.request.get("/api/showcase/regions")).json();
  // Krainę startową (kresy) zostawiamy w spokoju — flip robimy na innej.
  const target = regions.find((x) => x.key !== "kresy" && !x.available);
  test.skip(!target, "brak krainy nie-live do przełączenia");

  try {
    const up = await page.request.patch(`/api/admin/regions/${target.key}/status`, {
      headers: ah, data: { status: "live" },
    });
    expect(up.ok()).toBeTruthy();
    expect((await up.json()).showcase_synced, "lustro wizytówki nie zostało odświeżone").toBe(true);

    const after = await badges(page);
    expect(after[target.label], `${target.label} nadal „wkrótce" po udostępnieniu`).toBe("grywalne");
  } finally {
    // Przywróć stan i zdejmij override (wraca kanon pliku krainy).
    await page.request.patch(`/api/admin/regions/${target.key}/status`, {
      headers: ah, data: { status: "coming" },
    });
    await page.request.patch(`/api/admin/regions/${target.key}/status`, {
      headers: ah, data: { status: null },
    });
  }

  const restored = await badges(page);
  expect(restored[target.label], "badge nie wrócił po ukryciu krainy").toBe("wkrótce");
});
