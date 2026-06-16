import json, urllib.request, urllib.error, subprocess
from collections import deque
API="http://192.168.1.61:8100/api"; HERO=2; DKEY="goblin_warren"; USER=1
def call(m,p,pl=None,t=120):
    d=json.dumps(pl).encode() if pl is not None else None
    r=urllib.request.Request(API+p,data=d,headers={"Content-Type":"application/json"},method=m)
    try:
        with urllib.request.urlopen(r,timeout=t) as x: return x.status,json.loads(x.read().decode())
    except urllib.error.HTTPError as e: return e.code,{}
    except Exception as e: return 0,{"error":str(e)}
def ssh_sql(s): subprocess.run(["ssh","claude@192.168.1.61",f'docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db "{s}"'],capture_output=True,text=True)
ssh_sql("DELETE FROM character_dungeon_runs WHERE character_id=2;")
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
for i in range(20):
    s,c=call("POST","/campaigns",{"title":f"[SMOKE] navc2 #{i}","system_id":"fantasy","model_id":"default","owner_user_id":USER,"language":"pl","mode":"dungeon","status":"active"})
    cid=c["id"]; call("POST",f"/characters/{HERO}/assign-campaign",{"campaign_id":cid,"user_id":USER})
    s,e=call("POST",f"/dungeons/{DKEY}/enter",{"character_id":HERO,"campaign_id":cid})
    g=e["dungeon_run"]["graph"]
    if not g["nodes"][g["entry_node"]]["content"].get("enemies"): break
for d,t in path_to(g,g["entry_node"],g["boss_node"]):
    s,mv=call("POST","/dungeons/move",{"character_id":HERO,"campaign_id":cid,"direction":d})
    if mv.get("combat") is not None: fight(cid)
s,bc=call("POST","/dungeons/boss-choice",{"character_id":HERO,"campaign_id":cid,"choice":"go_deeper"})
s,rr=call("GET",f"/campaigns/{cid}/dungeon-run"); r=rr["dungeon_run"]; g2=r["graph"]
pos=r["positions"]["2"]; bn=g2["boss_node"]
print("after go_deeper: positions[2]=",pos," boss_node=",bn)
print("old-boss node doors:",{k:v for k,v in g2["nodes"][pos]["doors_open"].items()})
p2=path_to(g2,pos,bn)
print("path pos->c2boss:",p2)
# also try from any c2 entry
c2entry=bc.get("new_entry_node")
print("c2 entry node exists in graph:",c2entry in g2["nodes"], " doors:",g2["nodes"].get(c2entry,{}).get("doors_open"))
print("path c2entry->c2boss:",path_to(g2,c2entry,bn))
# walk it
if p2:
    for d,t in p2:
        s,mv=call("POST","/dungeons/move",{"character_id":HERO,"campaign_id":cid,"direction":d})
        ek=[x.get("enemy_key") for x in g2["nodes"][t]["content"].get("enemies",[])]
        print(f"  c2 move {d}->{t} ok={mv.get('ok')} reason={mv.get('reason')} combat={'Y' if mv.get('combat') else 'N'} enemies={ek}")
        if mv.get("combat") is not None: fight(cid)
ssh_sql("DELETE FROM character_dungeon_runs WHERE character_id=2;")
print("DONE")
