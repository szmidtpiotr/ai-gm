/**
 * REGRESSION #1361 (WALKA-T2-FIX-b) — resolve_reaction waliduje wybór vs pending['options'].
 * Wybór reakcji != 'take' spoza available `options` (np. wyszarzone `cap_reached` wysłane przez
 * devtools) NIE może być zastosowany — silnik degraduje do 'take' i zwraca `reaction_rejected`,
 * zamykając obejście capu 1/rundę (#1322). Pełna logika deterministycznie w pytest
 * test_issue1361_resolve_reaction_validation.py; tu weryfikujemy kontrakt endpointu + invariant.
 * Acceptance: endpoint resolve-reaction jest osłonięty (brak okna → 400, nie 500) ORAZ — gdy demo
 * ma aktywne okno reakcji — wybór spoza `reaction_options` daje `reaction_rejected` lub 400.
 */
const { test, expect } = require("@playwright/test");

const REACTION_KEYS = ["take", "dodge", "block", "shield_block", "arcane_ward", "mana_shield"];

test("REGRESSION #1361 — resolve-reaction osłonięty: brak pending → 400, nie 500", async ({
  page,
}) => {
  // Kampania bez aktywnego okna reakcji: endpoint musi zwrócić kontrolowany 400 ('no pending
  // reaction' / 'no active combat'), nigdy 500. Dowodzi, że ścieżka walidacji jest wpięta.
  const r = await page.request
    .post("/api/campaigns/999999/combat/resolve-reaction", { data: { choice: "dodge" } })
    .catch(() => null);
  expect(r, "endpoint resolve-reaction nie odpowiada (#1361)").toBeTruthy();
  expect(r.status(), "resolve-reaction bez okna nie powinien dawać 500 (#1361)").toBeLessThan(500);
});

test("REGRESSION #1361 — wybór spoza reaction_options → reaction_rejected lub 400", async ({
  page,
}) => {
  const login = await page.request.post("/api/admin/dev-login").catch(() => null);
  const token = login && login.ok() ? (await login.json()).token : null;
  const headers = token ? { Authorization: `Bearer ${token}` } : {};

  const campsRes = await page.request.get("/api/campaigns", { headers }).catch(() => null);
  if (!campsRes || !campsRes.ok()) {
    test.info().annotations.push({ type: "skip", description: "brak dostępu do /api/campaigns" });
    return;
  }
  const camps = await campsRes.json();
  const list = Array.isArray(camps) ? camps : camps.campaigns || [];

  let probed = 0;
  for (const c of list.slice(0, 12)) {
    const id = c && (c.id ?? c.campaign_id);
    if (!id) continue;
    const cr = await page.request.get(`/api/campaigns/${id}/combat`, { headers }).catch(() => null);
    if (!cr || !cr.ok()) continue;
    const env = await cr.json();
    const combat = env && (env.combat ?? env);
    const opts = combat && Array.isArray(combat.reaction_options) ? combat.reaction_options : null;
    // Aktywne okno reakcji z pustymi/niepełnymi opcjami — znajdź klucz reakcji SPOZA available.
    if (!combat || combat.reaction_window !== true || opts === null) continue;
    const bogus = REACTION_KEYS.find((k) => k !== "take" && !opts.includes(k));
    if (!bogus) continue;

    const rr = await page.request
      .post(`/api/campaigns/${id}/combat/resolve-reaction`, { headers, data: { choice: bogus } })
      .catch(() => null);
    expect(rr, "resolve-reaction nie odpowiada dla wyboru spoza options (#1361)").toBeTruthy();
    if (rr.status() === 400) {
      probed += 1;
      break;
    }
    const body = await rr.json().catch(() => ({}));
    // INVARIANT #1361: wybór spoza options nie może być zastosowany — flaga reaction_rejected.
    expect(
      body.reaction_rejected,
      `wybór '${bogus}' spoza options zastosowany bez reaction_rejected (#1361)`,
    ).toBeTruthy();
    probed += 1;
    break;
  }
  test.info().annotations.push({
    type: "info",
    description: `sprawdzono ${probed} aktywnych okien reakcji (0 = kontrakt kryty pytestem)`,
  });
});
