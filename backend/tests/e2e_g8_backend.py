"""E2E backend test for G8 — runs inside the container to verify trigger_narration stores roll_facts."""
import json
import sqlite3
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, "/app")
from app.services import multiplayer_round_service as mrs

db_path = "/data/ai_gm.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# Clean prior test artifacts
conn.execute("DELETE FROM campaign_rounds WHERE campaign_id=99885 AND round_number=999")
conn.execute("DELETE FROM campaign_round_actions WHERE campaign_id=99885 AND action_text='[G8 TEST]'")
conn.commit()

char_row = conn.execute("SELECT id, sheet_json FROM characters WHERE user_id=1 LIMIT 1").fetchone()
if not char_row:
    print("ERROR: no character for user_id=1")
    sys.exit(1)
char_id = int(char_row["id"])
sheet = json.loads(char_row["sheet_json"]) if char_row["sheet_json"] else {}
dex = sheet.get("stats", {}).get("DEX", "?")
print(f"Using char_id={char_id}, DEX={dex}")

cur = conn.execute(
    "INSERT INTO campaign_rounds (campaign_id, round_number, status, deadline) VALUES (99885, 999, 'narrating', datetime('now', '+1 day'))"
)
round_id = cur.lastrowid
conn.execute(
    """INSERT INTO campaign_round_actions
       (round_id, campaign_id, user_id, character_id, character_name, action_text, initiative_roll)
       VALUES (?, 99885, 1, ?, 'Bohater', '[G8 TEST]', 12)""",
    (round_id, char_id),
)
conn.commit()
conn.close()
print(f"Created round_id={round_id}")

planner_resp = json.dumps([{"character_name": "Bohater", "test": "stealth", "dc": 12}])
narrator_resp = json.dumps({
    "narrative": "Bohater skrada się cicho. 🎲 Skradanie: 14 vs DC 12 ✓",
    "player_notes": {},
})

call_log = []

def fake_generate(base_url, model, messages, api_key=""):
    call_log.append(len(call_log) + 1)
    return planner_resp if len(call_log) == 1 else narrator_resp

with patch("app.services.multiplayer_round_service.llm_service") as mock_llm:
    mock_cfg = {"provider": "openai", "base_url": "", "model": "gpt-4", "api_key": ""}
    mock_llm.get_effective_config.return_value = mock_cfg
    driver = MagicMock()
    driver.generate_chat.side_effect = fake_generate
    mock_llm.OpenAIDriver.return_value = driver
    mrs.trigger_narration(round_id)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
row = conn.execute("SELECT status, narrative_json FROM campaign_rounds WHERE id=?", (round_id,)).fetchone()
data = json.loads(row["narrative_json"]) if row and row["narrative_json"] else {}
print(f"status={row['status'] if row else 'MISSING'}")
print(f"narrative={data.get('narrative', '')[:70]}")
print(f"roll_facts={data.get('roll_facts', 'MISSING')}")
print(f"LLM calls={len(call_log)}")

conn.execute("DELETE FROM campaign_round_actions WHERE round_id=?", (round_id,))
conn.execute("DELETE FROM campaign_rounds WHERE id=?", (round_id,))
conn.commit()
conn.close()

facts = data.get("roll_facts")
if facts is None:
    print("RESULT: FAIL — roll_facts missing")
    sys.exit(1)
if len(call_log) != 2:
    print(f"RESULT: FAIL — expected 2 LLM calls, got {len(call_log)}")
    sys.exit(1)
if facts and facts[0].get("test") == "stealth":
    f = facts[0]
    print(f"RESULT: PASS — test={f['test']}, dc={f['dc']}, raw={f['raw']}, total={f['total']}, success={f['success']}, nat20={f['is_nat20']}, nat1={f['is_nat1']}")
else:
    print(f"RESULT: WARN — unexpected roll_facts={facts}")
print("G8 E2E: OK")
