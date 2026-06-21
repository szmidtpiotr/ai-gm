/**
 * REGRESSION #869 (FAZA L) — Klik w kafel mapy lochu wykonuje sekwencję ruchów (pathfinding).
 * Acceptance: klient liczy BFS po OTWARTYCH drzwiach przez ODKRYTE kafle; cel może być
 * PIERWSZYM kaflem mgły (granicznym) — ostatni hop jest odkrywający. Głęboka mgła
 * (trasa wymagałaby przejścia PRZEZ nieznane kafle) = null. Zwraca listę N|S|E|W.
 *
 * Test deterministyczny: ładuje player UI, wstrzykuje znany graf, woła window.dungeonBfsPath
 * i sprawdza wyliczone trasy. Bez LLM, bez stanu serwera. Pełny przebieg klik→marsz
 * weryfikowany ręcznie na telefonie (mapa lochu = ekran mobilny).
 */
const { test, expect } = require("@playwright/test");

// Graf testowy:
//   A(v) --E--> B(v) --E--> C(v) --E--> F(FOG, graniczny) --E--> G(FOG, głęboki)
//   A --N--> D(FOG, bezpośredni sąsiad)
//   B --N--> X(FOG) --E--> Z(v)
const GRAPH_NODES = {
  A: { position: [0, 0], visited: true,  doors_open: { E: "B", N: "D" } },
  B: { position: [1, 0], visited: true,  doors_open: { W: "A", E: "C", N: "X" } },
  C: { position: [2, 0], visited: true,  doors_open: { W: "B", E: "F" } },
  F: { position: [3, 0], visited: false, doors_open: { W: "C", E: "G" } },  // pierwsza mgła za 2 znanymi
  G: { position: [4, 0], visited: false, doors_open: { W: "F" } },          // głęboka mgła
  D: { position: [0, 1], visited: false, doors_open: { S: "A" } },          // mgła = bezpośredni sąsiad
  X: { position: [1, 1], visited: false, doors_open: { S: "B", E: "Z" } },
  Z: { position: [2, 1], visited: true,  doors_open: { W: "X" } },          // visited, ale tylko przez mgłę X
};

test("REGRESSION #869 — dungeonBfsPath trasuje do pierwszego kafla mgły, blokuje głęboką mgłę", async ({ page }) => {
  await page.goto("/");
  // app.js parsuje się po załadowaniu strony — funkcja musi być globalna (window.*)
  await page.waitForFunction(() => typeof window.dungeonBfsPath !== "undefined", null, { timeout: 15000 })
    .catch(() => {});

  const isFn = await page.evaluate(() => typeof window.dungeonBfsPath === "function");
  expect(isFn, "window.dungeonBfsPath musi istnieć jako funkcja (#869)").toBeTruthy();

  const r = await page.evaluate((nodes) => {
    const bfs = window.dungeonBfsPath;
    return {
      aToC: bfs(nodes, "A", "C"),     // ['E','E']  — czysto po odkrytych
      aToB: bfs(nodes, "A", "B"),     // ['E']
      aToA: bfs(nodes, "A", "A"),     // []         — cel = aktualny węzeł
      aToD: bfs(nodes, "A", "D"),     // ['N']      — pierwsza mgła, bezpośredni sąsiad
      aToF: bfs(nodes, "A", "F"),     // ['E','E','E'] — pierwsza mgła za 2 znanymi kaflami
      aToG: bfs(nodes, "A", "G"),     // null       — głęboka mgła (trasa przez mgłę F)
      aToZ: bfs(nodes, "A", "Z"),     // null       — Z tylko przez mgłę X
    };
  }, GRAPH_NODES);

  expect(r.aToC, "A→C przez B = [E,E]").toEqual(["E", "E"]);
  expect(r.aToB, "A→B = [E]").toEqual(["E"]);
  expect(r.aToA, "A→A = [] (no-op)").toEqual([]);
  expect(r.aToD, "A→D (pierwsza mgła, sąsiad) = [N]").toEqual(["N"]);
  expect(r.aToF, "A→F (pierwsza mgła za 2 znanymi) = [E,E,E]").toEqual(["E", "E", "E"]);
  expect(r.aToG, "A→G (głęboka mgła) = null").toBeNull();
  expect(r.aToZ, "A→Z (trasa tylko przez mgłę X) = null").toBeNull();
});
