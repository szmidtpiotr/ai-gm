import json, urllib.request, urllib.error, subprocess
API="http://192.168.1.61:8100/api"; HERO=2; DKEY="goblin_warren"; USER=1
def call(m,p,pl=None,t=180):
    d=json.dumps(pl).encode() if pl is not None else None
    r=urllib.request.Request(API+p,data=d,headers={"Content-Type":"application/json"},method=m)
    try:
        with urllib.request.urlopen(r,timeout=t) as x: return x.status,json.loads(x.read().decode())
    except urllib.error.HTTPError as e:
        try:return e.code,json.loads(e.read().decode(errors="replace"))
        except:return e.code,{}
    except Exception as e:return 0,{"error":str(e)}
def ssh_sql(s): subprocess.run(["ssh","claude@192.168.1.61",f'docker exec ai-gm-dev-backend-1 sqlite3 /data/ai_gm.db "{s}"'],capture_output=True,text=True)
ssh_sql("DELETE FROM character_dungeon_runs WHERE character_id=2;")
s,c=call("POST","/campaigns",{"title":"[SMOKE] narr689b","system_id":"fantasy","model_id":"default","owner_user_id":USER,"language":"pl","mode":"dungeon","status":"active"})
cid=c["id"]; call("POST",f"/characters/{HERO}/assign-campaign",{"campaign_id":cid,"user_id":USER})
s,e=call("POST",f"/dungeons/{DKEY}/enter",{"character_id":HERO,"campaign_id":cid})
print("entry tile:",e["dungeon_run"]["graph"]["nodes"][e["dungeon_run"]["graph"]["entry_node"]]["content"]["room_description"])
for msg in ["co mam teraz zrobić?","rozejrzyj się dookoła"]:
    s,t=call("POST",f"/campaigns/{cid}/turns",{"character_id":HERO,"text":msg})
    narr=(t.get("prose") or "")[:220]
    forest=any(w in narr.lower() for w in ["las","drzew","korona","puszcz","leśn","pole "])
    print(f"\n[{msg}] esc={t.get('travel_escalation_level')} forest={forest}\n  {narr!r}")
ssh_sql("DELETE FROM character_dungeon_runs WHERE character_id=2;")
