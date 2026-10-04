import glob, os, sys, time, wave
from pathlib import Path
import numpy as np
_R = Path(__file__).resolve()
while not (_R / "server.py").exists():
    _R = _R.parent
sys.path[:0] = [str(_R), str(_R / "research" / "grid")]
import server as s
from bwmcp.analysis import capture
from bwmcp.devices import gridedit as ge
import modproof as mp

D = mp.D
def make(name, cutoff=None, target=None, amount=0.5, rng=(-24.0, 24.0), base=0.0):
    f = ge.load(glob.glob(D + "4ccfc70e*/Default.bwpreset")[0])
    if cutoff is not None:
        ge.set_f64(ge.member(ge.device_obj(f), "CUTOFF").node(ge.F_REAL), cutoff)
    if target:
        tpl = ge.modulator_templates([D.rstrip("/")])
        uuid, (nm, cat, file, mid) = next((u, v) for u, v in tpl.items() if v[0] == "LFO")
        m = ge.add_modulator(f, ge.extract_modulator(ge.load(file), mid))
        ge.add_mapping(f, m.get(ge.F_NAME), target, amount, rng_min=rng[0], rng_max=rng[1], base=base)
    assert ge.check(f) == [], ge.check(f)
    p = mp.OUT / (name + ".bwpreset"); ge.save(f, p); return p

def measure(preset, label):
    n0 = len(s.bw.call("get_session")["tracks"])
    i = s.create_track("audio", name="ZZ modproof")["index"]
    wp = os.path.abspath(str(_R / "research" / "scratch" / "noise.wav"))
    s.load_sample(wp, track_index=i, slot=0, mode="clip"); time.sleep(2)
    s.bw.call("select_track", track_index=i); time.sleep(.5)
    s.bw.call("insert_file", path=str(preset)); time.sleep(3)
    s.launch(i, 0); time.sleep(1.0)
    x, sr, _ = capture.capture_recorder(8.0)
    s.stop_clips(); time.sleep(.8); s.transport("stop")
    m = x.mean(axis=1)[int(sr):]; w = int(0.1 * sr)
    rms = np.array([np.sqrt(np.mean(m[k:k+w] ** 2)) for k in range(0, len(m) - w, w)]); db = 20 * np.log10(rms + 1e-9)
    c = mp.centre_series(x, sr)
    print(label, "level %.1f dB (std %.2f dB)  centre %.0f Hz (std %.1f)" % (db.mean(), db.std(), c.mean(), c.std()), flush=True)
    s.delete_track(i); time.sleep(1.2); assert len(s.bw.call("get_session")["tracks"]) == n0

if __name__ == "__main__":
    measure(make("mp_base"), "plain filter, cutoff 60     ")
    measure(make("mp_cut100", cutoff=100.0), "plain filter, cutoff 100    ")
    measure(make("mp_gain_lfo", target="CONTENTS/POST_GAIN", amount=1.0, rng=(-24.0, 24.0), base=0.0), "LFO -> POST_GAIN amount 1.0 ")
