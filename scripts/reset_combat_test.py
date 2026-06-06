"""Reset combat 150 for loot drop test: goblin 1HP, player 10HP, status active."""
import sqlite3
import json

conn = sqlite3.connect("/data/ai_gm.db")
row = conn.execute("SELECT combatants FROM active_combat WHERE id=150").fetchone()
combatants = json.loads(row[0])
combatants[0]["hp_current"] = 10  # player back to full
combatants[1]["hp_current"] = 1   # goblin near death
conn.execute(
    "UPDATE active_combat SET combatants=?, status='active', ended_reason=NULL, current_turn='player', round=1 WHERE id=150",
    (json.dumps(combatants),)
)
conn.execute("UPDATE campaigns SET status='active' WHERE id=1116")
conn.execute("UPDATE characters SET sheet_json=json_set(sheet_json, '$.current_hp', 10) WHERE id=1125")
conn.commit()

r = conn.execute("SELECT combatants, status, current_turn FROM active_combat WHERE id=150").fetchone()
c = json.loads(r[0])
print("Combat:", r[1], "Turn:", r[2])
for x in c:
    print(f"  {x['name']} HP: {x['hp_current']}/{x['hp_max']}")
hp_row = conn.execute("SELECT sheet_json FROM characters WHERE id=1125").fetchone()
sheet = json.loads(hp_row[0])
print("Player HP:", sheet.get("current_hp"), "Level:", sheet.get("level"))
conn.close()
