/**
 * REGRESSION #1134 (PT-D5) — guard_check różnicowany reputacją frakcji.
 * Acceptance: encounter społeczny `guard_check` istnieje w katalogu
 * `game_config_encounters` i rekord przenosi kolumnę `faction_tag` (hook, po którym
 * silnik pobiera reputację frakcji straży i różnicuje konsekwencję). Kontrakt danych
 * — deterministyczny, bez LLM.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(request) {
  const username = process.env.AI_TEST_PLAYER_USERNAME || "ai_test_player";
  const password = process.env.AI_TEST_PLAYER_PASSWORD || "demo";
  const r = await request.post("/api/admin/dev-login", {
    data: { username, password },
  });
  expect(r.ok(), "dev-login nie zwrócił 200 (#1134)").toBeTruthy();
  const body = await r.json();
  expect(body.token, "brak tokenu admina (#1134)").toBeTruthy();
  return body.token;
}

test("REGRESSION #1134 — guard_check w katalogu z kolumną faction_tag", async ({ request }) => {
  const token = await adminToken(request);
  const headers = { Authorization: `Bearer ${token}` };

  const r = await request.get("/api/admin/forge/encounters/catalog?kind=social", { headers });
  expect(r.ok(), "katalog social nie odpowiada 200 (#1134)").toBeTruthy();
  const body = await r.json();
  expect(body.ok).toBeTruthy();
  expect(Array.isArray(body.encounters)).toBeTruthy();

  const guard = body.encounters.find((e) => e.key === "guard_check");
  expect(guard, "brak encountera guard_check w katalogu (#1134)").toBeTruthy();

  // hook reputacji frakcji: rekord MUSI eksponować kolumnę faction_tag (może być null)
  expect(
    Object.prototype.hasOwnProperty.call(guard, "faction_tag"),
    "rekord guard_check nie eksponuje faction_tag (#1134)"
  ).toBeTruthy();
});
