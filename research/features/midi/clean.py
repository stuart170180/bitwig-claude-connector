import sys, time
sys.path.insert(0, "research"); sys.path.insert(0, ".")
from bwlock import hold
import server
with hold("midi: cleanup"):
    for _ in range(3):
        for t in sorted(server.get_session()["tracks"], key=lambda t: -t["index"]):
            if t["name"].startswith("ZZmidi"): server.delete_track(t["index"]); time.sleep(1.5)
        time.sleep(1.5)
    s = server.get_session(); print([t["name"] for t in s["tracks"]], s["tempo"], server.get_transport().get("playing"))
