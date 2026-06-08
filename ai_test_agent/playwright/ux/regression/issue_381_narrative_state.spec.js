/**
 * REGRESSION #381 (D6) — Narracja: tagi, parsery, Narrative State.
 * Tagi [NARRATIVE_EVENT: key=..., note=...] i [NARRATIVE_SEED: key=..., hint=...]
 * są kumulowane w Narrative State (World State) i USUWANE z narracji pokazywanej
 * graczowi (strip); skrót wraca do kontekstu LLM (blok NARRATIVE STATE).
 * Acceptance (deterministyczny): żadna zapisana narracja tury nie zawiera surowego
 * znacznika [NARRATIVE_EVENT: ani [NARRATIVE_SEED:. Logika parserów + akumulacji
 * pokryta pytestem test_issue381_narrative_state.py.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #381 — surowe tagi narracyjne nie wyciekają do narracji gracza", async ({ page }) => {
  let scanned = 0;
  const ids = [];
  for (let i = 1; i <= 60; i++) ids.push(i);
  for (let i = 1190; i <= 1260; i++) ids.push(i);
  for (const cid of ids) {
    const r = await page.request.get(`/api/campaigns/${cid}/turns?limit=100`);
    if (!r.ok()) continue;
    const body = await r.json();
    const turns = body.turns || body.items || (Array.isArray(body) ? body : []);
    for (const t of turns) {
      const text = String(t.assistant_text || t.narrative || "");
      scanned++;
      expect(
        text.includes("[NARRATIVE_EVENT:") || text.includes("[NARRATIVE_SEED:"),
        `Surowy tag narracyjny wyciekł do narracji tury (kampania ${cid}) — strip nie zadziałał (#381)`,
      ).toBeFalsy();
    }
  }
  console.log(`#381 scan: ${scanned} tur sprawdzonych pod kątem wycieku tagów narracyjnych`);
});
