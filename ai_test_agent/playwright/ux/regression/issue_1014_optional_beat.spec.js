/**
 * REGRESSION #1014 — Forge template authoring: flaga beatu `optional`.
 * Acceptance: zapis szablonu z beatem {summary, optional:true} przechowuje
 * `optional:true` w gm_plan_json ORAZ nadaje beatowi `beat_key`; beat-string
 * (legacy) defaultuje do optional:false (wsteczna zgodność).
 */
const { test, expect } = require("@playwright/test");

async function _login(page) {
  await page.goto("/admin/");
  const tok = await page.evaluate(async () => {
    const r = await fetch("/api/admin/dev-login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "demo", password: "demo" }),
    });
    const b = await r.json();
    return b.token;
  });
  expect(tok, "login token missing").toBeTruthy();
  return tok;
}

test("REGRESSION #1014 — optional beat persists + beat_key derived on template save", async ({ page }) => {
  const tok = await _login(page);
  const H = { "Content-Type": "application/json", "Authorization": "Bearer " + tok };

  const created = await page.request.post("/api/admin/forge/templates", {
    headers: H, data: { title: "TEST #1014 optional beat" },
  });
  expect(created.ok(), "POST /forge/templates nie zwrócił 2xx").toBeTruthy();
  const id = (await created.json()).id;

  try {
    const plan = {
      acts: [{
        number: 1, title: "Akt I", summary: "s",
        key_beats: [
          { summary: "Zbadaj opuszczoną wieżę", optional: true },
          "Pokonaj nekromantę",
        ],
      }],
      endings: [], key_npcs: [], key_locations: [],
    };
    const patched = await page.request.patch("/api/admin/forge/templates/" + id, {
      headers: H, data: { gm_plan_json: plan },
    });
    expect(patched.ok(), "PATCH szablonu nie zwrócił 2xx").toBeTruthy();

    const got = await page.request.get("/api/admin/forge/templates/" + id, { headers: H });
    expect(got.ok()).toBeTruthy();
    const beats = (await got.json()).gm_plan_json.acts[0].key_beats;

    expect(beats.every(b => b && typeof b === "object" && b.beat_key),
      "beat bez beat_key — normalizacja nie zadziałała (#1014)").toBeTruthy();
    expect(beats[0].optional, "beat opcjonalny stracił flagę (#1014)").toBe(true);
    expect(beats[1].optional, "beat-string błędnie oznaczony optional (#1014)").toBe(false);
  } finally {
    await page.request.delete("/api/admin/forge/templates/" + id, { headers: H }).catch(() => {});
  }
});
