/**
 * REGRESSION #869 (FAZA L) — Klik w kafel mapy lochu wykonuje sekwencję ruchów (pathfinding).
 * Acceptance: klient liczy BFS po OTWARTYCH drzwiach przez ODKRYTE kafle do celu,
 * nigdy nie trasuje do mgły (?), zwraca listę kierunków N|S|E|W.
 *
 * Test deterministyczny: ładuje player UI, wstrzykuje znany graf, woła window.dungeonBfsPath
 * i sprawdza wyliczone trasy. Bez LLM, bez stanu serwera. Pełny przebieg klik→marsz
 * weryfikowany ręcznie na telefonie (mapa lochu = ekran mobilny).
 */
const { test, expect } = require("@playwright/test");

// Graf testowy:
//   A(entry, visited) --E--> B(visited) --E--> C(visited)   [trasa A→C = E,E]
//   A --N--> D(FOG, !visited)                                [cel w mgle = null]
//   B --N--> X(!visited) --E--> Z(visited)                   [Z osiągalne tylko przez X mgłę = null]
const GRAPH_NODES = {
  A: { position: [0, 0], visited: true,  doors_open: { E: "B", N: "D" } },
  B: { position: [1, 0], visited: true,  doors_open: { W: "A", E: "C", N: "X" } },
  C: { position: [2, 0], visited: true,  doors_open: { W: "B" } },
  D: { position: [0, 1], visited: false, doors_open: { S: "A" } },
  X: { position: [1, 1], visited: false, doors_open: { S: "B", E: "Z" } },
  Z: { position: [2, 1], visited: true,  doors_open: { W: "X" } },
};

test("REGRESSION #869 — dungeonBfsPath liczy trasę przez odkryte kafle, pomija mgłę", async ({ page }) => {
  await page.goto("/");
  // app.js parsuje się po załadowaniu strony — funkcja musi być globalna (window.*)
  await page.waitForFunction(() => typeof window.dungeonBfsPath !== "undefined", null, { timeout: 15000 })
    .catch(() => {});

  const isFn = await page.evaluate(() => typeof window.dungeonBfsPath === "function");
  expect(isFn, "window.dungeonBfsPath musi istnieć jako funkcja (#869)").toBeTruthy();

  const r = await page.evaluate((nodes) => {
    const bfs = window.dungeonBfsPath;
    return {
      aToC: bfs(nodes, "A", "C"),     // ['E','E']
      aToB: bfs(nodes, "A", "B"),     // ['E']
      aToA: bfs(nodes, "A", "A"),     // [] (cel = aktualny węzeł)
      aToD: bfs(nodes, "A", "D"),     // null — D w mgle, nie trasujemy
      aToZ: bfs(nodes, "A", "Z"),     // null — Z osiągalne tylko przez mgłę X
    };
  }, GRAPH_NODES);

  expect(r.aToC, "A→C przez B = [E,E]").toEqual(["E", "E"]);
  expect(r.aToB, "A→B = [E]").toEqual(["E"]);
  expect(r.aToA, "A→A = [] (no-op)").toEqual([]);
  expect(r.aToD, "A→D (mgła) = null").toBeNull();
  expect(r.aToZ, "A→Z (trasa tylko przez mgłę) = null").toBeNull();
});
