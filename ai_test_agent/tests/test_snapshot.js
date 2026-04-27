const { test } = require("node:test");
const assert = require("node:assert/strict");
const { buildSnapshot, decisionsToMessages } = require("../agent/snapshot");

test("decisionsToMessages maps user and assistant", () => {
  const d = {
    decisions: [
      {
        is_legal: true,
        details: { user_text: "hi", assistant_text: "hello", route: "narrative" },
      },
    ],
  };
  const m = decisionsToMessages(d);
  assert.equal(m.length, 2);
  assert.equal(m[0].role, "player");
  assert.equal(m[1].role, "gm");
});

test("buildSnapshot includes player_state and serializes to valid JSON", async () => {
  const prev = global.fetch;
  global.fetch = async (url) => {
    if (String(url).includes("player_state")) {
      return {
        ok: true,
        json: async () => ({
          location: "Start",
          hp: 10,
          max_hp: 10,
          gold_gp: 0,
          quests_active: ["q1"],
          quests_completed: [],
        }),
      };
    }
    if (String(url).includes("gm_decisions")) {
      return { ok: true, json: async () => ({ decisions: [] }) };
    }
    throw new Error(`unexpected fetch ${url}`);
  };
  const page = {
    evaluate: async () => ["send_chat_message"],
  };
  try {
    const snap = await buildSnapshot(page, { goal: "test goal" }, 7, 9, 2, "http://127.0.0.1:9");
    assert.equal(snap.player_state.location, "Start");
    assert.equal(snap.step, 2);
    assert.equal(snap.scenario_goal, "test goal");
    JSON.parse(JSON.stringify(snap));
  } finally {
    global.fetch = prev;
  }
});

test("buildSnapshot last_messages from gm_decisions", async () => {
  const prev = global.fetch;
  global.fetch = async (url) => {
    if (String(url).includes("player_state")) {
      return {
        ok: true,
        json: async () => ({
          location: "A",
          hp: 1,
          max_hp: 1,
          gold_gp: 0,
          quests_active: [],
          quests_completed: [],
        }),
      };
    }
    if (String(url).includes("gm_decisions")) {
      return {
        ok: true,
        json: async () => ({
          decisions: [
            { is_legal: true, details: { user_text: "u", assistant_text: "a", route: "n" } },
          ],
        }),
      };
    }
    return { ok: false, json: async () => ({}) };
  };
  const page = { evaluate: async () => [] };
  try {
    const snap = await buildSnapshot(page, { goal: "g" }, 1, 1, 0, "http://x");
    assert.ok(snap.last_messages.length >= 1);
  } finally {
    global.fetch = prev;
  }
});
