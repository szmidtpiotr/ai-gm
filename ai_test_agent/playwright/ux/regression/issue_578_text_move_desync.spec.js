/**
 * REGRESSION #578 (U30/U27) — mechaniczny ruch po hexach działa, a directional text-move
 * został wpięty w tor JSON /turns (parytet ze streamingiem).
 *
 * Ten spec sprawdza DETERMINISTYCZNY kontrakt mechaniki ruchu: POST /travel przesuwa
 * bohatera na sąsiedni hex (bez LLM). To jest ścieżka, w którą U30 kieruje ruch tekstowy
 * ("idę na północ") po naprawie #578. Samo wiązanie tekst→podróż oraz guard
 * `travel_narrated_without_move` są pokryte pytestem (zależą od LLM → niestabilne w E2E).
 *
 * Acceptance: /travel zwraca arrived_hex == cel dla sąsiada; runda tam-i-z-powrotem wraca
 * do hexa startowego (stan nieuszkodzony).
 */
const { test, expect } = require("@playwright/test");

const CAMPAIGN_ID = 74; // [TEST] Wojownik (id 2) na koncie Demo
const CHARACTER_ID = 2;

async function travel(page, target) {
  const r = await page.request.post(`/api/campaigns/${CAMPAIGN_ID}/travel`, {
    data: { character_id: CHARACTER_ID, target_hex: target },
  });
  expect(r.ok(), "endpoint /travel nie odpowiada 200 (#578)").toBeTruthy();
  return r.json();
}

test("REGRESSION #578 — /travel przesuwa hex na sąsiada i wraca (mechanika ruchu)", async ({ page }) => {
  // Ustal punkt startowy: przejdź na {1,0} (Brzezino na wspólnej mapie) — deterministyczny węzeł.
  const start = await travel(page, { q: 1, r: 0 });
  // Może być przerwane spotkaniem — ale hex i tak ma się przesunąć (ruch rozstrzygnięty).
  expect(start.arrived_hex, "brak arrived_hex w odpowiedzi /travel").toBeTruthy();
  expect(start.arrived_hex.q).toBe(1);
  expect(start.arrived_hex.r).toBe(0);

  // Ruch na sąsiada {2,0}.
  const east = await travel(page, { q: 2, r: 0 });
  expect(east.ok, `ruch na sąsiada odrzucony: ${east.error}`).toBeTruthy();
  expect(east.arrived_hex).toEqual({ q: 2, r: 0 });

  // Powrót na {1,0} — stan nieuszkodzony.
  const back = await travel(page, { q: 1, r: 0 });
  expect(back.arrived_hex).toEqual({ q: 1, r: 0 });
});
