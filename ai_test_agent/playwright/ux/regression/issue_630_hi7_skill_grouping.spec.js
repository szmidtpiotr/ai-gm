/**
 * REGRESSION #630 (HI7) — Inspektor/Arkusz: grupowanie skilli (posiadane vs niewyuczone).
 * Skille z rankiem >=1 muszą być w grupie „Posiadane" NAD separatorem, a rank 0 w
 * „Niewyuczone" pod nim; każda grupa posortowana alfabetycznie.
 * Acceptance: dwa separatory w kolejności known→none; skille rank>=1 nad rank0.
 */
const { test, expect } = require("@playwright/test");

async function adminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), "dev-login nie zwrócił 200 (#630)").toBeTruthy();
  return (await r.json()).token;
}

// Bohater z OBIEMA grupami skilli (część rank>=1, część rank 0).
async function findMixedSkillHero(page, headers) {
  const list = await page.request.get("/api/admin/characters", { headers });
  const items = (await list.json()).items || [];
  for (const h of items) {
    const full = await page.request.get(`/api/admin/characters/${h.id}/full`, { headers });
    if (!full.ok()) continue;
    const skills = (await full.json()).skills || {};
    const vals = Object.values(skills);
    const known = vals.filter(v => (v || 0) >= 1).length;
    const none = vals.filter(v => (v || 0) < 1).length;
    if (known > 0 && none > 0) return h.id;
  }
  return null;
}

async function loginUi(page, token) {
  await page.addInitScript(t => {
    localStorage.setItem("aigm_admin_token", t);
    localStorage.setItem("aigm_admin_user", "demo");
  }, token);
}

test("REGRESSION #630 — skille pogrupowane: Posiadane nad Niewyuczonymi, posortowane", async ({ page }) => {
  const token = await adminToken(page);
  const headers = { Authorization: `Bearer ${token}` };
  const heroId = await findMixedSkillHero(page, headers);
  expect(heroId, "brak bohatera z obiema grupami skilli (#630)").toBeTruthy();

  await loginUi(page, token);
  await page.goto("/admin/#heroes");
  await page.waitForLoadState("networkidle");
  await page.evaluate(async id => {
    const m = await import("/admin/sections/heroes.js?v=39");
    await m.openInspector(id);
  }, heroId);

  await expect(page.locator("#hero-sheet-edit"), "Arkusz nie wyrenderowany (#630)").toBeVisible({ timeout: 15000 });

  // Kolejność separatorów w DOM: known → none.
  const sepOrder = await page.evaluate(() =>
    Array.from(document.querySelectorAll("[data-hi-skill-sep]")).map(e => e.getAttribute("data-hi-skill-sep"))
  );
  expect(sepOrder, "separatory grup skilli w złej kolejności (#630)").toEqual(["known", "none"]);

  // Każda grupa posortowana alfabetycznie + grupa known w całości nad none (po pozycji w DOM).
  const layout = await page.evaluate(() => {
    const rows = Array.from(document.querySelectorAll("[data-hi-skill-group]"));
    return rows.map(r => ({ group: r.getAttribute("data-hi-skill-group"), key: r.getAttribute("data-hi-skill-key") }));
  });
  const knownKeys = layout.filter(r => r.group === "known").map(r => r.key);
  const noneKeys = layout.filter(r => r.group === "none").map(r => r.key);
  expect(knownKeys.length, "brak skilli w grupie Posiadane (#630)").toBeGreaterThan(0);
  expect(noneKeys.length, "brak skilli w grupie Niewyuczone (#630)").toBeGreaterThan(0);
  // Posortowane alfabetycznie w obrębie grupy.
  expect(knownKeys, "grupa Posiadane niesortowana (#630)").toEqual([...knownKeys].sort());
  expect(noneKeys, "grupa Niewyuczone niesortowana (#630)").toEqual([...noneKeys].sort());
  // Wszystkie known przed wszystkimi none w kolejności DOM.
  const lastKnownIdx = layout.map(r => r.group).lastIndexOf("known");
  const firstNoneIdx = layout.map(r => r.group).indexOf("none");
  expect(lastKnownIdx, "grupa Posiadane nie jest w całości nad Niewyuczonymi (#630)").toBeLessThan(firstNoneIdx);
});
