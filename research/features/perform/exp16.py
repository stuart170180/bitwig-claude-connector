import sys, time, json
sys.path.insert(0, "research"); sys.path.insert(0, "research/features/perform")
from bwlock import hold
import server
from performdev import Perform, value_at, move
c = server.bw.call
P = Perform(server.bw)
def tidx(name):
    return [i for i, t in enumerate(c("get_session")["tracks"]) if t["name"] == name][0]
def case(label, tg, m, **extra):
    TR = tidx("ZZperfD")
    c("stop"); time.sleep(0.3); c("set_position", beats=0); time.sleep(0.4)
    P.record([m], total_beats=5, select={"track": TR, "device": 0}, **extra) if "set_mode" not in extra else c("perform_record", moves=[m], total_beats=5, end_beat=5, select={"track": TR, "device": 0}, **extra)
    t0 = time.time(); live = []
    while time.time() - t0 < 14:
        st = P.status()
        if st["phase"] == "running": live.append((round(st["position"], 1), round(c("perform_read", target=tg), 3), c("get_transport")["automation_write"]))
        if not st["running"] and st["phase"] != "selecting": break
        time.sleep(0.4)
    print(label, st["phase"], st["applied"], "live", live[::3]); time.sleep(0.5)
    c("stop"); time.sleep(0.3); c("set_arranger_record", enabled=False); c("set_automation", write=False)
    c("set_position", beats=0); time.sleep(0.5); c("play"); time.sleep(0.3)
    out = []; t0 = time.time()
    while time.time() - t0 < 4.5:
        out.append((c("get_transport")["position"], c("perform_read", target=tg))); time.sleep(0.04)
    c("stop")
    pts = [(p, v) for p, v in out if 1.3 < p < 3.7]
    print("   replay range", round(min(v for _, v in pts), 3), round(max(v for _, v in pts), 3), "rms", round((sum((v - value_at(m, p)) ** 2 for p, v in pts) / len(pts)) ** 0.5, 3))
def mk(name):
    n0 = len(c("get_session")["tracks"]); c("create_audio_track"); time.sleep(1.0)
    assert len(c("get_session")["tracks"]) == n0 + 1
    c("set_track_name", track_index=n0, name=name); time.sleep(0.3)
def cleanup():
    for _ in range(10):
        z = [i for i, t in enumerate(c("get_session")["tracks"]) if t["name"].startswith("ZZperf")]
        if not z: break
        c("delete_track", track_index=z[-1]); time.sleep(0.6)
with hold("perform: exp16 device variants"):
    print([t["name"] for t in c("get_session")["tracks"]])
    try:
        mk("ZZperfD"); server.device_insert(tidx("ZZperfD"), "EQ+"); time.sleep(0.5)
        tg = {"kind": "remote", "index": 0}; m = move(tg, 0.1, 0.9, 1, 3)
        TR = tidx("ZZperfD")
        tv = {"kind": "volume", "track": TR}; mv_ = move(tv, 0.2, 0.7, 1, 3, "exp")
        # combined remote + volume in one plan: reuse case() machinery per target but record once
        c("stop"); time.sleep(0.3); c("set_position", beats=0); time.sleep(0.4)
        P.record([m, mv_], total_beats=5, select={"track": TR, "device": 0})
        t0 = time.time()
        while time.time() - t0 < 14:
            st = P.status()
            if not st["running"] and st["phase"] != "selecting": break
            time.sleep(0.4)
        print("combined", st["phase"], st["applied"], st["error"]); time.sleep(0.5)
        c("stop"); time.sleep(0.3); c("set_arranger_record", enabled=False); c("set_automation", write=False)
        c("set_position", beats=0); time.sleep(0.5); c("play"); time.sleep(0.3)
        out = []; t0 = time.time()
        while time.time() - t0 < 4.5:
            out.append((c("get_transport")["position"], c("perform_read", target=tg), c("perform_read", target=tv))); time.sleep(0.04)
        c("stop")
        for nm, mm, ix in (("remote", m, 1), ("volume", mv_, 2)):
            pts = [(o[0], o[ix]) for o in out if 1.3 < o[0] < 3.7]
            print("  ", nm, "range", round(min(v for _, v in pts), 3), round(max(v for _, v in pts), 3), "rms", round((sum((v - value_at(mm, p)) ** 2 for p, v in pts) / len(pts)) ** 0.5, 3))
    finally:
        cleanup()
