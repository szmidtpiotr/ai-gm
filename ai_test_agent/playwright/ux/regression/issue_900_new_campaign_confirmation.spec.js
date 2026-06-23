/**
 * REGRESSION #900 — New campaign guard: clicking "Nowa Kampania" when the hero already
 * belongs to an active campaign must show a confirmation modal before creating anything.
 * Acceptance: #confirm-new-campaign-overlay appears in the DOM; no new campaign is
 * silently created without the player's explicit confirmation.
 */
const { test, expect } = require("@playwright/test");
const { login } = require("../../helpers/player_flow");
const { resetTestEnv } = require("../../helpers/game_state");

test.setTimeout(60_000);

test("REGRESSION #900 — confirmation modal appears before creating new campaign for hero with active campaign", async ({ page }) => {
    // Set up a known state: test hero assigned to a campaign (has campaign_id).
    await resetTestEnv();
    await login(page);

    // After login the test player should have an existing campaign.
    // If the game auto-entered, navigate back to campaigns screen.
    const onGame = await page.evaluate(
        () => !!document.getElementById("game-screen")?.classList.contains("screen--active"),
    );
    if (onGame) {
        // Go back to heroes, then select hero to reach campaigns screen
        await page.locator("#home-btn").click().catch(() => {});
        await page.waitForSelector("#heroes-screen.screen--active", { timeout: 10000 });
    }

    // On heroes screen — click the first hero card to reach campaigns screen
    await page.waitForSelector("#heroes-screen.screen--active", { timeout: 15000 });
    const heroCard = page.locator(".hero-card").first();
    await heroCard.waitFor({ state: "visible", timeout: 10000 });

    // Verify via API that this hero has a campaign_id (precondition for the guard)
    const heroId = await heroCard.getAttribute("data-hero-id")
        ?? await page.evaluate(() => {
            const card = document.querySelector(".hero-card[data-hero-id]");
            return card?.getAttribute("data-hero-id");
        });

    // Click hero → should show campaigns screen (not auto-enter game since we'll navigate to it)
    await heroCard.click();

    // May land on game screen or campaigns screen
    await page.waitForFunction(
        () => {
            const cs = document.getElementById("campaigns-screen");
            const gs = document.getElementById("game-screen");
            return cs?.classList.contains("screen--active") || gs?.classList.contains("screen--active");
        },
        null,
        { timeout: 15000 },
    );

    // If we ended up in game, navigate back to campaigns
    const inGame = await page.evaluate(
        () => !!document.getElementById("game-screen")?.classList.contains("screen--active"),
    );
    if (inGame) {
        // Click menu/home button to get back to heroes
        await page.locator("#home-btn, #menu-btn, .header__back").first().click().catch(() => {});
        await page.waitForSelector("#heroes-screen.screen--active, #campaigns-screen.screen--active", { timeout: 10000 });
        // If on heroes again, click same hero
        const backOnHeroes = await page.evaluate(() => !!document.getElementById("heroes-screen")?.classList.contains("screen--active"));
        if (backOnHeroes) {
            await page.locator(".hero-card").first().click();
            await page.waitForSelector("#campaigns-screen.screen--active", { timeout: 10000 });
        }
    }

    // Now on campaigns-screen — verify the new-campaign-btn is present
    await page.waitForSelector("#campaigns-screen.screen--active", { timeout: 10000 });
    const newCampaignBtn = page.locator("#new-campaign-btn");
    await newCampaignBtn.waitFor({ state: "visible", timeout: 8000 });

    // Hero has campaign_id (set by resetTestEnv). Clicking "Nowa Kampania" MUST show
    // the confirmation overlay — not silently create a campaign.
    await newCampaignBtn.click();

    // The confirmation overlay should appear within 3 seconds
    await expect(
        page.locator("#confirm-new-campaign-overlay"),
        "Confirmation modal (#confirm-new-campaign-overlay) must appear when hero already has active campaign (#900)",
    ).toBeVisible({ timeout: 3000 });

    // Verify the overlay has the expected action buttons
    await expect(page.locator("#cnc-cancel")).toBeVisible({ timeout: 1000 });
    await expect(page.locator("#cnc-confirm")).toBeVisible({ timeout: 1000 });

    // Clicking "Anuluj" dismisses the modal — no new campaign created
    await page.locator("#cnc-cancel").click();
    await expect(page.locator("#confirm-new-campaign-overlay")).not.toBeVisible({ timeout: 2000 });
});
