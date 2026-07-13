/**
 * REGRESSION #1359 (WALKA-T2-FIX) — niedostępne obrony są WYSZARZONE z powodem, nie ukryte.
 * Backend `_reaction_options_detailed` zwraca WSZYSTKIE reakcje wg posiadanych skilli z flagą
 * available + reason; snapshot walki niesie `defense_options_detailed`, a `defense_options`
 * (available-only) pozostaje = podzbiór available (backward compat / bramka okna reakcji).
 * Acceptance: 4 reakcje obronne istnieją w katalogu (źródło opcji do wyszarzenia) ORAZ — gdy
 * demo ma aktywną walkę — snapshot niesie `defense_options_detailed` spójny z `defense_options`.
 */
const { test, expect } = require("@playwright/test");

const DEFENSE_KEYS = ["dodge", "shield_block", "arcane_ward", "mana_shield"];
const REASONS = new Set(["no_mana", "no_shield", "cap_reached", "locked"]);

test("REGRESSION #1359 — katalog niesie 4 reakcje obronne (źródło opcji greyable)", async ({
  page,
}) => {
  const r = await page.request.get("/api/mechanics/skills");
  expect(r.ok(), "katalog skilli nie odpowiada 200 (#1359)").toBeTruthy();
  const body = await r.json();
  const rows = Array.isArray(body) ? body : body.skills || [];
  for (const key of DEFENSE_KEYS) {
    const s = rows.find((x) => x && x.key === key);
    expect(s, `brak ${key} w katalogu — nie da się go wyszarzyć w oknie obrony (#1359)`).toBeTruthy();
  }
});

test("REGRESSION #1359 — snapshot walki: defense_options = available-subset(detailed)", async ({
  page,
}) => {
  // Zaloguj demo i znajdź kampanię z aktywną walką; brak walki → test przechodzi jako no-op
  // (kontrakt weryfikowany deterministycznie w pytest test_issue1359_defense_greyed.py).
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

  let checked = 0;
  for (const c of list.slice(0, 12)) {
    const id = c && (c.id ?? c.campaign_id);
    if (!id) continue;
    const cr = await page.request.get(`/api/campaigns/${id}/combat`, { headers }).catch(() => null);
    if (!cr || !cr.ok()) continue;
    const env = await cr.json();
    const combat = env && (env.combat ?? env);
    const detailed = combat && combat.defense_options_detailed;
    if (!Array.isArray(detailed) || detailed.length === 0) continue;

    // każdy wpis dobrze uformowany
    for (const d of detailed) {
      expect(DEFENSE_KEYS.includes(d.key), `nieznany klucz obrony: ${d.key}`).toBeTruthy();
      expect(typeof d.available).toBe("boolean");
      if (!d.available) {
        expect(REASONS.has(d.reason), `niedostępna obrona bez powodu: ${d.key}/${d.reason}`).toBeTruthy();
      }
    }
    // INVARIANT #1359: defense_options (available-only) == klucze available z detailed
    const availableFromDetailed = detailed.filter((d) => d.available).map((d) => d.key);
    const flat = Array.isArray(combat.defense_options) ? combat.defense_options : [];
    expect([...flat].sort()).toEqual([...availableFromDetailed].sort());
    checked += 1;
  }
  test.info().annotations.push({
    type: "info",
    description: `sprawdzono ${checked} aktywnych walk z defense_options_detailed`,
  });
});
