import sys, time
sys.path.insert(0, "research"); sys.path.insert(0, "research/features/perform")
from bwlock import hold
import server
from performdev import Perform, value_at, volume_ramp, pan_ramp, send_ramp, move
c = server.bw.call
with hold("perform: exp9 multi target"):
    ss = c("get_session")["tracks"]; nm = [t["name"] for t in ss]
    ix = {n: i for i, n in enumerate(nm) if n.startswith("ZZperf")}
    print(ix)
    # static seek verification of the volume ramp written on ZZperf3 (latch+touch, 0.1->0.7 over beats 1..4)
    T = {"kind": "volume", "track": ix["ZZperf3"]}
    c("stop"); c("set_arranger_record", enabled=False); c("set_automation", write=False)
    c("perform_restore_control", target=T)
    for b in (0.0, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0):
        c("set_position", beats=b); time.sleep(0.35)
        v = c("perform_read", target=T); exp = 0.1 + 0.6 * min(max((b - 1) / 3, 0), 1)
        print("static", b, round(v, 4), "expected", round(exp, 4))
    # FX track + device
    c("create_effect_track"); time.sleep(0.8)
    ss = c("get_session")["tracks"]; nm = [t["name"] for t in ss]
    fx = [i for i, t in enumerate(ss) if t["name"].startswith("FX") or t["name"].startswith("Effect")]
    print("fx candidates", fx, [nm[i] for i in fx])
