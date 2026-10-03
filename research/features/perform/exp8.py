import sys, time
sys.path.insert(0, "research"); sys.path.insert(0, "research/features/perform")
from bwlock import hold
import server
from replay import replay
c = server.bw.call
VARS = [("write off + touch", dict(write=False)),
        ("write on, no touch", dict(touch=False)),
        ("latch + touch", dict(mode="latch")),
        ("mode write + touch", dict(mode="write")),
        ("mode touch + touch", dict(mode="touch")),
        ("arranger record + touch", dict(record=True, mode="latch")),
        ("arranger record, no touch", dict(record=True, touch=False))]
with hold("perform: exp8 variants"):
    ss = c("get_session")["tracks"]
    mine = [i for i, t in enumerate(ss) if t["name"].startswith("Audio ") and i >= 7][:7]
    mine += [i for i, t in enumerate(ss) if t["name"].startswith("ZZperf")]
    print("mine", mine, [ss[i]["name"] for i in mine])
    for k, i in enumerate(mine):
        if ss[i]["name"].startswith("Audio"):
            c("set_track_name", track_index=i, name="ZZperf%d" % (k + 1))
    time.sleep(0.5)
    for (label, kw), idx in zip(VARS, mine):
        T = {"kind": "volume", "track": idx}
        c("stop"); time.sleep(0.3)
        plan = {"moves": [{"target": T, "from": 0.1, "to": 0.7, "start_beat": 1, "length_beats": 3}],
                "play": True, "from_beat": 0, "stop_at_end": True, "end_beat": 5}
        plan.update(kw); rec = plan.pop("record", False)
        c("set_track_volume", track_index=idx, value=0.3)
        print(label, c("perform_record" if rec else "perform_plan", **plan))
        t0 = time.time(); mids = []
        while time.time() - t0 < 6:
            st = c("perform_status"); tr = c("get_transport")
            mids.append((st["running"], st["phase"], round(st["position"], 1), st["applied"], tr["playing"], tr["arranger_record"], tr["automation_write"], tr["automation_mode"]))
            if not st["running"] and st["phase"] != "waiting": break
            time.sleep(0.4)
        print("  ", mids[::3], c("perform_status").get("error"))
        time.sleep(0.5)
        s = replay(T, 3.5)
        vals = [v for p, v in s if p > 1.2]
        print("  replay", min(vals), max(vals), s[10:40:8])
