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
def run(label, mode, touch, rec, wr=True):
    c("stop"); time.sleep(0.3)
    c("set_arranger_record", enabled=rec); 
    plan = {"moves": [{"target": T, "from": 0.1, "to": 0.7, "start_beat": 1, "length_beats": 3, "curve": "linear"}],
            "play": True, "from_beat": 0, "stop_at_end": True, "touch": touch, "mode": mode, "end_beat": 5, "write": wr, "keep_record": False}
    c("perform_plan", **plan)
    mid = None; t0 = time.time()
    while time.time() - t0 < 5:
        st = c("perform_status")
        if st["position"] > 2 and mid is None:
            tr = c("get_transport"); mid = {k: tr[k] for k in ("arranger_record","automation_write","automation_mode")}
        if not st["running"]: break
        time.sleep(0.15)
    time.sleep(0.5)
    s = replay(T, 3.5, preset=0.3)
    vals = [v for p, v in s if p > 0.2]
    print(label, "mid", mid, "replay range", min(vals), max(vals), "sample", s[10:40:6])
with hold("perform: exp3 variants"):
    for cfg in [("latch+touch+rec", "latch", True, True), ("write+touch+rec", "write", True, True), ("touch+touch+rec", "touch", True, True), ("latch notouch rec", "latch", False, True), ("latch touch norec", "latch", True, False)]:
        run(*cfg)
