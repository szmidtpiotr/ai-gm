import json, urllib.request, urllib.error, sys, subprocess
from collections import deque
API="http://192.168.1.61:8100/api"; HERO=2; DKEY="goblin_warren"; USER=1
def call(m,p,pl=None,t=120):
    d=json.dumps(pl).encode() if pl is not None else None
    r=urllib.request.Request(API+p,data=d,headers={"Content-Type":"application/json"},method=m)
    try:
        with urllib.request.urlopen(r,timeout=t) as x: return x.status,json.loads(x.read().decode())
    except urllib.error.HTTPError as e:
        try: b=json.loads(e.read().decode(errors="replace"))
        except Exception: b={"raw":"?"}
        return e.code,b
    except Exception as e: return 0,{"error":str(e)}
def ssh_sql(sql):
    return subprocess.run(["ssh","claude@192.168.1.61",f'docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db "{sql}"'],capture_output=True,text=True).stdout.strip()
def reset_cd(): ssh_sql("DELETE FROM character_dungeon_runs WHERE character_id=2 AND location_key IN (SELECT location_key FROM game_dungeons WHERE key='goblin_warren');")
def enter_fresh(tag):
    reset_cd()
    for i in range(20):
        s,c=call("POST","/campaigns",{"title":f"[SMOKE] {tag} #{i}","system_id":"fantasy","model_id":"default","owner_user_id":USER,"language":"pl","mode":"dungeon","status":"active"})
        cid=c.get("id"); call("POST",f"/characters/{HERO}/assign-campaign",{"campaign_id":cid,"user_id":USER})
        s,e=call("POST",f"/dungeons/{DKEY}/enter",{"character_id":HERO,"campaign_id":cid,"previous_campaign_id":None})
        run=e["dungeon_run"]; g=run["graph"]
        if not g["nodes"][g["entry_node"]]["content"].get("enemies"): return cid,run,g
def is_player(c): return c.get("type")=="player" or str(c.get("id"))=="player"
def fight(cid,collect=False):
    seen_enemy=None
    for _ in range(60):
        s,cb=call("GET",f"/campaigns/{cid}/combat"); comb=cb.get("combat")
        if not cb.get("active") or not comb or comb.get("status")!="active": return comb,seen_enemy
        if collect and seen_enemy is None:
            for c in comb["combatants"]:
                if not is_player(c): seen_enemy={k:c.get(k) for k in("enemy_key","hp_max","attack_bonus","damage_dice","tier")}
        if any(c.get("pending_reaction") for c in comb["combatants"]):
            call("POST",f"/campaigns/{cid}/combat/resolve-reaction",{"choice":"take"}); continue
        players=[c for c in comb["combatants"] if is_player(c)]; pid=players[0]["id"]
        if str(comb.get("current_turn"))==str(pid):
            en=[c for c in comb["combatants"] if not is_player(c) and (c.get("hp_current") or 0)>0]
            if not en: call("POST",f"/campaigns/{cid}/combat/enemy-turn"); continue
            call("POST",f"/campaigns/{cid}/combat/resolve-attack",{"raw_d20":19,"attacker":"player","target_id":str(en[0]["id"]),"enemy_key":en[0].get("enemy_key")})
        else: call("POST",f"/campaigns/{cid}/combat/enemy-turn")
    return None,seen_enemy
def path_to(g,s,goal):
    nodes=g["nodes"]; q=deque([(s,[])]); seen={s}
    while q:
        nid,p=q.popleft()
        if nid==goal: return p
        for d,t in (nodes[nid]["doors_open"] or {}).items():
            if t and t not in seen: seen.add(t); q.append((t,p+[(d,t)]))
    return None

print("TEST D2 — ABANDON full dump")
cid,run,g=enter_fresh("abandon2")
print(" entry enemy-free, nodes:",list(g["nodes"].keys()))
d,t=path_to(g,g['entry_node'],g['boss_node'])[0]
s,mv=call("POST","/dungeons/move",{"character_id":HERO,"campaign_id":cid,"direction":d})
print(f" move {d}->{t} ok={mv.get('ok')} combat={'Y' if mv.get('combat') else 'N'}")
if mv.get("combat") is not None: fight(cid)
s,rr=call("GET",f"/campaigns/{cid}/dungeon-run"); print(" run completed/failed/at_checkpoint:",{k:(rr.get('dungeon_run') or {}).get(k) for k in('completed','failed','at_checkpoint')})
s,ex=call("POST","/dungeons/exit",{"character_id":HERO,"campaign_id":cid})
print(f" exit STATUS={s} BODY={json.dumps(ex,ensure_ascii=False)}")
print(" DB rows char2:", ssh_sql("SELECT location_key,cooldown_until FROM character_dungeon_runs WHERE character_id=2;"))

print("\nTEST F — ENDLESS cycle-2 enemy scaling")
cid,run,g=enter_fresh("endless")
# fight cycle1 boss path, capture a cycle1 non-boss enemy
path=path_to(g,g['entry_node'],g['boss_node'])
c1_enemy=None
for d,t in path:
    s,mv=call("POST","/dungeons/move",{"character_id":HERO,"campaign_id":cid,"direction":d})
    if mv.get("combat") is not None:
        c,se=fight(cid,collect=(c1_enemy is None))
        if se and g["nodes"][t]["content"].get("enemies") and not g["nodes"][t]["content"].get("is_boss_tile") and c1_enemy is None:
            c1_enemy=se
print(" cycle1 sample enemy:",c1_enemy)
s,rr=call("GET",f"/campaigns/{cid}/dungeon-run"); r2=rr.get("dungeon_run") or {}
if r2.get("boss_choice_pending"):
    s,bc=call("POST","/dungeons/boss-choice",{"character_id":HERO,"campaign_id":cid,"choice":"go_deeper"})
    print(f" go_deeper: cycle={bc.get('new_cycle')} entry={bc.get('new_entry_node')} boss={bc.get('new_boss_node')}")
    s,rr=call("GET",f"/campaigns/{cid}/dungeon-run"); r3=rr.get("dungeon_run") or {}
    g2=r3["graph"]; entry2=r3.get("positions",{}).get("2") or g2.get("entry_node")
    # walk c2 toward its boss, capture first c2 enemy
    p2=path_to(g2, entry2, g2.get("boss_node"))
    print(" c2 path:",p2)
    c2_enemy=None
    for d,t in (p2 or []):
        s,mv=call("POST","/dungeons/move",{"character_id":HERO,"campaign_id":cid,"direction":d})
        if mv.get("combat") is not None:
            c,se=fight(cid,collect=True)
            if se: c2_enemy=se; break
    print(" cycle2 sample enemy:",c2_enemy)
    print(f" SCALING: c1 atk_bonus={c1_enemy and c1_enemy.get('attack_bonus')} hp={c1_enemy and c1_enemy.get('hp_max')}  ->  c2 atk_bonus={c2_enemy and c2_enemy.get('attack_bonus')} hp={c2_enemy and c2_enemy.get('hp_max')}")
print("DONE")
