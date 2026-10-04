import sys
from pathlib import Path

_R = Path(__file__).resolve()
while not (_R / "server.py").exists():
    _R = _R.parent
sys.path[:0] = [str(_R), str(_R / "research")]   # repo root (server, bwmcp) and research/ (bwlock, bwformat)
import sys, time
sys.path.insert(0, "research"); sys.path.insert(0, "research/features/perform")
from bwlock import hold
import server
from replay import replay
c = server.bw.call
idx = int(sys.argv[1]); T = {"kind": "volume", "track": idx}
with hold("perform: exp2"):
    s = replay(T, 3.0)
    print(s[:3], s[-3:])
    print({k: v for k, v in c("get_transport").items() if k in ("arranger_record","automation_write","automation_mode","playing")})
