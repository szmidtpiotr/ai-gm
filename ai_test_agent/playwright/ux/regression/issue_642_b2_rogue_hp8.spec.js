/**
 * REGRESSION #642 (B2) — Łotrzyk ma bazowe HP = 8 w kreatorze postaci.
 * Acceptance: kreator (app.js _wizardCalcHP) liczy rogue bazę 8 (mniej niż warrior 10,
 * więcej niż mag 6) — kreator pokazuje prawdziwą wartość, którą dostaje gotowa postać.
 */
const { test, expect } = require("@playwright/test");

test("REGRESSION #642 — kreator: rogue base HP 8, warrior 10, scholar 6", async ({ page }) => {
  // Pobierz źródło kreatora (app.js) tak jak przeglądarka gracza.
  const r = await page.request.get("/js/app.js?v=642-rogue-hp8-2026-06-15");
  expect(r.ok(), "app.js nie serwuje się (200) (#642)").toBeTruthy();
  const src = await r.text();

  // Wytnij ciało _wizardCalcHP — jedyne źródło HP pokazywanego w kreatorze.
  const m = src.match(/function _wizardCalcHP[\s\S]*?const base =([^;]+);/);
  expect(m, "_wizardCalcHP nie znaleziony w app.js (#642)").toBeTruthy();
  const baseExpr = m[1];

  // Kanon AK.2: warrior 10 > rogue 8 > scholar 6.
  expect(baseExpr, "rogue powinien mieć bazę 8 (#642)").toMatch(/rogue'\s*\?\s*8\b/);
  expect(baseExpr, "warrior zostaje 10 (#475 nietknięte)").toMatch(/warrior'\s*\?\s*10\b/);
  expect(baseExpr, "scholar zostaje 6").toMatch(/scholar'\s*\?\s*6\b/);
  // Pewność, że stara wartość rogue=10 zniknęła.
  expect(baseExpr).not.toMatch(/rogue'\s*\?\s*10\b/);

  // Etykieta karty wyboru Łotrzyka (pierwsze HP, które widzi gracz) też = 8.
  const card = src.match(/data-arch="rogue"[\s\S]*?archetype-bonus">([^<]+)</);
  expect(card, "karta archetypu rogue nie znaleziona (#642)").toBeTruthy();
  expect(card[1], "etykieta karty Łotrzyka musi pokazywać HP: 8 (#642)").toMatch(/HP:\s*8\b/);
  expect(card[1]).not.toMatch(/HP:\s*10\b/);
});
