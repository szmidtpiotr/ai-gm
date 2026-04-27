const { test } = require("node:test");
const assert = require("node:assert/strict");
const { validate, FALLBACK } = require("../agent/action_validator");

test("rejects empty chat message", () => {
  const a = validate({ type: "send_chat_message", params: { text: "  " } }, []);
  assert.equal(a.type, FALLBACK.type);
});

test("rejects unknown screen", () => {
  const a = validate(
    { type: "open_screen", params: { screen: "admin" } },
    []
  );
  assert.equal(a.type, FALLBACK.type);
});

test("rejects unknown click selector", () => {
  const a = validate(
    { type: "click", params: { selector: "#evil" } },
    []
  );
  assert.equal(a.type, FALLBACK.type);
});

test("rejects js injection in text", () => {
  const a = validate(
    { type: "send_chat_message", params: { text: "Hello <script>alert(1)</script>" } },
    []
  );
  assert.equal(a.type, FALLBACK.type);
});

test("fallback on invalid json string", () => {
  const a = validate("{invalid", []);
  assert.equal(a.type, FALLBACK.type);
});

test("loop detection forces finish", () => {
  const same = { type: "send_chat_message", params: { text: "x" } };
  const h = [same, same, same].map((x) => JSON.parse(JSON.stringify(x)));
  const a = validate(same, h);
  assert.equal(a.type, "finish");
  assert.equal(a.params.reason, "loop_detected");
});
