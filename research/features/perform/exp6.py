import sys, time
sys.path.insert(0, "research"); sys.path.insert(0, "research/features/perform")
from bwlock import hold
import server
from replay import replay
c = server.bw.call
idx = int(sys.argv[1]); T = {"kind": "volume", "track": idx}
with hold("perform: exp6"):
    print(c("get_transport")["playing"])
    for pre in (None, 0.3):
        s = replay(T, 3.5, preset=pre)
        vals = [v for p, v in s if p > 1.2]
        print("preset", pre, min(vals), max(vals), s[8:30:7])
