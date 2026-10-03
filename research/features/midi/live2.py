import sys, os, time
sys.path.insert(0, "research"); sys.path.insert(0, "research/features/midi"); sys.path.insert(0, ".")
from bwlock import hold
import server, midifile
OUT = os.path.abspath("research/features/midi/scratch")
notes = [{"pitch": 60 + i % 5, "start": i * 0.5 + 0.013 * (i % 3), "duration": 0.37, "velocity": 50 + i, "channel": 1} for i in range(12)]
notes.append({"pitch": 72, "start": 3.3333, "duration": 0.3333, "velocity": 90})
p = os.path.join(OUT, "offgrid_140bpm.mid"); midifile.write_midi(p, [notes], tempo=140, time_signature=(3, 4))
drum = "C:/Users/stuar/AppData/Roaming/Cycling '74/Max 9/Examples/legacy-examples/recycler-folder/drumLoop.mid"
with hold("midi: native insert tests"):
    try:
        server.create_track("instrument", name="ZZmidi C")
        c = [t["index"] for t in server.get_session()["tracks"] if t["name"] == "ZZmidi C"][0]
        t0 = server.get_transport()
        for slot, path in ((0, p), (1, drum)):
            print(server.bw.call("insert_file_to_slot", track_index=c, slot=slot, path=path))
            clip = midifile.read_clip_settled(c, slot)
            print(slot, os.path.basename(path), clip["count"], clip["length_beats"], [(n["pitch"], n["start"], n["duration"], n["velocity"]) for n in clip["notes"][:14]])
        s = server.get_session(); t1 = server.get_transport()
        print("tempo/sig before", t0["tempo"], t0["time_signature"], "after", t1["tempo"], t1["time_signature"])
        print("clips", server.get_track(c)["clips"])
        r = midifile.import_midi(p, c, 2)
        clip = midifile.read_clip_settled(c, 2); print("via write_notes", r["length_beats"], [(n["pitch"], n["start"], n["duration"], n["velocity"]) for n in clip["notes"][:14]])
    except Exception as e:
        print("ERR", repr(e))
    finally:
        for t in server.get_session()["tracks"]:
            if t["name"] == "ZZmidi C": server.delete_track(t["index"])
        time.sleep(3); print([t["name"] for t in server.get_session()["tracks"]], server.get_transport()["tempo"])
