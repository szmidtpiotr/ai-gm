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
    return subprocess.run(["ssh","claude@192.168.1.61",
        f'docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db "{sql}"'],
        capture_output=True,text=True).stdout.strip()
def reset_cd():
    ssh_sql("DELETE FROM character_dungeon_runs WHERE character_id=2 AND location_key IN (SELECT location_key FROM game_dungeons WHERE key='goblin_warren');")
def enter_fresh(tag):
    reset_cd()
    for i in range(20):
        s,c=call("POST","/campaigns",{"title":f"[SMOKE] {tag} #{i}","system_id":"fantasy","model_id":"default","owner_user_id":USER,"language":"pl","mode":"dungeon","status":"active"})
        cid=c.get("id"); call("POST",f"/characters/{HERO}/assign-campaign",{"campaign_id":cid,"user_id":USER})
        s,e=call("POST",f"/dungeons/{DKEY}/enter",{"character_id":HERO,"campaign_id":cid,"previous_campaign_id":None})
        if s!=200: print(f"enter fail {s} {e}"); sys.exit(1)
        run=e["dungeon_run"]; g=run["graph"]
        if not g["nodes"][g["entry_node"]]["content"].get("enemies"): return cid,run,g
    print("no enemy-free entry"); sys.exit(1)
def is_player(c): return c.get("type")=="player" or str(c.get("id"))=="player"
def fight(cid):
    for _ in range(60):
        s,cb=call("GET",f"/campaigns/{cid}/combat"); comb=cb.get("combat")
        if not cb.get("active") or not comb or comb.get("status")!="active": return comb
        if any(c.get("pending_reaction") for c in comb["combatants"]):
            call("POST",f"/campaigns/{cid}/combat/resolve-reaction",{"choice":"take"}); continue
        players=[c for c in comb["combatants"] if is_player(c)]; pid=players[0]["id"]
        if str(comb.get("current_turn"))==str(pid):
            en=[c for c in comb["combatants"] if not is_player(c) and (c.get("hp_current") or 0)>0]
            if not en: call("POST",f"/campaigns/{cid}/combat/enemy-turn"); continue
            call("POST",f"/campaigns/{cid}/combat/resolve-attack",{"raw_d20":19,"attacker":"player","target_id":str(en[0]["id"]),"enemy_key":en[0].get("enemy_key")})
        else: call("POST",f"/campaigns/{cid}/combat/enemy-turn")
    return None
def path_to(g,s,goal):
    nodes=g["nodes"]; q=deque([(s,[])]); seen={s}
    while q:
        nid,p=q.popleft()
        if nid==goal: return p
        for d,t in (nodes[nid]["doors_open"] or {}).items():
            if t and t not in seen: seen.add(t); q.append((t,p+[(d,t)]))
    return None

print("="*60,"\nTEST B — CHEST")
cid,run,g=enter_fresh("chest")
# find a chest node (content.items)
chest=None
for nid,n in g["nodes"].items():
    if n["content"].get("items") and not n["content"].get("enemies"): chest=nid; break
if chest:
    path=path_to(g,g["entry_node"],chest)
    print(" path to chest",chest,":",path)
    ok=True
    for d,t in path:
        s,mv=call("POST","/dungeons/move",{"character_id":HERO,"campaign_id":cid,"direction":d})
        if mv.get("combat") is not None: fight(cid)
        if not mv.get("ok"): print("  blocked:",mv.get("reason")); ok=False; break
    if ok:
        for a in range(1,4):
            s,r=call("POST","/dungeons/resolve-tile",{"character_id":HERO,"campaign_id":cid,"action":"open_chest"})
            print(f"  open_chest #{a}: ok={r.get('ok')} success={r.get('success')} roll={r.get('roll')} dc={r.get('dc')} attempt={r.get('attempt')} loot={len(r.get('loot') or [])} locked={r.get('chest_locked_forever')}")
            if r.get("success") or r.get("chest_locked_forever"): break
else: print("  no pure-chest node in this graph")

print("="*60,"\nTEST C — DEATH ends run")
cid,run,g=enter_fresh("death")
# move into first combat then kill player via death endpoint
path=path_to(g,g["entry_node"],g["boss_node"])
d,t=path[0]
s,mv=call("POST","/dungeons/move",{"character_id":HERO,"campaign_id":cid,"direction":d})
pos_before=call("GET",f"/campaigns/{cid}/dungeon-run")[1]["dungeon_run"]["positions"]
s,dd=call("POST","/dungeons/death",{"character_id":HERO,"campaign_id":cid})
s,rr=call("GET",f"/campaigns/{cid}/dungeon-run"); r2=rr.get("dungeon_run") or {}
print(f"  death resp: failed={dd.get('failed')} restored={dd.get('restored')} cd={dd.get('cooldown_until')}")
print(f"  run after death: failed={r2.get('failed')} completed={r2.get('completed')} positions={r2.get('positions')} entry={g['entry_node']}")
print(f"  -> position NOT reset to entry? {r2.get('positions')!={'2':g['entry_node']}} (still at {t})")

print("="*60,"\nTEST D — ABANDON 50% cooldown")
cid,run,g=enter_fresh("abandon")
d,t=path_to(g,g['entry_node'],g['boss_node'])[0]
call("POST","/dungeons/move",{"character_id":HERO,"campaign_id":cid,"direction":d})
fight(cid)
s,ex=call("POST","/dungeons/exit",{"character_id":HERO,"campaign_id":cid})
cd=ssh_sql("SELECT cooldown_until, cleared_at FROM character_dungeon_runs WHERE character_id=2;")
print(f"  exit: was_failed={ex.get('was_failed')} at_checkpoint={ex.get('at_checkpoint')} cd_until={ex.get('cooldown_until')}")
print(f"  DB cooldown row: {cd}")

print("="*60,"\nTEST E — FLAG dungeon_enabled OFF")
ssh_sql("INSERT INTO game_config_meta(key,value) VALUES('game_mode_flags',json('{\\\"dungeon_enabled\\\":false}')) ON CONFLICT(key) DO UPDATE SET value=json('{\\\"dungeon_enabled\\\":false}');")
reset_cd()
s,c=call("POST","/campaigns",{"title":"[SMOKE] flagoff","system_id":"fantasy","model_id":"default","owner_user_id":USER,"language":"pl","mode":"dungeon","status":"active"})
cid=c.get("id"); call("POST",f"/characters/{HERO}/assign-campaign",{"campaign_id":cid,"user_id":USER})
s,e=call("POST",f"/dungeons/{DKEY}/enter",{"character_id":HERO,"campaign_id":cid,"previous_campaign_id":None})
print(f"  enter with flag OFF: status={s} detail={e.get('detail')}")
ssh_sql("UPDATE game_config_meta SET value=json('{\\\"dungeon_enabled\\\":true}') WHERE key='game_mode_flags';")
s,e2=call("POST",f"/dungeons/{DKEY}/enter",{"character_id":HERO,"campaign_id":cid,"previous_campaign_id":None})
print(f"  enter with flag ON again: status={s}")
print("DONE")
