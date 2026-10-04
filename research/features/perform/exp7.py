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
VARS = [("write off + touch", dict(write=False)),
        ("write on, no touch (latch)", dict(touch=False)),
        ("latch + touch", dict(mode="latch")),
        ("mode write + touch", dict(mode="write")),
        ("mode touch + touch", dict(mode="touch")),
        ("arranger record + touch", dict(record=True, mode="latch")),
        ("arranger record, no touch", dict(record=True, touch=False))]
def names(): return [t["name"] for t in c("get_session")["tracks"]]
with hold("perform: exp7 variants on fresh tracks"):
    n0 = len(names())
    for i in range(len(VARS)):
        c("create_audio_track"); time.sleep(0.6)
    ns = names(); print(ns)
    for i, (label, kw) in enumerate(VARS):
        idx = n0 + i; T = {"kind": "volume", "track": idx}
        c("stop"); time.sleep(0.2)
        plan = {"moves": [{"target": T, "from": 0.1, "to": 0.7, "start_beat": 1, "length_beats": 3}],
                "play": True, "from_beat": 0, "stop_at_end": True, "end_beat": 5}
        plan.update(kw); rec = plan.pop("record", False)
        c("set_track_volume", track_index=idx, value=0.3)
        c("perform_record" if rec else "perform_plan", **plan)
        t0 = time.time(); mid = None
        while time.time() - t0 < 6:
            st = c("perform_status")
            if st["position"] > 2 and mid is None:
                tr = c("get_transport"); mid = (tr["arranger_record"], tr["automation_write"], tr["automation_mode"])
            if not st["running"]: break
            time.sleep(0.15)
        time.sleep(0.5)
        s = replay(T, 3.5)
        vals = [v for p, v in s if p > 1.2]
        print(label, "| mid(rec,write,mode)", mid, "| replay", min(vals), max(vals), "| final status", c("perform_status")["phase"])
