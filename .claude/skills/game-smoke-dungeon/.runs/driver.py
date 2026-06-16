import json, urllib.request, urllib.error, sys, time

API="http://192.168.1.61:8100/api"
HERO=2
DKEY="goblin_warren"
USER=1

def call(method, path, payload=None, timeout=120):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(API+path, data=data,
        headers={"Content-Type":"application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try: body=json.loads(e.read().decode(errors="replace"))
        except Exception: body={"raw":"?"}
        return e.code, body
    except Exception as e:
        return 0, {"error":str(e)}

def p(tag, obj):
    print(f"\n### {tag}")
    print(json.dumps(obj, ensure_ascii=False, default=str)[:1500])

# 1. create dungeon campaign
s,camp = call("POST","/campaigns",{"title":"[SMOKE] L13c silnik","system_id":"fantasy",
    "model_id":"default","owner_user_id":USER,"language":"pl","mode":"dungeon","status":"active"})
cid = camp.get("id") or (camp.get("campaign") or {}).get("id")
p(f"create campaign {s} cid={cid}", camp)

# 2. assign hero
s,a = call("POST",f"/characters/{HERO}/assign-campaign",{"campaign_id":cid,"user_id":USER})
p(f"assign {s}", a)

# 3. enter
s,e = call("POST",f"/dungeons/{DKEY}/enter",{"character_id":HERO,"campaign_id":cid,"previous_campaign_id":None})
p(f"enter {s}", e)
if s!=200:
    print("ENTER FAILED"); sys.exit(1)
run = e["dungeon_run"]
graph = run["graph"]
print("\nENTRY NODE:", graph["entry_node"], "BOSS NODE:", graph["boss_node"])
print("NODES:")
for nid,n in graph["nodes"].items():
    cont=n["content"]
    print(f"  {nid} tile={cont.get('tile_id')} '{cont.get('label')}' boss={cont.get('is_boss_tile')} "
          f"enemies={[x.get('enemy_key') for x in cont.get('enemies',[])]} items={bool(cont.get('items'))} "
          f"doors_open={n['doors_open']}")

# 4. one move from entry through first open door -> dump combat shape
entry = graph["entry_node"]
doors = graph["nodes"][entry]["doors_open"]
opendir = [d for d,t in doors.items() if t]
print("\nENTRY open dirs:", doors)
if opendir:
    d=opendir[0]
    s,mv = call("POST","/dungeons/move",{"character_id":HERO,"campaign_id":cid,"direction":d})
    p(f"move {d} {s}", mv)
    s,cb = call("GET",f"/campaigns/{cid}/combat")
    p(f"combat after move {s}", cb)
print("\nCID=",cid)
