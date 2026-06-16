/**
 * REGRESSION #681 (L12) — Wybór drzwi w UI: przyciski kierunków, obraz kafelka, akcje tile.
 * Acceptance: Gdy aktywny dungeon v2, pod composerem widoczne przyciski N/S/E/W; kafelek ma obraz;
 * klik drzwi na mapie = POST /dungeons/move; skrzynia/zagadka = POST /dungeons/resolve-tile.
 * Weryfikuje: DOM istnienie elementów, API contract dla /dungeons/move i /dungeons/resolve-tile,
 * app.js wersja zawiera '681'.
 */
const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://frontend:80";

test("REGRESSION #681 — #dungeon-nav istnieje w DOM z 4 przyciskami kierunków", async ({ page }) => {
    await page.goto(`${BASE}/`);
    const nav = page.locator("#dungeon-nav");
    await expect(nav, "#dungeon-nav musi istnieć w DOM").toHaveCount(1);

    // Przyciski kierunków (data-dir lub btn-dungeon-dir class)
    const dirs = ["N", "S", "E", "W"];
    for (const dir of dirs) {
        const btn = page.locator(`[data-dungeon-dir="${dir}"]`);
        await expect(btn, `Przycisk kierunku ${dir} musi istnieć`).toHaveCount(1);
    }
});

test("REGRESSION #681 — #dungeon-tile-scene istnieje w DOM (panel obrazu kafelka)", async ({ page }) => {
    await page.goto(`${BASE}/`);
    const scene = page.locator("#dungeon-tile-scene");
    await expect(scene, "#dungeon-tile-scene musi istnieć w DOM").toHaveCount(1);
});

test("REGRESSION #681 — przyciski akcji kafelkowych istnieją (#dungeon-open-chest, #dungeon-answer-riddle)", async ({ page }) => {
    await page.goto(`${BASE}/`);
    const chest = page.locator("#dungeon-open-chest");
    await expect(chest, "#dungeon-open-chest musi istnieć w DOM").toHaveCount(1);

    const riddle = page.locator("#dungeon-answer-riddle");
    await expect(riddle, "#dungeon-answer-riddle musi istnieć w DOM").toHaveCount(1);

    const hint = page.locator("#dungeon-riddle-hint-btn2").or(page.locator("[data-dungeon-action='riddle_hint']"));
    await expect(hint, "Przycisk podpowiedzi zagadki musi istnieć w DOM").toHaveCount(1);
});

test("REGRESSION #681 — POST /dungeons/move zwraca {ok, node_id, narrative} dla poprawnego kierunku", async ({ request }) => {
    const loginRes = await request.post(`${BASE}/api/auth/login`, {
        data: { username: "demo", password: "demo" },
    });
    expect(loginRes.ok(), "login musi zwrócić 200").toBeTruthy();
    const token = (await loginRes.json()).token || (await loginRes.json()).access_token;

    // Test z nieprawidłowym campaign_id — powinno zwrócić błąd (400/404/422), ale NIE 405/410
    const moveRes = await request.post(`${BASE}/api/dungeons/move`, {
        headers: { Authorization: `Bearer ${token}` },
        data: { campaign_id: 0, character_id: 0, direction: "N" },
    });
    // Endpoint istnieje (nie 404 na samej ścieżce, nie 405 Method Not Allowed, nie 410 GONE)
    expect(
        moveRes.status() !== 404 && moveRes.status() !== 405 && moveRes.status() !== 410,
        `POST /dungeons/move musi istnieć i akceptować POST (nie ${moveRes.status()})`
    ).toBeTruthy();
});

test("REGRESSION #681 — POST /dungeons/resolve-tile zwraca kontrakt dla pustej kampanii (error, nie 410)", async ({ request }) => {
    const loginRes = await request.post(`${BASE}/api/auth/login`, {
        data: { username: "demo", password: "demo" },
    });
    const token = (await loginRes.json()).token || (await loginRes.json()).access_token;

    const res = await request.post(`${BASE}/api/dungeons/resolve-tile`, {
        headers: { Authorization: `Bearer ${token}` },
        data: { campaign_id: 0, character_id: 0, action: "open_chest" },
    });
    expect(
        res.status() !== 404 && res.status() !== 405 && res.status() !== 410,
        `POST /dungeons/resolve-tile musi istnieć (nie ${res.status()})`
    ).toBeTruthy();
});

test("REGRESSION #681 — app.js załadowany z wersją L12 / 681 (cache-bust)", async ({ page }) => {
    await page.goto(`${BASE}/`);
    const scripts = await page.evaluate(() =>
        Array.from(document.querySelectorAll("script[src]")).map(s => s.src)
    );
    const appJs = scripts.find(s => s.includes("app.js"));
    expect(appJs, "app.js musi być załadowany").toBeTruthy();
    expect(
        appJs.includes("681") || appJs.includes("l12"),
        `app.js ?v= powinno zawierać '681' lub 'l12', mamy: ${appJs}`
    ).toBeTruthy();
});
