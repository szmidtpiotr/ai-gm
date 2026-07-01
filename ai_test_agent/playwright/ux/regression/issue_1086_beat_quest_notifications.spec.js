/**
 * REGRESSION #1086 — Beat/quest completion notifications in player chat.
 * Acceptance: GET /api/admin/config/gm-plan-notifications returns enabled flag;
 * PATCH toggles it; endpoint exists and responds 200.
 */
const { test, expect } = require("@playwright/test");

async function getAdminToken(request) {
    const r = await request.post("/api/admin/dev-login", {
        data: { username: "ai_test_gm", password: "ai_test_gm" }
    });
    const body = await r.json();
    return body.token;
}

test("REGRESSION #1086 — gm-plan-notifications GET returns enabled flag", async ({ request }) => {
    const token = await getAdminToken(request);
    const r = await request.get("/api/admin/config/gm-plan-notifications", {
        headers: { Authorization: `Bearer ${token}` }
    });
    expect(r.ok(), "GET /api/admin/config/gm-plan-notifications nie odpowiada 200 (#1086)").toBeTruthy();
    const body = await r.json();
    expect(typeof body.gm_plan_notifications_enabled, "brak pola gm_plan_notifications_enabled (#1086)").toBe("boolean");
    expect(body.gm_plan_notifications_enabled).toBe(true);
});

test("REGRESSION #1086 — gm-plan-notifications PATCH toggles flag", async ({ request }) => {
    const token = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

    // disable
    const r1 = await request.patch("/api/admin/config/gm-plan-notifications", {
        headers,
        data: { gm_plan_notifications_enabled: false }
    });
    expect(r1.ok(), "PATCH disable failed (#1086)").toBeTruthy();
    const b1 = await r1.json();
    expect(b1.gm_plan_notifications_enabled).toBe(false);

    // re-enable
    const r2 = await request.patch("/api/admin/config/gm-plan-notifications", {
        headers,
        data: { gm_plan_notifications_enabled: true }
    });
    expect(r2.ok(), "PATCH enable failed (#1086)").toBeTruthy();
    const b2 = await r2.json();
    expect(b2.gm_plan_notifications_enabled).toBe(true);
});
