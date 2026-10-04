import sys
from pathlib import Path

_R = Path(__file__).resolve()
while not (_R / "server.py").exists():
    _R = _R.parent
sys.path[:0] = [str(_R), str(_R / "research")]   # repo root (server, bwmcp) and research/ (bwlock, bwformat)
import sys, time, json
sys.path.insert(0, "research")
from bwlock import hold
import server
c = server.bw.call

def replay(T, seconds=5.0, from_beat=0.0, step=0.05, preset=None):
    c("stop"); c("set_arranger_record", enabled=False); c("set_automation", write=False)
    if preset is not None:
        c("perform_touch_set", target=T, value=preset)
    c("perform_restore_control", target=T)
    c("set_position", beats=from_beat); time.sleep(0.3)
    c("play"); out = []; t0 = time.time()
    while time.time() - t0 < seconds:
        p = c("get_transport")["position"]; v = c("perform_read", target=T)
        out.append((round(p, 3), round(v, 4))); time.sleep(step)
    c("stop")
    return out

if __name__ == "__main__":
    idx = int(sys.argv[1]); T = {"kind": "volume", "track": idx}
    with hold("perform: replay"):
        s = replay(T, 5.0, preset=0.3)
        for p, v in s[::3]: print(p, v)
