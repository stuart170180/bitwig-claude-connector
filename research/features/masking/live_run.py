import sys
from pathlib import Path

_R = Path(__file__).resolve()
while not (_R / "server.py").exists():
    _R = _R.parent
sys.path[:0] = [str(_R), str(_R / "research")]   # repo root (server, bwmcp) and research/ (bwlock, bwformat)
import sys, json, time
sys.path.insert(0, "../.."); sys.path.insert(0, "../../.."); sys.path.insert(0, ".")
from bwlock import hold
import server
from bwmcp.analysis import masking

_orig = server.bw.call
def _retry(cmd, **kw):
    for k in range(4):
        try: return _orig(cmd, **kw)
        except Exception as e:
            if k == 3: raise
            time.sleep(1.5)
server.bw.call = _retry

def build():
    names = [("ZZ Kick", "Sub-Bass"), ("ZZ Bass", "Classic Polysynth"), ("ZZ Pad", "Pad Lisa"),
             ("ZZ Lead", "Lead 1"), ("ZZ Empty", None)]
    idx = {}
    for n, inst in names:
        t = server.create_track("instrument", name=n)
        i = t["index"]; assert t["name"] == n, t
        if inst: server.load_preset(inst, track_index=i)
        server.set_track(i, name=n, volume_db=-18)
        idx[n] = i
    server.write_notes(idx["ZZ Kick"], 0, [{"pitch": 52, "start": b * 1.0, "duration": 0.4, "velocity": 120} for b in range(8)], length_beats=8)
    server.write_bass(idx["ZZ Bass"], 0, chords=["Am", "F"], key="A", style="root", octave=2, bars_per_chord=1)
    server.write_chords(idx["ZZ Pad"], 0, chords=["Am", "F"], key="A", scale="minor", octave=5)
    server.write_melody(idx["ZZ Lead"], 0, chords=["Am", "F"], key="A", scale="minor", octave=5, density=0.8, seed=3)
    return idx

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    with hold("masking: build+measure+fix"):
        idx = {}
        try:
            idx = build()
            for n in ("ZZ Kick", "ZZ Bass", "ZZ Pad", "ZZ Lead"):
                server.launch(idx[n], 0)
            server.transport("play"); time.sleep(1.5)
            tr = [idx[n] for n in idx]
            t0 = time.time()
            rep = masking.report(tr, 5)
            print("report time", round(time.time() - t0, 1))
            print(masking.format_report(rep)); print("timing", rep["timing_s"])
            for n, s in rep["spectra"].items():
                print(n, "peak band", masking.CENTRES[int(max(range(len(s)), key=lambda k: s[k]))], "Hz;", s)
            res = masking.apply(rep, max_fixes=2)
            print("APPLIED", json.dumps(res["applied"], indent=1)); print("before", res["before"], "after", res["after"])
            if res["after_report"]: print(masking.format_report(res["after_report"]))
        finally:
            try: server.transport("stop"); server.stop_clips()
            except Exception as e: print("stop err", e)
            s = server.bw.call("get_session")
            mine = ("ZZ Kick", "ZZ Bass", "ZZ Pad", "ZZ Lead", "ZZ Empty")
            for _ in range(8):
                ts = [t for t in server.bw.call("get_session")["tracks"] if t["name"] in mine]
                if not ts: break
                server.delete_track(ts[-1]["index"]); time.sleep(0.7)
            s = server.bw.call("get_session")
            print("FINAL", [(t["name"], t["mute"], t["solo"]) for t in s["tracks"]], s["playing"])
