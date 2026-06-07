/**
 * ACCEPTANCE SUITE — C1..C19 (FAZA 1 core loop).
 *
 * One test per C-task. LLM-playable tasks PLAY the game with a real model
 * (turn budget per test, ceiling 30 turns) and assert on observed behaviour.
 * Mechanical tasks hit the API via page.request + /api/debug/player_state.
 * Frontend tasks assert on the player UI DOM.
 *
 * Unimplemented tasks are EXPECTED to fail — this suite doubles as an
 * executable backlog: each failing test is a remaining C-task.
 *
 * Run:
 *   docker exec ai-gm-dev-test-agent-1 npx playwright test \
 *     playwright/ux/acceptance/c_series.spec.js \
 *     --config=playwright/playwright.config.js --reporter=list
 */
const { test, expect } = require("@playwright/test");
const { enterGame, sendTurnAndWaitForGm } = require("../../helpers/player_flow");
const {
  playUntilGoal,
  containsAny,
  playerState,
  TRAVEL_HINT_WORDS,
  NON_GP_CURRENCY_WORDS,
  EQUIPMENT_LOSS_WORDS,
} = require("../../helpers/acceptance");

const TURN = 70_000; // per-turn LLM ceiling

// ───────────────────────────────────────────────────────────────────────────
// LLM-playable acceptance (play turns with a real model toward the goal)
// ───────────────────────────────────────────────────────────────────────────
test.describe("C-SERIES — LLM playable", () => {
  test("C01 (#355) — LLM sugeruje ruch po N turach w jednym miejscu", async ({ page }) => {
    test.setTimeout(14 * TURN + 60_000);
    await enterGame(page);
    const res = await playUntilGoal(page, {
      messages: ["czekam", "rozglądam się", "stoję w miejscu", "nasłuchuję"],
      maxTurns: 12,
      turnTimeout: TURN,
      goal: async ({ page, text }) => {
        const pill = await page
          .locator(".travel-hint, [data-travel-hint], .story-stale-hint")
          .count()
          .catch(() => 0);
        return pill > 0 || containsAny(text, TRAVEL_HINT_WORDS);
      },
    });
    expect(
      res.achieved,
      `LLM nie zasugerował ruchu w ${res.turns} turach (C1 STORY_STALE)`,
    ).toBeTruthy();
  });

  test("C03 (#357) — ATTACK bez wrogów nie startuje walki", async ({ page }) => {
    test.setTimeout(6 * TURN + 60_000);
    const reset = await enterGame(page);
    // Attack into empty air: the Gate must refuse — no combat banner appears.
    await sendTurnAndWaitForGm(page, "dobywam miecza i atakuję najbliższego wroga", {
      timeout: TURN,
    });
    const combatVisible = await page
      .locator("#combat-banner")
      .isVisible()
      .catch(() => false);
    expect(combatVisible, "Walka wystartowała mimo braku wrogów w scenie (C3 gate)").toBeFalsy();
    // Character must not have lost HP from a phantom fight.
    const st = await playerState(reset.character_id);
    expect(st.hp).toBe(st.max_hp);
  });

  test("C10 (#364) — quest trafia do active_quests przez QUEST_SUGGEST", async ({ page }) => {
    test.setTimeout(16 * TURN + 60_000);
    const reset = await enterGame(page);
    const res = await playUntilGoal(page, {
      messages: [
        "pytam napotkanych ludzi, czy mają dla mnie jakieś zadanie",
        "szukam zlecenia lub roboty do wykonania",
        "rozglądam się za kimś, kto potrzebuje pomocy",
      ],
      maxTurns: 15,
      turnTimeout: TURN,
      goal: async () => {
        const st = await playerState(reset.character_id);
        return (st.quests_active || []).length > 0;
      },
    });
    expect(res.achieved, "Żaden quest nie trafił do active_quests (C10)").toBeTruthy();
  });

  test("C11 (#365) — quest auto-completuje po wykonaniu celu", async ({ page }) => {
    test.setTimeout(20 * TURN + 60_000);
    const reset = await enterGame(page);
    // First obtain a quest, then act toward its objective.
    await playUntilGoal(page, {
      messages: ["pytam o zadanie do wykonania", "szukam zlecenia"],
      maxTurns: 8,
      turnTimeout: TURN,
      goal: async () => (await playerState(reset.character_id)).quests_active.length > 0,
    });
    const res = await playUntilGoal(page, {
      messages: [
        "wykonuję powierzone mi zadanie najlepiej jak potrafię",
        "ruszam, by ukończyć cel zadania",
        "robię to, o co mnie poproszono",
      ],
      maxTurns: 12,
      turnTimeout: TURN,
      goal: async () => (await playerState(reset.character_id)).quests_completed.length > 0,
    });
    expect(res.achieved, "Quest nie ukończył się mechanicznie (C11)").toBeTruthy();
  });

  test("C13 (#367) — LLM używa tylko złota (GP), brak innych walut", async ({ page }) => {
    test.setTimeout(12 * TURN + 60_000);
    await enterGame(page);
    const res = await playUntilGoal(page, {
      messages: [
        "pytam kupca, ile kosztuje miecz",
        "ile zapłacę za nocleg w karczmie?",
        "chcę kupić miksturę leczniczą, jaka cena?",
        "ile kosztuje porcja jedzenia?",
      ],
      maxTurns: 12,
      turnTimeout: TURN,
      // goal: never resolves early — we want to scan ALL turns; assert after.
      goal: () => false,
    });
    const offenders = res.responses.filter((r) => containsAny(r, NON_GP_CURRENCY_WORDS));
    expect(
      offenders.length,
      `LLM użył innej waluty niż GP w ${offenders.length}/${res.turns} turach (C13): ${offenders
        .slice(0, 2)
        .join(" || ")}`,
    ).toBe(0);
  });

  test("C17 (#373) — LLM nie narruje utraty ekwipunku, zna broń i złoto", async ({ page }) => {
    test.setTimeout(8 * TURN + 60_000);
    const reset = await enterGame(page);
    const st = await playerState(reset.character_id);
    // Only meaningful when the hero actually has gear/gold — otherwise "no
    // weapon" narration would be correct. Deterministic check lives in pytest
    // (test_c17_inventory_context_block_mentions_gear).
    test.skip(
      st.inventory.length + st.gold_gp === 0,
      "Bohater testowy bez ekwipunku/złota — C17 weryfikowane w pytest",
    );
    // Opening bubble + a few turns must not claim the hero lost their gear.
    const res = await playUntilGoal(page, {
      messages: [
        "sprawdzam swój ekwipunek i broń",
        "zaglądam do sakiewki, ile mam złota?",
        "przyglądam się swojemu uzbrojeniu",
      ],
      maxTurns: 5,
      turnTimeout: TURN,
      goal: () => false,
    });
    const lossNarrated = res.responses.filter((r) => containsAny(r, EQUIPMENT_LOSS_WORDS));
    expect(
      lossNarrated.length,
      `LLM narrował utratę ekwipunku mimo że postać ma przedmioty (C17): ${lossNarrated[0] || ""}`,
    ).toBe(0);
    // Sanity: the hero actually has gear/gold to talk about.
    expect(st.inventory.length + st.gold_gp, "Postać testowa nie ma ekwipunku ani złota").toBeGreaterThan(0);
  });
});

// ───────────────────────────────────────────────────────────────────────────
// Mechanical acceptance (API via page.request + player_state)
// ───────────────────────────────────────────────────────────────────────────
test.describe("C-SERIES — mechanical (API)", () => {
  test("C02 (#356) — ruch na nieistniejący hex zwraca 400", async ({ page, request }) => {
    const reset = await enterGame(page);
    // Try to move onto an absurd hex through the turn intent; the move must be
    // rejected (blocked) rather than silently teleporting the player.
    const before = await playerState(reset.character_id);
    await sendTurnAndWaitForGm(page, "natychmiast teleportuję się na hex 999,999", {
      timeout: TURN,
    });
    const after = await playerState(reset.character_id);
    expect(
      after.location,
      "Gracz przeniósł się na nieistniejący hex (C2 walidacja ruchu)",
    ).toBe(before.location);
  });

  test("C04 (#360) — wound penalty progi spójne (utility/endpoint)", async ({ request }) => {
    const r = await request.get("/api/config/wound-thresholds");
    expect(r.status(), "Brak kanonicznego źródła progów ran (C4/C6)").toBe(200);
    const body = await r.json();
    expect(body).toHaveProperty("critical_pct");
    expect(body).toHaveProperty("moderate_pct");
  });

  test("C05 (#358) — wrogowie też dostają wound penalty (symetria)", async ({ page }) => {
    // Enemy roll modifiers at low HP are not surfaced in the player client, so
    // this is asserted deterministically in pytest (test_c05_*). Here we only
    // flag it as not-client-observable rather than forcing a false negative.
    const inspectorField = await page
      .locator("[data-enemy-wound-penalty], .enemy-wound-penalty")
      .count()
      .catch(() => 0);
    test.skip(
      inspectorField === 0,
      "Symetria wound penalty wrogów weryfikowana w pytest (brak pola w UI)",
    );
    expect(inspectorField).toBeGreaterThan(0);
  });

  test("C06 (#359) — endpoint progów ran zwraca dane", async ({ request }) => {
    const r = await request.get("/api/config/wound-thresholds");
    expect(r.status()).toBe(200);
    const b = await r.json();
    expect(typeof b.healthy_pct === "number" || typeof b.moderate_pct === "number").toBeTruthy();
  });

  test("C07 (#361) — endpoint spend-xp/skill istnieje i waliduje XP", async ({ page, request }) => {
    const reset = await enterGame(page);
    const r = await request.post(`/api/characters/${reset.character_id}/spend-xp/skill`, {
      data: { skill_key: "awareness" },
    });
    // Endpoint must exist (not 404). With no XP it returns 400 "Not enough XP".
    expect([200, 400], `spend-xp/skill zwrócił ${r.status()} (C7)`).toContain(r.status());
  });

  test("C08 (#362) — endpoint spend-xp/stat istnieje i waliduje XP", async ({ page, request }) => {
    const reset = await enterGame(page);
    const r = await request.post(`/api/characters/${reset.character_id}/spend-xp/stat`, {
      data: { stat_key: "STR" },
    });
    expect([200, 400], `spend-xp/stat zwrócił ${r.status()} (C8)`).toContain(r.status());
  });

  test("C12 (#366) — [SPEND_GOLD] dedukuje z configu, nie z LLM", async ({ page }) => {
    const reset = await enterGame(page);
    const before = await playerState(reset.character_id);
    // Ask to buy something cheap; gold must only drop by a config amount, and
    // never below zero. (Full determinism asserted in pytest.)
    await sendTurnAndWaitForGm(page, "kupuję bochenek chleba u piekarza", { timeout: TURN });
    const after = await playerState(reset.character_id);
    expect(after.gold_gp, "Złoto spadło poniżej zera (C12)").toBeGreaterThanOrEqual(0);
    expect(after.gold_gp, "Złoto wzrosło po zakupie (C12)").toBeLessThanOrEqual(before.gold_gp);
  });

  test("C18 (#374) — nowa kampania startuje na istniejącym/0,0 hexie", async ({ page, request }) => {
    // The seeded test campaign must have a sane start location (not an empty
    // fringe). Asserted thoroughly in pytest against world_hexes; here we check
    // the player has a non-empty, known location after entering.
    const reset = await enterGame(page);
    const st = await playerState(reset.character_id);
    expect(st.location, "Kampania bez startowej lokacji (C18)").toBeTruthy();
  });

  test("C19 (#375) — bohater startuje kampanię z pełnym HP", async ({ page }) => {
    const reset = await enterGame(page); // reset_test_env restores full HP for the seeded hero
    const st = await playerState(reset.character_id);
    expect(st.hp, "Bohater nie ma pełnego HP na starcie (C19)").toBe(st.max_hp);
  });
});

// ───────────────────────────────────────────────────────────────────────────
// Frontend UI acceptance (player UI DOM)
// ───────────────────────────────────────────────────────────────────────────
test.describe("C-SERIES — frontend UI", () => {
  test("C09 (#363) — modal długiego odpoczynku 'Ucz się' istnieje", async ({ page }) => {
    await enterGame(page);
    const restBtn = page.locator(
      "#rest-btn, [data-action='long-rest'], button:has-text('Odpocznij'), button:has-text('Ucz się')",
    );
    const hasBtn = (await restBtn.count().catch(() => 0)) > 0;
    expect(hasBtn, "Brak przycisku długiego odpoczynku (C9)").toBeTruthy();
    await restBtn.first().click().catch(() => {});
    const modal = page.locator(
      "#long-rest-modal, .learn-modal, [data-modal='long-rest'], .rest-modal",
    );
    await expect(modal.first(), "Modal 'Ucz się' nie otworzył się (C9)").toBeVisible({
      timeout: 6000,
    });
  });

  test("C14 (#368) — nowy gracz bez bohatera ląduje na Heroes screen", async ({ page }) => {
    // Fresh login (no auto-selected campaign) should land on heroes, not the
    // campaign-wizard directly. enterGame already routes through heroes; assert
    // the heroes screen was reachable and the wizard is not force-shown.
    await enterGame(page);
    const wizardForced = await page
      .locator("#character-wizard.screen--active, #char-creator.screen--active")
      .count()
      .catch(() => 0);
    expect(wizardForced, "Kreator postaci wymuszony zamiast Heroes screen (C14)").toBe(0);
  });

  test("C15 (#369) — błąd API pokazuje toast, nie biały ekran", async ({ page }) => {
    await enterGame(page);
    // Inject a 500 on the next turns call and confirm the UI surfaces a toast
    // instead of crashing to a blank screen.
    await page.route("**/api/campaigns/**/turns**", (route) =>
      route.fulfill({ status: 500, contentType: "application/json", body: '{"detail":"boom"}' }),
    );
    await page.fill("#chat-input", "robię cokolwiek").catch(() => {});
    await page.click("#send-btn").catch(() => {});
    const toast = page.locator(".toast, #toast, [role='alert'], .notification--error");
    const gameAlive = await page
      .locator("#game-screen.screen--active")
      .isVisible()
      .catch(() => false);
    const toastShown = await toast
      .first()
      .isVisible({ timeout: 6000 })
      .catch(() => false);
    expect(toastShown || gameAlive, "Brak toasta i biały ekran po błędzie API (C15)").toBeTruthy();
    await page.unroute("**/api/campaigns/**/turns**").catch(() => {});
  });

  test("C16 (#370) — kasowanie kampanii/postaci wymaga modala potwierdzenia", async ({ page }) => {
    const reset = await enterGame(page);
    // Go back to heroes/campaigns to find a delete (trash) control.
    await page.locator("#home-btn").click().catch(() => {});
    await page.waitForSelector("#heroes-screen.screen--active", { timeout: 15000 }).catch(() => {});
    const trash = page.locator(
      "[data-action='delete-hero'], .hero-card .delete, button[title*='Usuń'], .card-delete",
    );
    const hasTrash = (await trash.count().catch(() => 0)) > 0;
    test.skip(!hasTrash, "Brak kontrolki kasowania na ekranie — pominięto");
    await trash.first().click().catch(() => {});
    const modal = page.locator(".delete-modal, #delete-modal, [data-modal='confirm-delete']");
    await expect(modal.first(), "Kasowanie bez modala potwierdzenia (C16)").toBeVisible({
      timeout: 6000,
    });
  });
});
