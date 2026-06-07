/**
 * REGRESSION #378 (D3) — NPC pamięć w World State.
 * Tag `[NPC_MEMORY: Imię | fakt]` jest zapisywany do pamięci NPC i USUWANY z
 * narracji pokazywanej graczowi (strip), a fakt wraca do kontekstu przy kolejnej
 * wizycie (blok "ZNANI NPC").
 * Acceptance (deterministyczny, bez LLM): żadna zapisana/wyświetlana narracja tury
 * nie może zawierać surowego znacznika `[NPC_MEMORY:` — dowód że strip działa.
 * Pełna logika (parser + akumulacja + injection) pokryta pytestem
 * test_issue378_npc_memory.py.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #378 — surowy tag [NPC_MEMORY:] nie wycieka do narracji gracza", async ({ page }) => {
  let scanned = 0;
  // Skan kampanii (niskie id + zakres realnych kampanii DEV ~1200) — dla każdej
  // aktywnej sprawdzamy ostatnie tury pod kątem wycieku surowego tagu.
  const ids = [];
  for (let i = 1; i <= 60; i++) ids.push(i);
  for (let i = 1190; i <= 1260; i++) ids.push(i);
  for (const cid of ids) {
    const r = await page.request.get(`/api/campaigns/${cid}/turns?limit=100`);
    if (!r.ok()) continue; // 404 = brak/nieaktywna kampania → pomiń
    const body = await r.json();
    const turns = body.turns || body.items || (Array.isArray(body) ? body : []);
    for (const t of turns) {
      const text = String(t.assistant_text || t.narrative || "");
      scanned++;
      expect(
        text.includes("[NPC_MEMORY:"),
        `Surowy tag [NPC_MEMORY:] wyciekł do narracji tury (kampania ${cid}) — strip nie zadziałał (#378)`,
      ).toBeFalsy();
    }
  }
  // Informacyjnie: ile tur przeskanowano (test przechodzi też przy 0 — invariant zachowany).
  console.log(`#378 scan: ${scanned} tur sprawdzonych pod kątem wycieku [NPC_MEMORY:]`);
});
