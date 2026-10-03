import sys, time, json
sys.path.insert(0, "research")
from bwlock import hold
import server
bw = server.bw
c = bw.call

def sess():
    return c("get_session")

def sample(target, seconds, step=0.08):
    out = []; t0 = time.time()
    while time.time() - t0 < seconds:
        p = c("get_transport")["position"]; v = c("perform_read", target=target)
        out.append((round(p, 3), round(v, 4))); time.sleep(step)
    return out

with hold("perform: exp1 volume ramp"):
    s0 = sess(); n0 = len(s0["tracks"]) if "tracks" in s0 else None
    tr0 = c("get_transport")
    print("initial", {k: tr0[k] for k in ("playing","arranger_record","automation_write","automation_mode","launch_quantization")})
    c("create_audio_track"); time.sleep(1.0)
    s = sess(); tracks = s["tracks"]; idx = len(tracks) - 1
    print("new idx", idx, tracks[idx].get("name"))
    c("set_track_name", track_index=idx, name="ZZperf"); 
    try:
        T = {"kind": "volume", "track": idx}
        c("set_track_volume", track_index=idx, value=0.3)
        res = {}
        # arranger record ON, write ON, touch, ramp 0.1 -> 0.7 over 4 beats starting beat 2
        plan = {"moves": [{"target": T, "from": 0.1, "to": 0.7, "start_beat": 2, "length_beats": 4, "curve": "linear"}],
                "play": True, "from_beat": 0, "stop_at_end": True, "touch": True, "mode": "latch", "end_beat": 8}
        c("set_arranger_record", enabled=True)
        print("start", c("perform_plan", **plan))
        t0 = time.time(); live = []
        while time.time() - t0 < 6:
            st = c("perform_status"); live.append((st["phase"], st["position"], st["applied"]))
            if not st["running"]: break
            time.sleep(0.2)
        print("status end", c("perform_status")); print(live[::4])
        time.sleep(0.5)
        print("has_automation x2", c("perform_has_automation", target=T)); time.sleep(0.3); print(c("perform_has_automation", target=T))
        tr = c("get_transport"); print("after", {k: tr[k] for k in ("playing","arranger_record","automation_write","automation_mode")})
        c("set_arranger_record", enabled=False); c("set_automation", write=False)
        # replay
        c("perform_restore_control", target=T); c("stop") if False else None
        c("set_position", position=0) if False else None
    finally:
        pass
    json.dump({"idx": idx}, open("research/features/perform/exp1_state.json", "w"))
