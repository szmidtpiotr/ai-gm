/**
 * REGRESSION #1020 — Forge publish wymusza wzorzec "winnable premade".
 * Acceptance: publikacja szablonu (PATCH status=published) jest BLOKOWANA (422),
 * gdy plan nie jest grywalny do końca — brak endings[], krytyczny orphan-beat,
 * albo akt bez domykalnego beatu krytycznego. Plan winnable publikuje się (200).
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
    return (await r.json()).token;
  });
  expect(tok, "login token missing").toBeTruthy();
  return tok;
}

function _winnablePlan() {
  return {
    acts: [
      { number: 1, title: "Akt I", key_beats: [
        { summary: "Start", optional: false, narrative_close: true },
        { summary: "Poboczny", optional: true },
      ] },
      { number: 2, title: "Akt II", key_beats: [
        { summary: "Pokonaj bossa", optional: false, objective_type: "kill_enemy", objective_value: "boss" },
      ] },
      { number: 3, title: "Finał", key_beats: [
        { summary: "Domknij wątek", optional: false, narrative_close: true },
      ] },
    ],
    endings: [
      { id: "ending_primary", type: "primary", title: "Zwycięstwo", requirements: [] },
    ],
    key_npcs: [], key_locations: [],
  };
}

test("REGRESSION #1020 — publish blokowany dla planu nie-winnable, dozwolony dla winnable", async ({ page }) => {
  const tok = await _login(page);
  const H = { "Content-Type": "application/json", "Authorization": "Bearer " + tok };

  const created = await page.request.post("/api/admin/forge/templates", {
    headers: H, data: { title: "TEST #1020 winnable" },
  });
  expect(created.ok(), "POST /forge/templates nie zwrócił 2xx").toBeTruthy();
  const id = (await created.json()).id;

  try {
    // 1) plan bez endings → publish musi być 422
    const noEndings = _winnablePlan();
    delete noEndings.endings;
    const blocked = await page.request.patch("/api/admin/forge/templates/" + id, {
      headers: H, data: { gm_plan_json: noEndings, status: "published" },
    });
    expect(blocked.status(), "publish bez endings powinien być 422 (#1020)").toBe(422);
    const detail = JSON.stringify(await blocked.json()).toLowerCase();
    expect(detail.includes("winnable") || detail.includes("ending"),
      "422 nie wskazuje powodu winnable (#1020)").toBeTruthy();

    // 2) plan winnable → publish 200
    const ok = await page.request.patch("/api/admin/forge/templates/" + id, {
      headers: H, data: { gm_plan_json: _winnablePlan(), status: "published" },
    });
    expect(ok.ok(), "publish planu winnable powinien przejść 200 (#1020)").toBeTruthy();
  } finally {
    await page.request.delete("/api/admin/forge/templates/" + id, { headers: H }).catch(() => {});
  }
});
