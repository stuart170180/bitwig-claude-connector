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
def run(label, **kw):
    try: c("perform_clear_automation", target=T); cl = "cleared"
    except Exception as e: cl = "clear failed: %s" % str(e)[:60]
    c("stop"); time.sleep(0.3)
    plan = {"moves": [{"target": T, "from": 0.1, "to": 0.7, "start_beat": 1, "length_beats": 3, "curve": "linear"}],
            "play": True, "from_beat": 0, "stop_at_end": True, "end_beat": 5}
    plan.update(kw)
    rec = plan.pop("record", False)
    c("perform_record" if rec else "perform_plan", **plan)
    t0 = time.time(); mid = None
    while time.time() - t0 < 6:
        st = c("perform_status")
        if st["position"] > 2 and mid is None:
            tr = c("get_transport"); mid = (tr["arranger_record"], tr["automation_write"], tr["automation_mode"])
        if not st["running"]: break
        time.sleep(0.15)
    time.sleep(0.5)
    s = replay(T, 3.5, preset=0.3)
    vals = [v for p, v in s if p > 1.2]
    print(label, cl, "mid(rec,write,mode)", mid, "replay range", min(vals), max(vals))
with hold("perform: exp5 clean variants"):
    run("write off + touch", write=False)
    run("write on, no touch", touch=False)
    run("latch + touch", mode="latch")
    run("write-mode + touch", mode="write")
    run("touch-mode + touch", mode="touch")
    run("arranger record + touch", record=True, mode="latch")
    run("arranger record, no touch", record=True, touch=False)
