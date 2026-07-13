/**
 * WALKA-T5-FIX-a2 (#1360) — trwały latch „widziane" per combat_id.
 *
 * Karty overlayowe walki (inicjatywa #1356, pojawienie wroga #1344) mają wyskoczyć
 * RAZ na walkę. Wcześniej pamiętał to `useRef<Set>` — pamięć ulotna, kasowana przy
 * odmontowaniu hooka. Po F5 w środku walki hook montował się z pustym setem i karta
 * wyskakiwała ponownie (dane dobre, moment zły).
 *
 * Źródłem prawdy jest `sessionStorage` (przeżywa F5, ginie po zamknięciu karty
 * przeglądarki — dokładnie zakres jednej rozgrywki). In-memory fallback tylko dla
 * środowisk, gdzie `sessionStorage` rzuca (tryb prywatny w części przeglądarek, SSR).
 */

const memoryFallback: Record<string, Set<number>> = {};

function fallbackStore(ns: string): Set<number> {
  return (memoryFallback[ns] ??= new Set());
}

/** Czy karta `ns` dla tej walki (`cid`) była już pokazana (przeżywa F5)? */
export function hasSeenCombat(ns: string, cid: number): boolean {
  try {
    return sessionStorage.getItem(`${ns}:${cid}`) === "1";
  } catch {
    return fallbackStore(ns).has(cid);
  }
}

/** Oznacz kartę `ns` dla tej walki (`cid`) jako pokazaną. */
export function markSeenCombat(ns: string, cid: number): void {
  try {
    sessionStorage.setItem(`${ns}:${cid}`, "1");
  } catch {
    fallbackStore(ns).add(cid);
  }
}
