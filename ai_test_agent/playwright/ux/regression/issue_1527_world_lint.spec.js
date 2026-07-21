/**
 * REGRESSION #1527 (fala 4) — 🩺 Kontrola świata: lint zamiast cichej samonaprawy.
 * Acceptance: panel dostaje listę realnych rozjazdów świata, każdy z jednoznacznym
 * werdyktem „naprawialne / decyzja człowieka", plus kronikę napraw dopisywaną przy
 * starcie backendu. Reguła „usługa bez gospodarza" nie może krzyczeć o krainy
 * zamknięte (Czarnobór, Martwe Pustkowia).
 */
const { test, expect } = require("@playwright/test");

const LINT_RULES = [
  "service_without_host",
  "orphan_npc_assignment",
  "hex_points_to_missing_location",
  "pin_not_backed_by_canon",
  "broken_sublocation_parent",
  "illegal_flag_value",
  "duplicate_label_in_region",
];

async function adminToken(page) {
  const r = await page.request.post("/api/admin/dev-login", {
    data: { username: "demo", password: "demo" },
  });
  expect(r.ok(), `dev-login nie odpowiada 200 (#1527): ${r.status()}`).toBeTruthy();
  const body = await r.json();
  return body.token;
}

async function lintReport(page) {
  const token = await adminToken(page);
  const r = await page.request.get("/api/admin/world/lint", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "GET /api/admin/world/lint nie odpowiada 200 (#1527)").toBeTruthy();
  return r.json();
}

test("REGRESSION #1527 — lint świata zwraca realne rozjazdy w kontrakcie panelu", async ({ page }) => {
  const d = await lintReport(page);

  expect(Array.isArray(d.issues), "brak listy issues").toBeTruthy();
  expect(typeof d.total).toBe("number");
  expect(typeof d.fixable).toBe("number");
  expect(d.truncated === true || d.truncated === false).toBeTruthy();

  // Na dzisiejszej bazie DEV rozjazdów jest sporo — pusta lista = lint nie działa.
  expect(d.total, "lint nie wykrył ani jednego problemu na DEV (#1527)").toBeGreaterThan(0);

  for (const issue of d.issues) {
    expect(LINT_RULES, `nieznana reguła: ${issue.rule}`).toContain(issue.rule);
    expect(["error", "warning"]).toContain(issue.severity);
    expect(issue.id).toBe(`${issue.rule}:${issue.target}`);
    expect(typeof issue.fixable).toBe("boolean");
    expect(issue.label.length, "pusta etykieta problemu").toBeGreaterThan(0);
  }
});

test("REGRESSION #1527 — reguły treściowe nie mają guzika Napraw", async ({ page }) => {
  const d = await lintReport(page);
  const humanOnly = d.issues.filter(
    (i) => i.rule === "service_without_host" || i.rule === "duplicate_label_in_region"
  );
  for (const issue of humanOnly) {
    expect(issue.fixable, `${issue.rule} nie może być auto-naprawialne (#1527)`).toBeFalsy();
  }
});

test("REGRESSION #1527 — krainy zamknięte nie generują fałszywych alarmów", async ({ page }) => {
  const token = await adminToken(page);
  const regionsRes = await page.request.get("/api/admin/regions", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(regionsRes.ok(), "GET /api/admin/regions nie odpowiada 200 (#1527)").toBeTruthy();
  const { regions } = await regionsRes.json();
  const closed = new Set((regions || []).filter((r) => r.status !== "live").map((r) => r.key));
  expect(closed.size, "baza bez krain zamkniętych — test nic nie sprawdza").toBeGreaterThan(0);

  const d = await lintReport(page);
  const alarms = d.issues.filter(
    (i) => i.rule === "service_without_host" && closed.has(String(i.detail).match(/„(.+?)"/)?.[1])
  );
  expect(alarms.length, "usługowka w krainie 'coming' trafiła do lintu (#1527)").toBe(0);
});

test("REGRESSION #1527 — kronika napraw jest dostępna i ma kształt wpisu", async ({ page }) => {
  const token = await adminToken(page);
  const r = await page.request.get("/api/admin/world/lint/history", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), "GET /api/admin/world/lint/history nie odpowiada 200 (#1527)").toBeTruthy();
  const d = await r.json();
  expect(Array.isArray(d.entries)).toBeTruthy();
  for (const e of d.entries.slice(0, 5)) {
    expect(["startup_reconcile", "startup_migration", "manual_fix"]).toContain(e.source);
    expect(typeof e.rule).toBe("string");
    expect(typeof e.created_at).toBe("string");
  }
});

test("REGRESSION #1527 — licznik do plakietki zgadza się z listą", async ({ page }) => {
  const token = await adminToken(page);
  const [countRes, d] = await Promise.all([
    page.request.get("/api/admin/world/lint/count", {
      headers: { Authorization: `Bearer ${token}` },
    }),
    lintReport(page),
  ]);
  expect(countRes.ok(), "GET /api/admin/world/lint/count nie odpowiada 200 (#1527)").toBeTruthy();
  const { count } = await countRes.json();
  expect(count).toBe(d.total);
});

test("REGRESSION #1527 — naprawa nienaprawialnej reguły jest odrzucana (400)", async ({ page }) => {
  const token = await adminToken(page);
  const d = await lintReport(page);
  const humanOnly = d.issues.find((i) => i.fixable === false);
  if (!humanOnly) test.skip(true, "brak rozjazdu wymagającego decyzji człowieka");

  const r = await page.request.post("/api/admin/world/lint/fix", {
    headers: { Authorization: `Bearer ${token}` },
    data: { issue_id: humanOnly.id },
  });
  expect(r.status(), "panel nie może po cichu 'naprawiać' decyzji treściowych (#1527)").toBe(400);
});
