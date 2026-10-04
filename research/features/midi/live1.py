import sys
from pathlib import Path

_R = Path(__file__).resolve()
while not (_R / "server.py").exists():
    _R = _R.parent
sys.path[:0] = [str(_R), str(_R / "research")]   # repo root (server, bwmcp) and research/ (bwlock, bwformat)
import sys, os, time, json
sys.path.insert(0, "research"); sys.path.insert(0, "research/features/midi"); sys.path.insert(0, ".")
from bwlock import hold
import server
from bwmcp.music import midifile
OUT = os.path.abspath("research/features/midi/scratch"); os.makedirs(OUT, exist_ok=True)
def norm(ns): return sorted((n["pitch"], round(n["start"], 3), round(n["duration"], 3), n["velocity"]) for n in ns)
with hold("midi: scratch round trip"):
    try:
        s = server.get_session(); print("tempo", s.get("tempo"), [t["name"] for t in s["tracks"]])
        tr = server.get_transport(); print({k: tr[k] for k in tr if "tempo" in k or "sig" in k})
        server.create_track("instrument", name="ZZmidi A"); server.create_track("instrument", name="ZZmidi B")
        s = server.get_session(); idx = {t["name"]: t["index"] for t in s["tracks"]}; a, b = idx["ZZmidi A"], idx["ZZmidi B"]
        server.write_chords(a, 0, chords=["Am", "F", "C", "G"], key="A", scale="minor", rhythm="arp_up")
        server.write_bass(a, 1, chords=["Am", "F", "C", "G"], key="A", scale="minor", style="syncopated")
        for slot in (0, 1):
            orig = midifile.read_clip_settled(a, slot)
            p = os.path.join(OUT, f"export{slot}.mid")
            print("export", midifile.export_clip_midi(a, slot, p))
            r = midifile.import_midi(p, b, slot, 0, name=f"re{slot}")
            back = midifile.read_clip_settled(b, slot, expect=orig["count"])
            print(slot, "orig", orig["count"], orig["length_beats"], "back", back["count"], back["length_beats"], "equal", norm(orig["notes"]) == norm(back["notes"]))
            if norm(orig["notes"]) != norm(back["notes"]):
                print(norm(orig["notes"])[:5], norm(back["notes"])[:5])
        # Bitwig's own insert
        p = os.path.join(OUT, "export0.mid")
        try:
            print("insert_file_to_slot", server.bw.call("insert_file_to_slot", track_index=b, slot=3, path=p))
            time.sleep(2)
            print(server.get_track(b)["clips"])
            c = midifile.read_clip_settled(b, 3); print("native", c["count"], c["length_beats"]); print(norm(c["notes"])[:6], norm(server.get_clip_notes(a,0)["notes"])[:6]); orig0 = server.get_clip_notes(a, 0)["notes"]
            print("equal native", norm(c["notes"]) == norm(orig0))
        except Exception as e:
            print("native insert failed:", repr(e))
        print("tempo after", server.get_transport().get("tempo"))
    finally:
        s = server.get_session()
        for t in sorted(s["tracks"], key=lambda t: -t["index"]):
            if t["name"].startswith("ZZmidi"): server.delete_track(t["index"])
        s = server.get_session(); print([t["name"] for t in s["tracks"]], s.get("tempo"))
