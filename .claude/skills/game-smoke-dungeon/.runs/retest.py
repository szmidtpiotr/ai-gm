import json, urllib.request, urllib.error, subprocess
from collections import deque
API="http://192.168.1.61:8100/api"; HERO=2; DKEY="goblin_warren"; USER=1
def call(m,p,pl=None,t=120):
    d=json.dumps(pl).encode() if pl is not None else None
    r=urllib.request.Request(API+p,data=d,headers={"Content-Type":"application/json"},method=m)
    try:
        with urllib.request.urlopen(r,timeout=t) as x: return x.status,json.loads(x.read().decode())
    except urllib.error.HTTPError as e:
        try: b=json.loads(e.read().decode(errors="replace"))
        except Exception: b={}
        return e.code,b
    except Exception as e: return 0,{"error":str(e)}
def ssh_sql(s): return subprocess.run(["ssh","claude@192.168.1.61",f'docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db "{s}"'],capture_output=True,text=True).stdout.strip()
def reset_cd(): ssh_sql("DELETE FROM character_dungeon_runs WHERE character_id=2;")
def new_enter():
    reset_cd()
    s,c=call("POST","/campaigns",{"title":"[SMOKE] retest","system_id":"fantasy","model_id":"default","owner_user_id":USER,"language":"pl","mode":"dungeon","status":"active"})
    cid=c["id"]; call("POST",f"/characters/{HERO}/assign-campaign",{"campaign_id":cid,"user_id":USER})
    s,e=call("POST",f"/dungeons/{DKEY}/enter",{"character_id":HERO,"campaign_id":cid})
    return cid,e
def is_player(c): return c.get("type")=="player"
def fight(cid):
    for _ in range(60):
        s,cb=call("GET",f"/campaigns/{cid}/combat"); comb=cb.get("combat")
        if not cb.get("active") or not comb or comb.get("status")!="active": return
        if any(c.get("pending_reaction") for c in comb["combatants"]): call("POST",f"/campaigns/{cid}/combat/resolve-reaction",{"choice":"take"}); continue
        pl=[c for c in comb["combatants"] if is_player(c)][0]
        if str(comb["current_turn"])==str(pl["id"]):
            en=[c for c in comb["combatants"] if not is_player(c) and (c.get("hp_current") or 0)>0]
            if not en: call("POST",f"/campaigns/{cid}/combat/enemy-turn"); continue
            call("POST",f"/campaigns/{cid}/combat/resolve-attack",{"raw_d20":19,"attacker":"player","target_id":str(en[0]["id"]),"enemy_key":en[0].get("enemy_key")})
        else: call("POST",f"/campaigns/{cid}/combat/enemy-turn")
def path_to(g,s,goal):
    q=deque([(s,[])]); seen={s}
    while q:
        nid,p=q.popleft()
        if nid==goal: return p
        for d,t in (g["nodes"][nid]["doors_open"] or {}).items():
            if t and t in g["nodes"] and t not in seen: seen.add(t); q.append((t,p+[(d,t)]))
    return None

print("="*60,"\n#685 RETEST — entry node always enemy-free (20 enters)")
bad=0
for i in range(20):
    cid,e=new_enter(); g=e["dungeon_run"]["graph"]
    en=g["nodes"][g["entry_node"]]["content"].get("enemies")
    if en: bad+=1; print(f"  try{i}: entry={g['entry_node']} HAS ENEMIES {en}  <-- FAIL")
print(f"  result: {bad}/20 enters had combat entry  -> {'PASS' if bad==0 else 'FAIL'}")

print("="*60,"\n#684 RETEST — DEATH endpoint")
reset_cd(); cid,e=new_enter(); g=e["dungeon_run"]["graph"]
d,t=path_to(g,g['entry_node'],g['boss_node'])[0]
call("POST","/dungeons/move",{"character_id":HERO,"campaign_id":cid,"direction":d})
s,dd=call("POST","/dungeons/death",{"character_id":HERO,"campaign_id":cid})
cd=ssh_sql("SELECT cooldown_until FROM character_dungeon_runs WHERE character_id=2;")
s2,rr=call("GET",f"/campaigns/{cid}/dungeon-run"); r=rr.get("dungeon_run") or {}
print(f"  /dungeons/death status={s} failed={dd.get('failed')} cooldown_until={dd.get('cooldown_until')}")
print(f"  run failed={r.get('failed')} positions={r.get('positions')} (entry={g['entry_node']})  DBcooldown={cd}")
print(f"  -> {'PASS' if s==200 and r.get('failed') and cd else 'FAIL'}")

print("="*60,"\n#684 RETEST — ABANDON endpoint (50% cooldown)")
reset_cd(); cid,e=new_enter(); g=e["dungeon_run"]["graph"]
d,t=path_to(g,g['entry_node'],g['boss_node'])[0]
call("POST","/dungeons/move",{"character_id":HERO,"campaign_id":cid,"direction":d}); fight(cid)
s,ex=call("POST","/dungeons/exit",{"character_id":HERO,"campaign_id":cid})
cd=ssh_sql("SELECT cooldown_until, cleared_at, CAST((julianday(cooldown_until)-julianday(cleared_at))*24 AS INT) AS hrs FROM character_dungeon_runs WHERE character_id=2;")
print(f"  /dungeons/exit status={s} was_failed={ex.get('was_failed')} at_checkpoint={ex.get('at_checkpoint')} cooldown_until={ex.get('cooldown_until')}")
print(f"  DB cooldown row (until|cleared|hours): {cd}")
print(f"  -> expect ~36h (ceil 72*0.5). status200={s==200}")
reset_cd()
print("DONE")
