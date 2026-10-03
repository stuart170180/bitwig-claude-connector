import sys, time
sys.path.insert(0, "research"); sys.path.insert(0, ".")
from bwlock import hold
import server
with hold("midi: debug"):
    try:
        server.create_track("instrument", name="ZZmidi A")
        a = [t["index"] for t in server.get_session()["tracks"] if t["name"] == "ZZmidi A"][0]
        print(server.write_chords(a, 0, chords=["Am","F","C","G"], key="A", scale="minor", rhythm="arp_up"))
        time.sleep(1); print(server.get_track(a)["clips"], server.get_clip_notes(a, 0)["count"])
        print(server.write_chords(a, 2, chords=["Am","F","C","G"], key="A", scale="minor", rhythm="stabs"))
        print("slot2", server.get_clip_notes(a, 2)["count"])
        print(server.write_notes(a, 3, [{"pitch":60,"start":0,"duration":1,"velocity":90}], 4, "x")); print("slot3", server.get_clip_notes(a, 3)["count"])
        time.sleep(3); print("slot0 again", server.get_clip_notes(a, 0)["count"], server.get_track(a)["clips"])
    finally:
        for t in sorted(server.get_session()["tracks"], key=lambda t: -t["index"]):
            if t["name"] == "ZZmidi A": server.delete_track(t["index"])
