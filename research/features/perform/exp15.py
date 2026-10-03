import sys, time, json
sys.path.insert(0, "research"); sys.path.insert(0, "research/features/perform")
from bwlock import hold
import server
from performdev import Perform, value_at, move
c = server.bw.call
P = Perform(server.bw)
def tidx(name):
    return [i for i, t in enumerate(c("get_session")["tracks"]) if t["name"] == name][0]
def mk(name):
    n0 = len(c("get_session")["tracks"]); c("create_audio_track"); time.sleep(1.0)
    assert len(c("get_session")["tracks"]) == n0 + 1
    c("set_track_name", track_index=n0, name=name); time.sleep(0.3)
def cleanup():
    for _ in range(10):
        z = [i for i, t in enumerate(c("get_session")["tracks"]) if t["name"].startswith("ZZperf")]
        if not z: break
        c("delete_track", track_index=z[-1]); time.sleep(0.6)
with hold("perform: exp15 device targets"):
    try:
        TR = tidx("ZZperfD")
        print(c("list_devices", track_index=TR) if False else "")
        if not server.deep.tree(TR): server.device_insert(TR, "EQ+"); time.sleep(0.5)
        tg = {"direct_freq1": {"kind": "direct", "id": "CONTENTS/FREQ1"}, "direct_gain1": {"kind": "direct", "id": "CONTENTS/GAIN1"}, "remote0": {"kind": "remote", "index": 0}}
        mv = {"direct_freq1": move(tg["direct_freq1"], 0.2, 0.8, 1, 3, "ease"), "direct_gain1": move(tg["direct_gain1"], 0.5, 0.8, 1, 3, "linear"),
              "remote0": move(tg["remote0"], 0.1, 0.9, 1, 3, "linear")}
        c("stop"); time.sleep(0.3); c("set_position", beats=0); time.sleep(0.4)
        print(P.record(list(mv.values()), total_beats=5, select={"track": TR, "device": 0}))
        t0 = time.time()
        while time.time() - t0 < 14:
            st = P.status()
            if not st["running"] and st["phase"] != "selecting": break
            time.sleep(0.2)
        print(st["phase"], st["applied"], st["error"]); time.sleep(0.5)
        c("stop"); time.sleep(0.3); c("set_arranger_record", enabled=False); c("set_automation", write=False)
        c("set_position", beats=0); time.sleep(0.5); c("play"); time.sleep(0.3)
        out = []; t0 = time.time()
        while time.time() - t0 < 5:
            row = {}
            for k in mv:
                try: row[k] = c("perform_read", target=tg[k])
                except Exception as e: row[k] = None
            out.append((c("get_transport")["position"], row)); time.sleep(0.04)
        c("stop")
        for k in mv:
            pts = [(p, v[k]) for p, v in out if 1.3 < p < 3.7 and v[k] is not None]
            if not pts: print(k, "no samples"); continue
            print("  ", k, "range", round(min(v for _, v in pts), 3), round(max(v for _, v in pts), 3), "rms", round((sum((v - value_at(mv[k], p)) ** 2 for p, v in pts) / len(pts)) ** 0.5, 3))
    finally:
        c("stop"); c("set_arranger_record", enabled=False); c("set_automation", write=False)
        cleanup()
