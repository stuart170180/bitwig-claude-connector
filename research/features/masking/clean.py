import sys
from pathlib import Path

_R = Path(__file__).resolve()
while not (_R / "server.py").exists():
    _R = _R.parent
sys.path[:0] = [str(_R), str(_R / "research")]   # repo root (server, bwmcp) and research/ (bwlock, bwformat)
import sys,time
sys.path.insert(0,"../.."); sys.path.insert(0,"../../.."); 
from bwlock import hold
import server
mine=("ZZ Kick","ZZ Bass","ZZ Pad","ZZ Lead","ZZ Empty")
with hold("masking: cleanup"):
    for _ in range(8):
        ts=[t for t in server.bw.call("get_session")["tracks"] if t["name"] in mine or t["solo"]]
        for t in ts:
            if t["solo"]: server.bw.call("set_track_solo",track_index=t["index"],value=False)
        ts=[t for t in ts if t["name"] in mine]
        if not ts: break
        server.delete_track(ts[-1]["index"]); time.sleep(0.7)
    print([(t["name"],t["solo"]) for t in server.bw.call("get_session")["tracks"]])
