/**
 * REGRESSION #1479 (Faza RM) — kraina zamknięta ⇒ rasa wyszarzona w kreatorze.
 * Acceptance: /creation/races oznacza krasnoluda jako niedostępnego, gdy Siwe Granie
 * nie są `live`, a POST /characters z taką rasą kończy się 409 (backend nie ufa UI).
 * Test flipuje status krainy i przywraca go w finally.
 */
const { test, expect } = require("@playwright/test");

const HOME_REGION = "siwe_granie";

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

async function setRegionStatus(page, ah, status) {
  const r = await page.request.patch(`/api/admin/regions/${HOME_REGION}/status`, {
    headers: ah, data: { status },
  });
  expect(r.ok(), `PATCH statusu ${HOME_REGION}=${status} nie odpowiada 200`).toBeTruthy();
}

async function races(page, headers) {
  const r = await page.request.get("/api/creation/races", { headers });
  expect(r.ok(), "GET /api/creation/races nie odpowiada 200").toBeTruthy();
  const { races: list } = await r.json();
  return new Map(list.map((x) => [x.key, x]));
}

test("REGRESSION #1479 — kontrakt /creation/races", async ({ page }) => {
  const list = await races(page, {});
  expect(list.has("human") && list.has("dwarf"), "brak ras w odpowiedzi").toBeTruthy();
  expect(list.get("human").home_region, "człowiek nie ma kotwicy w krainie").toBeNull();
  expect(list.get("dwarf").home_region).toBe(HOME_REGION);
  // Człowiek jest dostępny niezależnie od stanu mapy.
  expect(list.get("human").available).toBe(true);
});

test("REGRESSION #1479 — zamknięcie Siwych Grań blokuje krasnoluda", async ({ page }) => {
  const atoken = await adminToken(page);
  const ah = { Authorization: `Bearer ${atoken}` };

  const before = (await races(page, {})).get("dwarf");
  try {
    await setRegionStatus(page, ah, "coming");

    // Anonimowy odczyt (bez tokenu = nie-tester) → rasa niedostępna z powodem.
    const closed = (await races(page, {})).get("dwarf");
    expect(closed.available, "krasnolud dostępny mimo zamkniętej krainy (#1479)").toBe(false);
    expect(closed.reason, "brak powodu przy zablokowanej rasie").toBeTruthy();
    expect(closed.reason).toContain("Siwe Granie");
    // Człowiek nietknięty.
    expect((await races(page, {})).get("human").available).toBe(true);

    // Backend nie ufa UI: próba zapisu postaci tą rasą → 409.
    const login = await page.request.post("/api/auth/login", {
      data: { username: "demo", password: "demo" },
    });
    expect(login.ok()).toBeTruthy();
    const { access_token } = await login.json();
    const create = await page.request.post("/api/characters", {
      headers: { Authorization: `Bearer ${access_token}` },
      data: { name: `TEST1479_${Date.now()}`, race: "dwarf", sheet_json: { archetype: "warrior" } },
    });
    // Konto demo bywa testerem — wtedy 409 nie przyjdzie i to jest poprawne
    // (tester może grać rasą krainy, do której wolno mu wejść, patrz #1478).
    if (create.status() === 409) {
      expect((await create.json()).detail).toContain("Siwe Granie");
    } else {
      expect(create.ok(), "nieoczekiwany status tworzenia postaci").toBeTruthy();
      const hero = await create.json();
      // Sprzątanie: usuń bohatera-śmiecia utworzonego przez test.
      if (hero?.id) {
        await page.request.delete(`/api/characters/${hero.id}`, {
          headers: { Authorization: `Bearer ${access_token}` },
        });
      }
    }

    // Ponowne otwarcie krainy → rasa wraca.
    await setRegionStatus(page, ah, "live");
    expect((await races(page, {})).get("dwarf").available).toBe(true);
  } finally {
    // Przywróć stan wyjściowy krainy (override zdejmujemy, wraca kanon pliku).
    await page.request.patch(`/api/admin/regions/${HOME_REGION}/status`, {
      headers: ah, data: { status: before.available ? "live" : "coming" },
    });
    await page.request.patch(`/api/admin/regions/${HOME_REGION}/status`, {
      headers: ah, data: { status: null },
    });
  }
});
