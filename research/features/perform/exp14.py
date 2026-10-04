import sys
from pathlib import Path

_R = Path(__file__).resolve()
while not (_R / "server.py").exists():
    _R = _R.parent
sys.path[:0] = [str(_R), str(_R / "research")]   # repo root (server, bwmcp) and research/ (bwlock, bwformat)
import sys, time, json
sys.path.insert(0, "research"); sys.path.insert(0, "research/features/perform")
from bwlock import hold
import server
from bwmcp.control.performdev import Perform, value_at, move
c = server.bw.call
P = Perform(server.bw)
def tidx(name):
    return [i for i, t in enumerate(c("get_session")["tracks"]) if t["name"] == name][0]
def case(label, name, kinds, total, extra):
    TR = tidx(name)
    tg = {"volume": {"kind": "volume", "track": TR}, "pan": {"kind": "pan", "track": TR}, "send0": {"kind": "send", "track": TR, "send": 0}}
    mv = {"volume": move(tg["volume"], 0.1, 0.7, 1, 3), "pan": move(tg["pan"], 0.1, 0.9, 1, 3), "send0": move(tg["send0"], 0.0, 0.7, 1, 3)}
    mv = {k: mv[k] for k in kinds}
    c("stop"); time.sleep(0.3); c("set_position", beats=0); time.sleep(0.4)
    a = dict(moves=list(mv.values()), total_beats=total, end_beat=total, mode="latch")
    a.update(extra)
    c("perform_record", **a)
    t0 = time.time()
    while time.time() - t0 < 12:
        st = P.status()
        if not st["running"] and st["phase"] != "selecting": break
        time.sleep(0.2)
    print(label, st["phase"], st["applied"], st["error"]); time.sleep(0.5)
    c("stop"); time.sleep(0.3); c("set_arranger_record", enabled=False); c("set_automation", write=False)
    c("set_position", beats=0); time.sleep(0.5); c("play"); time.sleep(0.3)
    out = []; t0 = time.time()
    while time.time() - t0 < 5:
        out.append((c("get_transport")["position"], {k: c("perform_read", target=tg[k]) for k in mv})); time.sleep(0.04)
    c("stop")
    for k in mv:
        pts = [(p, v[k]) for p, v in out if 1.3 < p < 3.7]
        print("  ", k, "range", round(min(v for _, v in pts), 3), round(max(v for _, v in pts), 3), "rms", round((sum((v - value_at(mv[k], p)) ** 2 for p, v in pts) / len(pts)) ** 0.5, 3))
def mk(name):
    n0 = len(c("get_session")["tracks"]); c("create_audio_track"); time.sleep(1.0)
    ts = c("get_session")["tracks"]; assert len(ts) == n0 + 1, "track count changed unexpectedly"
    c("set_track_name", track_index=n0, name=name); time.sleep(0.3)
def cleanup():
    for _ in range(10):
        ts = c("get_session")["tracks"]
        z = [i for i, t in enumerate(ts) if t["name"].startswith("ZZperf")]
        if not z: break
        c("delete_track", track_index=z[-1]); time.sleep(0.6)
with hold("perform: exp14"):
    try:
        for n in ("ZZperfA", "ZZperfB", "ZZperfC"): mk(n)
        case("A fresh vol, from_beat 0, end 5", "ZZperfA", ["volume"], 5, {"from_beat": 0})
        case("B fresh 3 targets total 9", "ZZperfB", ["volume", "pan", "send0"], 9, {})
        case("C 3 targets total 5 from_beat 0", "ZZperfC", ["volume", "pan", "send0"], 5, {"from_beat": 0})
    finally:
        c("stop"); c("set_arranger_record", enabled=False); c("set_automation", write=False)
        cleanup()
