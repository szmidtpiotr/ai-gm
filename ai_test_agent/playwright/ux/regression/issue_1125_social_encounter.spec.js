/**
 * REGRESSION #1125 (PT-D2) — Encountery społeczne w sub-lokacjach.
 * Weryfikuje kontrakt endpointu local-travel: odpowiedź zawiera pole `encounter`
 * (null gdy brak trafienia puli 0.20, albo obiekt z polem `kind` gdy trafi:
 * 'combat' | 'social' | 'combat_escalated'). Split 50/50 i logika kieszonkowca
 * są pokryte pytestem (test_issue1125_social_encounter.py) — tu pilnujemy, że
 * warstwa API nie regresuje kształtu odpowiedzi ruchu lokalnego.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #1125 — local-map endpoint kontrakt (has_local_map)", async ({ page }) => {
  // Local-map GET jest bezpieczny bez auth (proxy /api → backend).
  const r = await page.request.get("/api/campaigns/1/local-map");
  // Endpoint MUSI istnieć i nie sypać 500 (404 = brak sesji dla tej kampanii — OK).
  expect(r.status(), "local-map 5xx (#1125)").toBeLessThan(500);
  const body = await r.json();
  if (r.status() === 200) {
    // Kontrakt kształtu przy realnej sesji (ML #993 + PT-D2 #1125).
    expect(body).toHaveProperty("has_local_map");
    expect(body).toHaveProperty("hexes");
    expect(Array.isArray(body.hexes)).toBeTruthy();
  } else {
    expect(body).toHaveProperty("detail"); // 404 struktura błędu
  }
});

test("REGRESSION #1125 — local-travel zwraca pole encounter (nullable)", async ({ page }) => {
  // Nieistniejący hex → 404, ale endpoint MUSI istnieć (nie 405/500).
  const r = await page.request.post("/api/campaigns/1/local-travel", {
    data: { hex_id: -1 },
    headers: { "Content-Type": "application/json" },
  });
  // 404 (hex nie znaleziony) lub 200 z encounter — obie ścieżki OK,
  // liczy się że routing PT-D2 nie został zerwany.
  expect([200, 404], "local-travel routing zerwany (#1125)").toContain(r.status());
  if (r.status() === 200) {
    const body = await r.json();
    expect(body).toHaveProperty("encounter"); // null lub {kind, ...}
  }
});
