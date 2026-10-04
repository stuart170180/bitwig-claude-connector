"""Does an added modulator change the sound? Noise -> Filter, plain vs with an LFO modulator mapped to the cutoff; measure the spectral centre over time."""
import glob
import os
import sys
import time
import wave
from pathlib import Path

import numpy as np

_R = Path(__file__).resolve()
while not (_R / "server.py").exists():
    _R = _R.parent
sys.path[:0] = [str(_R)]
import server as s  # noqa: E402
from bwmcp.analysis import capture  # noqa: E402
from bwmcp.devices import gridedit as ge  # noqa: E402

D = "C:/Program Files/Bitwig Studio/Library/device-settings/"
OUT = _R / "data" / "patched_presets"
OUT.mkdir(parents=True, exist_ok=True)
sr = 44100


def _fix_snapshot(f):
    """Use the range-snapshot hints Bitwig itself writes for a pitch-type cutoff (copied from Polymer's remote-control page):
    domain 2, engine domain 2, 0xbc6 1, 0x7c4 0.5, unit 4."""
    def walk(o):
        if isinstance(o, ge.Obj):
            if o.get(0xe3d) == "CONTENTS/CUTOFF":
                snap = o.node(0x1334).v
                for fid, val in ((0x126, 2), (0x127, 2), (0xbc6, 1), (0x128, 4)):
                    snap.set(fid, val)
                ge.set_f64(snap.node(0x7c4), 0.5)
            for fl in o.fields:
                walk(fl.node.v)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(f.root)


def build(rate=None, amount=0.45):
    f = ge.load(glob.glob(D + "4ccfc70e*/Default.bwpreset")[0])
    if amount:
        tpl = ge.modulator_templates([D.rstrip("/")])
        uuid, (name, cat, file, mid) = next((u, v) for u, v in tpl.items() if v[0] == "LFO")
        t = ge.extract_modulator(ge.load(file), mid)
        m = ge.add_modulator(f, t)
        ge.add_mapping(f, m.get(ge.F_NAME), "CONTENTS/CUTOFF", amount, rng_min=15.0, rng_max=144.0, base=60.0)
        _fix_snapshot(f)
    assert ge.check(f) == [], ge.check(f)
    p = OUT / ("mod_proof_lfo.bwpreset" if amount else "mod_proof_plain.bwpreset")
    ge.save(f, p)
    return p


def centre_series(x, srr, win=0.1):
    m = x.mean(axis=1)[int(srr * 1.0):]
    n = int(win * srr)
    out = []
    f = np.fft.rfftfreq(n, 1 / srr)
    for i in range(0, len(m) - n, n):
        sp = np.abs(np.fft.rfft(m[i:i + n] * np.hanning(n))) ** 2
        out.append(float((f * sp).sum() / (sp.sum() + 1e-18)))
    return np.array(out)


def run():
    rng = np.random.default_rng(1)
    noise = (0.25 * rng.standard_normal(sr * 20)).clip(-1, 1)
    wp = os.path.abspath(str(_R / "research" / "scratch" / "noise.wav"))
    w = wave.open(wp, "wb")
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(sr)
    w.writeframes((noise * 32767).astype("<i2").tobytes())
    w.close()
    res = {}
    for label, preset in (("plain", build(amount=0)), ("lfo", build(amount=0.45))):
        n0 = len(s.bw.call("get_session")["tracks"])
        i = s.create_track("audio", name="ZZ modproof")["index"]
        s.load_sample(wp, track_index=i, slot=0, mode="clip")
        time.sleep(2)
        pos = os.path.getsize(os.path.expandvars(r"%LOCALAPPDATA%\Bitwig Studio\BitwigStudio.log"))
        s.bw.call("select_track", track_index=i)
        time.sleep(0.5)
        s.bw.call("insert_file", path=str(preset))
        time.sleep(3)
        s.launch(i, 0)
        time.sleep(1.0)
        x, srr, _ = capture.capture_recorder(10.0)
        s.stop_clips()
        time.sleep(0.8)
        s.transport("stop")
        c = centre_series(x, srr)
        spec = np.abs(np.fft.rfft(c - c.mean()))
        fr = np.fft.rfftfreq(len(c), 0.1)
        k = int(np.argmax(spec[1:])) + 1
        res[label] = {"centre_mean_hz": round(float(c.mean())), "centre_std_hz": round(float(c.std()), 1), "centre_min": round(float(c.min())), "centre_max": round(float(c.max())),
                      "dominant_modulation_hz": round(float(fr[k]), 2), "devices": len(s.bw.call("list_devices")["devices"])}
        print(label, res[label], flush=True)
        s.delete_track(i)
        time.sleep(1.2)
        assert len(s.bw.call("get_session")["tracks"]) == n0
    print("RATIO of centre variation (lfo / plain): %.1f" % (res["lfo"]["centre_std_hz"] / max(res["plain"]["centre_std_hz"], 1e-9)), flush=True)


if __name__ == "__main__":
    run()
