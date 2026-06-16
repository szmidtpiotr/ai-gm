import sqlite3, json
conn = sqlite3.connect('/data/ai_gm.db')
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM dungeon_tiles WHERE category_key='krypta'")
total = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM dungeon_tiles WHERE category_key='krypta' AND is_boss_tile=1")
boss = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM dungeon_tiles WHERE category_key='krypta' AND riddle_key IS NOT NULL")
riddles = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM dungeon_tiles WHERE category_key='krypta' AND items_json != '[]'")
chests = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM dungeon_tiles WHERE category_key='krypta' AND enemies_json='[]' AND items_json='[]' AND riddle_key IS NULL")
rest = c.fetchone()[0]
c.execute("SELECT doors_json FROM dungeon_tiles WHERE category_key='krypta'")
doors_counts = {}
for row in c.fetchall():
    n = len(json.loads(row[0]))
    doors_counts[n] = doors_counts.get(n, 0) + 1
print(f'Total: {total}, Boss: {boss}, Riddles: {riddles}, Chests: {chests}, Rest: {rest}')
print(f'Door distribution: {sorted(doors_counts.items())}')
c.execute("SELECT key, label FROM dungeon_tile_categories WHERE key='krypta'")
cat = c.fetchone()
print(f'Category: {cat}')
c.execute("SELECT key, theme FROM game_config_riddles WHERE key IN ('riddle_grave','riddle_tomb')")
print(f'New riddles: {c.fetchall()}')
conn.close()
