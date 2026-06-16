import json, urllib.request, urllib.error, sys, time
API="http://192.168.1.61:8100/api"
HERO=2; DKEY="goblin_warren"; USER=1
LOG=[]
def call(method, path, payload=None, timeout=120):
    data=json.dumps(payload).encode() if payload is not None else None
    req=urllib.request.Request(API+path,data=data,headers={"Content-Type":"application/json"},method=method)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r: return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try: b=json.loads(e.read().decode(errors="replace"))
        except Exception: b={"raw":"?"}
        return e.code,b
    except Exception as e: return 0,{"error":str(e)}
def log(m): LOG.append(m); print(m, flush=True)

def is_player(c):
    return bool(c.get("is_player")) or c.get("side")=="player" or str(c.get("id")) in ("player",str(HERO)) or c.get("kind")=="player" or c.get("type")=="player"
def hp(c):
    for k in ("hp","current_hp","hp_current","hp_now"):
        if k in c: return c[k]
    return c.get("stats",{}).get("hp")

DUMPED=[False]
def fight(cid, tag="", maxr=60):
    for i in range(maxr):
        s,cb=call("GET",f"/campaigns/{cid}/combat")
        comb=cb.get("combat")
        if not cb.get("active") or not comb or comb.get("status")!="active":
            log(f"  [{tag}] combat ended after {i} acts, reason={comb.get('ended_reason') if comb else '-'}")
            return comb
        if not DUMPED[0]:
            log("  COMBATANTS SHAPE: "+json.dumps(comb.get("combatants"),ensure_ascii=False,default=str)[:900])
            DUMPED[0]=True
        rwin=[c for c in comb["combatants"] if c.get("pending_reaction")]
        if rwin:
            call("POST",f"/campaigns/{cid}/combat/resolve-reaction",{"choice":"take"}); continue
        cur=comb.get("current_turn")
        players=[c for c in comb["combatants"] if is_player(c)]
        pid=players[0]["id"] if players else None
        if str(cur)==str(pid):
            enemies=[c for c in comb["combatants"] if not is_player(c) and (hp(c) or 0)>0]
            if not enemies:
                call("POST",f"/campaigns/{cid}/combat/enemy-turn"); continue
            tgt=enemies[0]
            body={"raw_d20":19,"attacker":"player","target_id":str(tgt.get("id"))}
            if tgt.get("enemy_key"): body["enemy_key"]=str(tgt["enemy_key"])
            s,r=call("POST",f"/campaigns/{cid}/combat/resolve-attack",body)
            log(f"  [{tag}] atk -> hit={r.get('hit')} dmg={r.get('damage')} dead={r.get('enemy_dead')} pHP_after={r.get('player_hp')}")
        else:
            s,r=call("POST",f"/campaigns/{cid}/combat/enemy-turn")
    log(f"  [{tag}] FIGHT TIMEOUT"); return None

# 1. enter until entry tile enemy-free (works around entry-combat soft-lock)
cid=None; run=None; tries=0
for tries in range(1,21):
    s,camp=call("POST","/campaigns",{"title":f"[SMOKE] L13c silnik #{tries}","system_id":"fantasy",
        "model_id":"default","owner_user_id":USER,"language":"pl","mode":"dungeon","status":"active"})
    cid=camp.get("id")
    call("POST",f"/characters/{HERO}/assign-campaign",{"campaign_id":cid,"user_id":USER})
    s,e=call("POST",f"/dungeons/{DKEY}/enter",{"character_id":HERO,"campaign_id":cid,"previous_campaign_id":None})
    if s!=200: log(f"enter failed {s}: {e}"); sys.exit(1)
    run=e["dungeon_run"]; g=run["graph"]
    entry_enemies=g["nodes"][g["entry_node"]]["content"].get("enemies")
    if not entry_enemies:
        log(f"ENTER ok try#{tries} cid={cid} entry={g['entry_node']} (enemy-free)"); break
log(f"GRAPH nodes={list(g['nodes'].keys())} entry={g['entry_node']} boss={g['boss_node']}")

# 2. pathfind entry->boss over doors_open
def path_to(g, start, goal):
    from collections import deque
    nodes=g["nodes"]; q=deque([(start,[])]); seen={start}
    while q:
        nid,p=q.popleft()
        if nid==goal: return p
        for d,t in (nodes[nid]["doors_open"] or {}).items():
            if t and t not in seen: seen.add(t); q.append((t,p+[(d,t)]))
    return None
path=path_to(g, g["entry_node"], g["boss_node"])
log(f"PATH to boss: {path}")

# 3. walk to boss, fighting en route
boss_combat=None
for d,target in path:
    s,mv=call("POST","/dungeons/move",{"character_id":HERO,"campaign_id":cid,"direction":d})
    tnode=g["nodes"].get(target,{})
    is_boss=tnode.get("content",{}).get("is_boss_tile")
    log(f"MOVE {d}->{target} ok={mv.get('ok')} blocked={mv.get('blocked')} reason={mv.get('reason')} combat={'Y' if mv.get('combat') else 'N'} boss={is_boss}")
    if not mv.get("ok"):
        log("  MOVE BLOCKED — abort walk"); break
    if mv.get("combat") is not None:
        c=fight(cid, tag=target)
        if is_boss: boss_combat=c

# 4. check run state for boss_choice_pending
s,rr=call("GET",f"/campaigns/{cid}/dungeon-run")
run2=rr.get("dungeon_run") or {}
log(f"AFTER BOSS: boss_choice_pending={run2.get('boss_choice_pending')} completed={run2.get('completed')} cycle={run2.get('cycle')}")

# 5. ENDLESS: go_deeper
if run2.get("boss_choice_pending"):
    s,bc=call("POST","/dungeons/boss-choice",{"character_id":HERO,"campaign_id":cid,"choice":"go_deeper"})
    log(f"GO_DEEPER {s}: new_cycle={bc.get('new_cycle')} seg_tiles={bc.get('new_segment_tile_count')} entry={bc.get('new_entry_node')} bossnode={bc.get('new_boss_node')}")
    # compare enemy scaling cycle1 vs cycle2 by inspecting new graph enemies' would-be level: just record cycle
else:
    log("NO boss_choice_pending — cannot test endless")

log("\nDONE cid="+str(cid))
