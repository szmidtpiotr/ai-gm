/**
 * REGRESSION #720 (L-fix) — Popup "co wypadło z bossa" po zabiciu bossa lochu.
 * Acceptance: po pokonaniu bossa, PRZED modalem wyboru głębiej/wyjdź, pojawia się
 * popup-rewelacja (tryb tylko-pokaż, łup już przyznany server-side) z nazwami przedmiotów.
 * Weryfikuje deterministycznie: front bundle zawiera logikę reveal (pendingBossLoot/revealOnly),
 * przechwytuje data.dungeon_boss_loot, a endpoint walki w lochu istnieje (kontrakt, nie 410).
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

async function fetchAppJs(page, request) {
    await page.goto(`${BASE}/`);
    const appSrc = await page.evaluate(() => {
        const s = Array.from(document.querySelectorAll("script[src]"))
            .map(x => x.src)
            .find(x => x.includes("app.js"));
        return s || null;
    });
    expect(appSrc, "app.js musi być załadowany w index.html").toBeTruthy();
    const res = await request.get(appSrc);
    expect(res.ok(), `app.js musi się pobrać (${appSrc})`).toBeTruthy();
    return await res.text();
}

test("REGRESSION #720 — front bundle ma logikę reveal łupu bossa (pendingBossLoot + revealOnly)", async ({ page, request }) => {
    const js = await fetchAppJs(page, request);
    expect(js.includes("pendingBossLoot"), "app.js musi trzymać stan pendingBossLoot").toBeTruthy();
    expect(js.includes("revealOnly"), "showLootPopup musi wspierać tryb revealOnly (tylko-pokaż)").toBeTruthy();
});

test("REGRESSION #720 — front przechwytuje data.dungeon_boss_loot z odpowiedzi walki", async ({ page, request }) => {
    const js = await fetchAppJs(page, request);
    expect(
        js.includes("dungeon_boss_loot"),
        "app.js musi czytać data.dungeon_boss_loot (łup bossa z labelami)"
    ).toBeTruthy();
});

test("REGRESSION #720 — reveal popup pokazywany PRZED modalem wyboru głębiej/wyjdź", async ({ page, request }) => {
    const js = await fetchAppJs(page, request);
    // Kolejność w kodzie: showLootPopup(...,{revealOnly}) musi wystąpić przed showDungeonBossChoiceModal
    const idxReveal = js.indexOf("revealOnly: true");
    const idxChoice = js.indexOf("showDungeonBossChoiceModal");
    expect(idxReveal, "wywołanie revealOnly:true musi istnieć").toBeGreaterThan(-1);
    expect(idxChoice, "showDungeonBossChoiceModal musi istnieć").toBeGreaterThan(-1);
    expect(idxReveal, "reveal popup musi być wywołany przed modalem wyboru").toBeLessThan(idxChoice);
});

test("REGRESSION #720 — endpoint boss-choice istnieje (kontrakt reveal→modal, nie 410/404/405)", async ({ request }) => {
    const loginRes = await request.post(`${BASE}/api/auth/login`, {
        data: { username: "demo", password: "demo" },
    });
    expect(loginRes.ok(), "login demo musi zwrócić 200").toBeTruthy();
    const j = await loginRes.json();
    const token = j.token || j.access_token;

    // Po reveal łupu → modal wyboru → POST /dungeons/boss-choice. Endpoint musi istnieć.
    // Pusta kampania → 409 (brak aktywnego runu), ale NIE 404/405/410.
    const res = await request.post(`${BASE}/api/dungeons/boss-choice`, {
        headers: { Authorization: `Bearer ${token}` },
        data: { campaign_id: 0, character_id: 0, choice: "exit" },
    });
    expect(
        res.status() !== 404 && res.status() !== 405 && res.status() !== 410,
        `POST /dungeons/boss-choice musi istnieć i akceptować POST (nie ${res.status()})`
    ).toBeTruthy();
});
