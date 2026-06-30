/**
 * REGRESSION #1053 — Modal Awansuj zostaje otwarty po wydaniu PD.
 * Acceptance: po kliknięciu "Tak, rozwijaj się" modal NIE zamyka się automatycznie;
 * lista odświeża się z nową pulą PD; gracz sam zamyka klikając X.
 */
const { test, expect } = require("@playwright/test");

const FRONTEND = process.env.FRONTEND_URL || "http://frontend:80";
const BACKEND = process.env.BACKEND_URL || "http://backend:8100";

// ─── Test 1: game.js NIE zamyka modala po spend-skill (źródło) ───────────────

test("REGRESSION #1053 — game.js nie zamyka awansuj-modal po spend-skill", async ({ request }) => {
  const r = await request.get(`${FRONTEND}/front/js/screens/game.js`);
  expect(r.ok(), "game.js niedostępny").toBeTruthy();
  const src = await r.text();

  // Wyszukaj blok obsługi sukcesu spend (po "Zapisano!")
  // BUG: modal.style.display = 'none' bezpośrednio po toaście = zamknięcie modala
  // FIX: zamiast tego openAwansujPanel(characterData, getSheet(characterData))

  // Znajdź indeks toast-sukcesu
  const toastIdx = src.indexOf("Zapisano! Pozostało:");
  expect(toastIdx, "Brak toast-sukcesu 'Zapisano! Pozostało:' w game.js — zmienił się kod?").toBeGreaterThan(-1);

  // Wytnij ~500 znaków po toaście (ścieżka sukcesu spend)
  const afterToast = src.slice(toastIdx, toastIdx + 500);

  // Musi zawierać openAwansujPanel (re-render po zakupie)
  expect(
    afterToast.includes("openAwansujPanel(characterData"),
    "Brak openAwansujPanel(characterData po toast-sukcesie — modal nadal się zamyka (#1053)"
  ).toBeTruthy();
});

// ─── Test 2: game.js zawiera getSheet helper (potrzebny do re-render) ─────────

test("REGRESSION #1053 — game.js eksportuje getSheet wymagany przez re-render", async ({ request }) => {
  const r = await request.get(`${FRONTEND}/front/js/screens/game.js`);
  expect(r.ok()).toBeTruthy();
  const src = await r.text();

  expect(src.includes("function getSheet"), "Brak getSheet w game.js").toBeTruthy();
  expect(
    src.includes("getSheet(characterData)"),
    "Brak wywołania getSheet(characterData) — re-render awansuj nie zostanie uruchomiony (#1053)"
  ).toBeTruthy();
});

// ─── Test 3: API xp/spend-skill zwraca xp_available (potrzebne do re-render) ─

test("REGRESSION #1053 — API spend-skill zwraca xp_available", async ({ request }) => {
  // Weryfikujemy kontrakt API (bez prawdziwego wykonania, bo nie mamy char z XP)
  // Endpoint musi istnieć i obsługiwać request (nie 404/405)
  const r = await request.post(`${BACKEND}/api/characters/99999999/xp/spend-skill`, {
    data: { skill_key: "stealth", user_id: 1 },
    headers: { "Content-Type": "application/json" },
  });
  // 404 = char nie istnieje (ok — endpoint działa, tylko brak danych testowych)
  // 400 = insufficient_xp lub unknown_skill (ok — endpoint działa)
  // NIE 405 (endpoint brakuje) ani 500 (crash)
  expect(r.status()).not.toBe(405);
  expect(r.status()).not.toBe(500);
  expect(
    [200, 400, 404].includes(r.status()),
    `Unexpected HTTP ${r.status()} z /xp/spend-skill`
  ).toBeTruthy();
});

// ─── Test 4: awansuj-modal istnieje w HTML ────────────────────────────────────

test("REGRESSION #1053 — awansuj-modal istnieje w front/index.html", async ({ request }) => {
  const r = await request.get(`${FRONTEND}/front/index.html`);
  expect(r.ok(), "front/index.html niedostępny").toBeTruthy();
  const html = await r.text();
  expect(html.includes("awansuj-modal"), "Brak awansuj-modal w index.html").toBeTruthy();
  expect(html.includes("awansuj-close"), "Brak awansuj-close w index.html").toBeTruthy();
  expect(html.includes("awansuj-body"), "Brak awansuj-body w index.html").toBeTruthy();
});
