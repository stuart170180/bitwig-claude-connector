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
with hold("perform: exp13 multi target record+replay"):
    TR = tidx("ZZperf2")
    targets = {"volume": {"kind": "volume", "track": TR}, "pan": {"kind": "pan", "track": TR},
               "send0": {"kind": "send", "track": TR, "send": 0},
               "remote1": {"kind": "remote", "index": 1}, "direct_freq1": {"kind": "direct", "id": "CONTENTS/FREQ1"}}
    moves = {"volume": move(targets["volume"], 0.2, 0.8, 1, 6, "linear"), "pan": move(targets["pan"], 0.1, 0.9, 1, 6, "ease"),
             "send0": move(targets["send0"], 0.0, 0.7, 1, 6, "exp"), "remote1": move(targets["remote1"], 0.1, 0.9, 1, 6, "linear"),
             "direct_freq1": move(targets["direct_freq1"], 0.2, 0.9, 1, 6, "linear")}
    try:
        c("stop"); c("set_position", beats=0); c("set_track_volume", track_index=TR, value=0.5); time.sleep(0.3)
        SEL = {"track": TR, "device": 0} if "dev" in sys.argv else None
        if SEL is None:
            moves = {k: v for k, v in moves.items() if k in ("volume", "pan", "send0")}; targets = {k: targets[k] for k in moves}
        print("rec", P.record(list(moves.values()), total_beats=9, select=SEL))
        t0 = time.time()
        while time.time() - t0 < 14:
            st = P.status()
            if st["phase"] == "running": print("  live", round(st["position"], 2), {k: round(c("perform_read", target=t), 3) for k, t in targets.items() if k in ("volume", "pan")}, c("get_transport")["playing"])
            if not st["running"] and st["phase"] != "selecting": break
            time.sleep(0.3)
        print(P.status()); time.sleep(0.5)
        assert tidx("ZZperf2") == TR
        c("stop"); time.sleep(0.3); c("set_arranger_record", enabled=False); c("set_automation", write=False)
        c("set_position", beats=0); time.sleep(0.5)
        c("play"); time.sleep(0.3)
        out = []; t0 = time.time()
        while time.time() - t0 < 8:
            row = {"pos": c("get_transport")["position"]}
            for k, t in targets.items():
                try: row[k] = c("perform_read", target=t)
                except Exception: row[k] = None
            out.append(row); time.sleep(0.04)
    finally:
        c("stop"); c("set_arranger_record", enabled=False); c("set_automation", write=False)
    json.dump(out, open("research/features/perform/exp13_samples.json", "w"))
    for k in targets:
        pts = [(r["pos"], r[k]) for r in out if r[k] is not None and 1.3 < r["pos"] < 6.7]
        if not pts: print(k, "no samples"); continue
        vs = [v for _, v in pts]
        best = min(((sum((v - value_at(moves[k], p - d)) ** 2 for p, v in pts) / len(pts)) ** 0.5, d) for d in [x / 100 for x in range(-40, 61, 2)])
        raw = (sum((v - value_at(moves[k], p)) ** 2 for p, v in pts) / len(pts)) ** 0.5
        print(k, "n", len(pts), "range", round(min(vs), 3), round(max(vs), 3), "rms err no offset", round(raw, 4), "best offset", best[1], "rms", round(best[0], 4))
