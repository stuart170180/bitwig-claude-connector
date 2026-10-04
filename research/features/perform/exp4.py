import sys
from pathlib import Path

_R = Path(__file__).resolve()
while not (_R / "server.py").exists():
    _R = _R.parent
sys.path[:0] = [str(_R), str(_R / "research")]   # repo root (server, bwmcp) and research/ (bwlock, bwformat)
import sys, time
sys.path.insert(0, "research")
from bwlock import hold
import server
c = server.bw.call
def st(l):
    time.sleep(0.4); t = c("get_transport"); print(l, {k: t[k] for k in ("playing","arranger_record","automation_write","automation_mode")})
with hold("perform: exp4 state probe"):
    c("stop"); st("start")
    c("set_arranger_record", enabled=True); st("rec on")
    c("set_automation", write=True); st("write on")
    c("set_position", beats=0); st("pos0")
    c("play"); st("play")
    time.sleep(1); st("1s")
    c("stop"); st("stop")
    c("set_arranger_record", enabled=False); c("set_automation", write=False); st("cleanup")
