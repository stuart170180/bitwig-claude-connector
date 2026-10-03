import sys, time
sys.path.insert(0, "research")
from bwlock import hold
import server
c = server.bw.call
with hold("perform: dbg"):
    T = {"kind": "volume", "track": 7}
    c("stop"); time.sleep(0.3)
    print(c("perform_plan", moves=[{"target": T, "from": 0.1, "to": 0.7, "start_beat": 1, "length_beats": 3}], play=True, from_beat=0, stop_at_end=True, end_beat=5))
    for i in range(12):
        print(c("perform_status")); print({k: v for k, v in c("get_transport").items() if k in ("playing","position")}); time.sleep(0.4)
    c("perform_abort"); c("stop")
