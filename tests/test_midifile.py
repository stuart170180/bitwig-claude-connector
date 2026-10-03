import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import os, random, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
from midifile import read_midi, write_midi
random.seed(1)
notes = [{"pitch": random.randint(30, 100), "start": round(random.randint(0, 255) / 4, 4),
          "duration": random.choice([0.25, 0.5, 1, 1.5]), "velocity": random.randint(1, 127)} for _ in range(200)]
drums = [{"pitch": 36, "start": i * 0.5, "duration": 0.125, "velocity": 100, "channel": 10} for i in range(32)]
p = os.path.join(tempfile.gettempdir(), "rt_test.mid")
write_midi(p, [notes, drums], tempo=133.5, time_signature=(7, 8))
m = read_midi(p)
assert m["format"] == 1 and m["tempos"][0]["bpm"] == 133.5 and m["time_signatures"][0]["num"] == 7 and m["time_signatures"][0]["den"] == 8
got = m["tracks"][1]["notes"]
key = lambda n: (n["start"], n["pitch"], n["velocity"])
assert len(got) == 200
# same-pitch overlapping notes can pair differently; compare sorted multisets of (pitch,start,vel)
a = sorted((n["pitch"], round(n["start"], 3), n["velocity"]) for n in notes)
b = sorted((n["pitch"], round(n["start"], 3), n["velocity"]) for n in got)
assert a == b, "start/pitch/vel mismatch"
assert m["tracks"][2]["notes"][0]["drum"] and len(m["tracks"][2]["notes"]) == 32
print("roundtrip OK, synthetic")
# running status + vel-0 note-off: hand-built
import struct
trk = bytes([0,0x90,60,100, 96,60,0, 0,62,100, 96,0x80,62,0, 0,0xFF,0x2F,0])  # 2nd/3rd use running status
open(p,"wb").write(b"MThd"+struct.pack(">IHHH",6,0,1,96)+b"MTrk"+struct.pack(">I",len(trk))+trk)
m = read_midi(p); n = m["tracks"][0]["notes"]
assert [(x["pitch"], x["start"], x["duration"]) for x in n] == [(60,0,1.0),(62,1.0,1.0)], n
print("running status + vel0 OK")
for f in sys.argv[1:]:
    m = read_midi(f); print(os.path.basename(f), m["format"], m["ticks_per_beat"], m["tempos"][:2], m["time_signatures"][:1],
        [(t["name"], len(t["notes"]), sorted({x["channel"] for x in t["notes"]})) for t in m["tracks"]], round(m["length_beats"],2))
