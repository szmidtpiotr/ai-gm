import json, urllib.request, urllib.error, subprocess
API="http://192.168.1.61:8100/api"; HERO=2; DKEY="goblin_warren"; USER=1
def call(m,p,pl=None,t=180):
    d=json.dumps(pl).encode() if pl is not None else None
    r=urllib.request.Request(API+p,data=d,headers={"Content-Type":"application/json"},method=m)
    try:
        with urllib.request.urlopen(r,timeout=t) as x: return x.status,json.loads(x.read().decode())
    except urllib.error.HTTPError as e:
        try: b=json.loads(e.read().decode(errors="replace"))
        except Exception: b={}
        return e.code,b
    except Exception as e: return 0,{"error":str(e)}
def ssh_sql(s): subprocess.run(["ssh","claude@192.168.1.61",f'docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db "{s}"'],capture_output=True,text=True)
ssh_sql("DELETE FROM character_dungeon_runs WHERE character_id=2;")
s,c=call("POST","/campaigns",{"title":"[SMOKE] narr689","system_id":"fantasy","model_id":"default","owner_user_id":USER,"language":"pl","mode":"dungeon","status":"active"})
cid=c["id"]; call("POST",f"/characters/{HERO}/assign-campaign",{"campaign_id":cid,"user_id":USER})
s,e=call("POST",f"/dungeons/{DKEY}/enter",{"character_id":HERO,"campaign_id":cid})
g=e["dungeon_run"]["graph"]; entry=g["entry_node"]
edesc=g["nodes"][entry]["content"]["room_description"]
print("ENTER ok. entry tile desc:",repr(edesc))
# free-text turn (the exact action that produced forest narration before)
s,t=call("POST",f"/campaigns/{cid}/turns",{"character_id":HERO,"text":"Opisz mi salę"})
print("turn status",s)
narr=(t.get("prose") or (t.get("result") or {}).get("message") or "")[:400]
print("NARRATIVE:",repr(narr))
print("travel_escalation_level:",t.get("travel_escalation_level"))
sa=t.get("suggested_actions") or []
print("suggested_actions types:",[a.get("type") for a in sa if isinstance(a,dict)])
forest=any(w in narr.lower() for w in ["las","drzew","korona","pni","puszcz","leśn"])
travel=any(isinstance(a,dict) and a.get("type")=="travel" for a in sa)
print("\nRESULT: forest_words=%s travel_hooks=%s escalation=%s" % (forest, travel, t.get("travel_escalation_level")))
print("PASS" if (not forest and not travel and (t.get("travel_escalation_level") in (0,None))) else "CHECK")
ssh_sql("DELETE FROM character_dungeon_runs WHERE character_id=2;")
