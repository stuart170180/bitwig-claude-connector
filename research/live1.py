import sys
from pathlib import Path

_R = Path(__file__).resolve()
while not (_R / "server.py").exists():
    _R = _R.parent
sys.path[:0] = [str(_R), str(_R / "research")]   # repo root (server, bwmcp) and research/ (bwlock, bwformat)
import server,time,json
bw=server.bw
L=r"C:\Program Files\Bitwig Studio\Library"
bw.call("create_instrument_track",position=-1); time.sleep(0.8)
s=bw.call("get_session"); idx=len(s["tracks"])-1; print("scratch idx",idx,[t["name"] for t in s["tracks"]])
bw.call("set_track_name",track_index=idx,name="ZZ research") if False else None
import json
print([c for c in dir(bw)][:5])
