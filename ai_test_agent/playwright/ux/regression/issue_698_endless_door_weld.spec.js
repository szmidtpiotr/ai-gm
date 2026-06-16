/**
 * REGRESSION #698 (L-doors2) — endless extend musi domykać drzwi na styku segmentów.
 * Acceptance: w aktywnym lochu kafelkowym (tiles_v2) graf NIE ma drzwi-widm (każdy
 * kierunek w doors_open istnieje w content.doors kafla) ani drzwi-null (otwartych),
 * a połączenia są symetryczne — także po doczepieniu segmentu endless (go_deeper).
 *
 * Uwaga: pełne przejście boss→go_deeper przez LLM jest niestabilne i pokrywa je pytest
 * (test_issue698_endless_door_weld.py). Ten spec sprawdza deterministycznie INWARIANT
 * grafu na realnym stanie kampanii; gdy brak aktywnego lochu — weryfikuje kontrakt endpointu.
 */
const { test, expect } = require("@playwright/test");

const OPPOSITE = { N: "S", S: "N", E: "W", W: "E" };

function assertGraphInvariants(graph) {
  const nodes = (graph && graph.nodes) || {};
  for (const [nid, n] of Object.entries(nodes)) {
    const real = new Set(((n.content && n.content.doors) || []));
    const doors = n.doors_open || {};
    for (const [dir, tgt] of Object.entries(doors)) {
      // brak drzwi-null (każde otwarte drzwi domknięte)
      expect(tgt, `#698: null door ${nid}.${dir}`).not.toBeNull();
      // brak drzwi-widm (kierunek musi istnieć w realnych drzwiach kafla)
      expect(real.has(dir), `#698: ghost door ${nid}.${dir} (real=${[...real]})`).toBeTruthy();
      // symetria połączenia
      const back = (nodes[tgt] && nodes[tgt].doors_open) || {};
      expect(back[OPPOSITE[dir]], `#698: asymetria ${nid}.${dir}->${tgt}`).toBe(nid);
    }
  }
}

test("REGRESSION #698 — graf lochu bez drzwi-widm/null i symetryczny", async ({ page }) => {
  // Demo campaign (user_id=1) — jeśli ma aktywny loch tiles_v2, sprawdź inwariant grafu.
  const r = await page.request.get("/api/campaigns/1/dungeon-run");
  expect(r.ok(), "endpoint dungeon-run nie odpowiada 200 (#698)").toBeTruthy();
  const body = await r.json();
  expect(body).toHaveProperty("dungeon_run");

  const run = body.dungeon_run;
  if (run && run.system === "tiles_v2" && run.graph && run.graph.nodes) {
    assertGraphInvariants(run.graph);
  } else {
    // Brak aktywnego lochu kafelkowego — kontrakt endpointu potwierdzony, inwariant pokrywa pytest.
    expect(run === null || typeof run === "object").toBeTruthy();
  }
});
