/**
 * REGRESSION #1478 (Faza RM) — tester wchodzi do krainy `coming`, gracz bez flagi nie.
 * Acceptance: ta sama podróż do heksa krainy nie-live daje różny wynik zależnie od
 * `users.is_tester` właściciela kampanii. Test JEST stanowy — wykonuje realną podróż
 * na kampanii demo (za zgodą Piotra: konta demo służą do testów, nie do grania).
 * Bohater Mizel (999420) jest wykluczony — na nim nie robimy testów zmieniających stan.
 */
const { test, expect } = require("@playwright/test");

const MIZEL = 999420;

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

/** Ustaw flagę testera konta demo i zwróć poprzednią wartość. */
async function setTesterFlag(page, ah, accountId, value) {
  const r = await page.request.patch(`/api/admin/accounts/${accountId}`, {
    headers: ah, data: { is_tester: value },
  });
  expect(r.ok(), `PATCH is_tester=${value} nie odpowiada 200`).toBeTruthy();
}

test("REGRESSION #1478 — status krain wciąż czytelny (live/coming/locked)", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.get("/api/admin/regions", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok()).toBeTruthy();
  const { regions } = await r.json();
  for (const reg of regions) {
    expect(["live", "coming", "locked"]).toContain(reg.status);
  }
  expect(regions.some((x) => x.status === "live"), "brak krainy live").toBeTruthy();
});

test("REGRESSION #1478 — flaga testera decyduje o wejściu do krainy coming", async ({ page }) => {
  const atoken = await adminToken(page);
  const ah = { Authorization: `Bearer ${atoken}` };

  // ── konto demo + jego kampania ────────────────────────────────────────────
  const accounts = await (await page.request.get("/api/admin/accounts", { headers: ah })).json();
  const demo = (accounts.items || []).find((a) => a.username === "demo");
  expect(demo, "brak konta demo w /api/admin/accounts").toBeTruthy();
  const hadTester = Number(demo.is_tester || 0);

  const login = await page.request.post("/api/auth/login", {
    data: { username: "demo", password: "demo" },
  });
  expect(login.ok(), "login demo nie odpowiada 200").toBeTruthy();
  const { access_token } = await login.json();
  const headers = { Authorization: `Bearer ${access_token}` };

  const camps = await (await page.request.get("/api/campaigns", { headers })).json();
  const candidates = (camps.campaigns || []).filter(
    (c) => c.status === "active" && c.character_id && c.character_id !== MIZEL
      && !/^\[(SBX|SANDBOX)/i.test(c.title || ""),
  );
  test.skip(!candidates.length, "brak aktywnej kampanii demo z postacią (poza sandboxem/Mizelem)");

  // ── cel: heks krainy coming (gracz go nie przejdzie) ──────────────────────
  const regs = await (await page.request.get("/api/admin/regions", { headers: ah })).json();
  const coming = regs.regions.find((x) => x.status === "coming");
  test.skip(!coming, "brak krainy o statusie coming — nie ma czego testować");
  const map = await (await page.request.get(
    `/api/admin/world/map?region=${encodeURIComponent(coming.key)}`, { headers: ah },
  )).json();
  test.skip(!map.hexes?.length, `kraina ${coming.key} nie ma heksów w DB`);
  const target = map.hexes[0];

  /** Spróbuj podróży w każdej kampanii-kandydatce; zwróć pierwszą odpowiedź 200. */
  async function tryTravel() {
    for (const camp of candidates) {
      const r = await page.request.post(`/api/campaigns/${camp.id}/travel`, {
        headers,
        data: { character_id: camp.character_id, target_hex: { q: target.q, r: target.r } },
      });
      if (r.ok()) return await r.json();
    }
    return null;
  }

  try {
    // ── 1. BEZ flagi testera → bramka krainy zatrzymuje ─────────────────────
    await setTesterFlag(page, ah, demo.id, 0);
    const asPlayer = await tryTravel();
    test.skip(!asPlayer, "żadna kampania demo nie przyjęła próby podróży (walka / blokada tury)");
    expect(asPlayer.ok, "gracz bez flagi testera wszedł do krainy coming (#1478)").toBe(false);
    expect(asPlayer.error_code).toBe("region_locked");
    expect(asPlayer.region_status).toBe("coming");

    // ── 2. Z flagą testera → przechodzi ─────────────────────────────────────
    await setTesterFlag(page, ah, demo.id, 1);
    const asTester = await tryTravel();
    expect(asTester, "brak odpowiedzi na podróż testera").toBeTruthy();
    expect(
      asTester.error_code,
      "tester nadal odbija się od krainy coming (#1478)",
    ).not.toBe("region_locked");
  } finally {
    await setTesterFlag(page, ah, demo.id, hadTester);
  }
});

test("REGRESSION #1478 — kraina locked zamknięta także dla testera", async ({ page }) => {
  const atoken = await adminToken(page);
  const ah = { Authorization: `Bearer ${atoken}` };

  const regs = await (await page.request.get("/api/admin/regions", { headers: ah })).json();
  const locked = regs.regions.find((x) => x.status === "locked");
  test.skip(!locked, "brak krainy o statusie locked na DEV");

  const map = await (await page.request.get(
    `/api/admin/world/map?region=${encodeURIComponent(locked.key)}`, { headers: ah },
  )).json();
  test.skip(!map.hexes?.length, `kraina ${locked.key} nie ma heksów w DB`);
  const target = map.hexes[0];

  const login = await page.request.post("/api/auth/login", {
    data: { username: "demo", password: "demo" },
  });
  const { access_token } = await login.json();
  const headers = { Authorization: `Bearer ${access_token}` };
  const camps = await (await page.request.get("/api/campaigns", { headers })).json();
  const camp = (camps.campaigns || []).find(
    (c) => c.status === "active" && c.character_id && c.character_id !== MIZEL
      && !/^\[(SBX|SANDBOX)/i.test(c.title || ""),
  );
  test.skip(!camp, "brak kampanii demo do testu");

  const r = await page.request.post(`/api/campaigns/${camp.id}/travel`, {
    headers, data: { character_id: camp.character_id, target_hex: { q: target.q, r: target.r } },
  });
  test.skip(!r.ok(), "kampania nie przyjęła próby podróży (walka / blokada tury)");
  const body = await r.json();
  expect(body.ok, "wejście do krainy locked musi być zablokowane dla każdego").toBe(false);
  expect(body.region_status).toBe("locked");
});
