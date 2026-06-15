/**
 * REGRESSION #655 (B8) — startowy zestaw maga L1: dane 4 czarów startowych istnieją i mają tier 1.
 * Grant + backfill (semantyka migracji) w pełni pokryte pytest test_issue655_b8_starter_spells.py (7/7).
 * Ten spec to kontrakt danych: katalog czarów wystawia 4 czary startowe (fire_bolt/minor_heal/
 * ward_of_iron/detect_magic), wszystkie tier 1, a obronny = ward_of_iron (NIE mage_armor tier 2 —
 * decyzja D-obronna 2026-06-15, spójność z bramką nauki L1 z B7).
 * Acceptance: GET /api/admin/spells zawiera 4 czary startowe B8, każdy tier==1.
 */
const { test, expect } = require("@playwright/test");

const B8_STARTER = ["fire_bolt", "minor_heal", "ward_of_iron", "detect_magic"];

async function adminToken(request) {
  const r = await request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), "admin dev-login demo/demo nie zwrócił 200").toBeTruthy();
  const body = await r.json();
  expect(body.token, "brak tokenu admina").toBeTruthy();
  return body.token;
}

test("REGRESSION #655 — 4 czary startowe maga B8 istnieją i są tier 1", async ({ request }) => {
  const token = await adminToken(request);
  const r = await request.get("/api/admin/spells", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "GET /api/admin/spells nie zwrócił 200").toBeTruthy();
  const body = await r.json();
  const items = body.items || [];
  const byKey = Object.fromEntries(items.map((s) => [s.key, s]));

  // Wszystkie 4 czary startowe istnieją w katalogu (fundament startowego zestawu).
  for (const key of B8_STARTER) {
    expect(byKey[key], `brak czaru startowego ${key} w katalogu`).toBeTruthy();
    expect(byKey[key].tier, `czar startowy ${key} nie jest tier 1`).toBe(1);
  }

  // Decyzja D-obronna: obronny w starcie = ward_of_iron (tier 1), NIE mage_armor (tier 2).
  expect(byKey["ward_of_iron"].tier, "ward_of_iron musi być tier 1").toBe(1);
  if (byKey["mage_armor"]) {
    expect(byKey["mage_armor"].tier, "mage_armor pozostaje tier 2 (poza startem)").toBe(2);
  }
});
