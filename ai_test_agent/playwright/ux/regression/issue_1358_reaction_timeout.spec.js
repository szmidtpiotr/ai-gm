/**
 * REGRESSION #1358 (WALKA-T5-FIX-c) — timeout okna reakcji (8s) nie może być cichy.
 * Po wygaśnięciu okna ReactionModal odpala „take" automatycznie; fix dokłada jawny
 * komunikat i odróżnialną kartę („czas minął"). Logika jednostkowa: vitest
 * src/lib/combat_reaction_timeout.test.ts. Tu weryfikujemy deterministycznie, że
 * wdrożony bundle front-v2 (ŻAR) faktycznie NIESIE marker fixa — chroni przed
 * „poprawka w repo, ale nie w wdrożeniu / stary cache". Combat siedzi w leniwym
 * chunku Game-*.js (nie w index.html), więc podążamy za referencjami z entry chunka.
 * Acceptance: karta timeout zawiera dopisek „czas minął" (nie identyczna z ręcznym take).
 */
const { test, expect } = require("@playwright/test");

const chunkRefs = (txt) => [...txt.matchAll(/assets\/[A-Za-z0-9_-]+\.js/g)].map((m) => "/graj/" + m[0]);

test("REGRESSION #1358 — bundle front-v2 niesie marker timeout-take", async ({ page }) => {
  const idx = await page.request.get("/graj/");
  expect(idx.ok(), "/graj/ nie odpowiada 200 (#1358)").toBeTruthy();

  // Zbierz chunki z index.html + jeden poziom w głąb (entry → leniwe chunki, m.in. Game-*.js).
  const seen = new Set(chunkRefs(await idx.text()));
  for (const url of [...seen]) {
    const res = await page.request.get(url);
    if (res.ok()) chunkRefs(await res.text()).forEach((u) => seen.add(u));
  }
  expect(seen.size, "brak chunków JS front-v2").toBeGreaterThan(0);

  let found = false;
  for (const url of seen) {
    const res = await page.request.get(url);
    if (res.ok() && (await res.text()).includes("czas minął")) {
      found = true;
      break;
    }
  }
  expect(found, "wdrożony bundle nie zawiera markera czas-minął (#1358 nie wdrożony)").toBeTruthy();
});
