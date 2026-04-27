const BACKEND_URL = process.env.BACKEND_URL || "http://192.168.1.61:8100";

async function resetTestEnv() {
  const res = await fetch(`${BACKEND_URL}/api/debug/reset_test_env`, { method: "POST" });
  const data = await res.json();
  if (!data.reset) {
    throw new Error(`reset_test_env failed: ${JSON.stringify(data)}`);
  }
  return data;
}

async function getPlayerState(characterId) {
  const res = await fetch(`${BACKEND_URL}/api/debug/player_state?character_id=${characterId}`);
  return res.json();
}

module.exports = { resetTestEnv, getPlayerState };
