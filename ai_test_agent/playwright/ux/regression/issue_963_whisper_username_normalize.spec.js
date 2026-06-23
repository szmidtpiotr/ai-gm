/**
 * REGRESSION #963 (G19) — whisper_to username auto-normalizes to character name.
 * Acceptance: POST whisper_to username → stored as char name → GET odbiorca widzi szept.
 * POST whisper_to nieznany → 400 (nie cichy przepadek).
 * Uses DEV test campaign 99885 (user 1=demo, user 9998=testjoin / char "Borys Zaglooba").
 */
const { test, expect } = require("@playwright/test");

// DEV test campaign with two members:
//   user 1 (demo) — sender
//   user 9998 (testjoin) — recipient, char "Borys Zaglooba"
const CAMP_ID = 99885;
const SENDER_UID = 1;
const RECIPIENT_USERNAME = "testjoin";
const RECIPIENT_CHAR_NAME = "Borys Zaglooba";
const RECIPIENT_UID = 9998;
const TEST_MARKER = "[PW963]";

test.describe("REGRESSION #963 — whisper_to normalizacja", () => {
  test.afterAll(async ({ request }) => {
    // Clean up test whispers (best effort, non-blocking)
    await request
      .delete(`/api/admin/debug/party-messages/${CAMP_ID}?marker=${TEST_MARKER}`)
      .catch(() => null);
  });

  test("POST whisper_to username → GET odbiorca widzi szept", async ({ page }) => {
    // Send whisper using username (bug: used to silently fail)
    const postResp = await page.request.post(
      `/api/multiplayer/campaigns/${CAMP_ID}/chat?user_id=${SENDER_UID}`,
      {
        data: {
          message: `${TEST_MARKER} Szept przez username`,
          character_name: "Demo",
          whisper_to: RECIPIENT_USERNAME,  // username, not char name
        },
      }
    );
    expect(
      postResp.ok(),
      `POST whisper_to username zwrócił ${postResp.status()}: ${await postResp.text()}`
    ).toBeTruthy();

    // Recipient fetches chat — must see the whisper
    const getResp = await page.request.get(
      `/api/multiplayer/campaigns/${CAMP_ID}/chat?user_id=${RECIPIENT_UID}`
    );
    expect(getResp.ok()).toBeTruthy();
    const body = await getResp.json();
    const whispers = (body.messages || []).filter(
      (m) => m.whisper_to != null && m.message.includes(TEST_MARKER)
    );
    expect(
      whispers.length,
      `Odbiorca powinien widzieć szept wysłany przez username. Widzi ${whispers.length}. Bug #963: whisper przepada gdy whisper_to=username.`
    ).toBeGreaterThanOrEqual(1);
    expect(whispers[0].whisper_to, "whisper_to w DB powinno być char name nie username").toBe(
      RECIPIENT_CHAR_NAME
    );
  });

  test("POST whisper_to nieznany → 400", async ({ page }) => {
    const resp = await page.request.post(
      `/api/multiplayer/campaigns/${CAMP_ID}/chat?user_id=${SENDER_UID}`,
      {
        data: {
          message: `${TEST_MARKER} Szept do nikogo`,
          character_name: "Demo",
          whisper_to: "uzytkownik_ktory_nie_istnieje_xyz9999",
        },
      }
    );
    expect(
      resp.status(),
      "Nieznany whisper_to powinien dawać 400, nie cichy 201"
    ).toBe(400);
  });
});
