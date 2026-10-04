"""Offline tests with synthetic signals + a few sample-library loops (NOT real commercial references)."""
import os
import sys
import tempfile

import numpy as np
from scipy.io import wavfile

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, str(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
import reflib  # noqa: E402

reflib.LIB = reflib.Path(tempfile.gettempdir()) / "reflib_test.json"
if reflib.LIB.exists():
    reflib.LIB.unlink()
sr = 44100
rng = np.random.default_rng(0)


def pink(n, tilt_db_oct=-3.0):
    w = rng.standard_normal(n)
    f = np.fft.rfftfreq(n, 1 / sr)
    f[0] = 1
    hp = (f >= 20).astype(float)
    X = np.fft.rfft(w) * f ** (tilt_db_oct / 6.02) * hp
    x = np.fft.irfft(X, n)
    return x / np.abs(x).max() * 0.5


def stereo(x, side=0.0):
    s = rng.standard_normal(len(x)) * side * x.std()
    return np.stack([x + s, x - s], axis=1)


tmp = tempfile.gettempdir()
n = sr * 10
files = {}
for name, tilt, side in (("pink", -4.5, 0.1), ("dark", -6.0, 0.1), ("bright", -3.0, 0.1), ("wide", -4.5, 0.8)):
    p = os.path.join(tmp, f"rl_{name}.wav")
    wavfile.write(p, sr, stereo(pink(n, tilt), side).astype(np.float32))
    files[name] = p
for k, v in files.items():
    print(k, reflib.add_reference(v, k))
# the library stores the tilt: dark should have more low / less high than pink
lib = reflib._load_lib()["references"]
t = lambda k, c: lib[k]["third_octave_db"][reflib.CENTERS.index(c)]
assert t("dark", 63) > t("pink", 63) > t("bright", 63), "low band ordering"
assert t("dark", 10000) < t("pink", 10000) < t("bright", 10000), "high band ordering"
# pink-noise-like PSD of -4.5 dB/oct -> 1/3-octave band levels fall about 1.5 dB per octave
slope = (t("pink", 8000) - t("pink", 100)) / (np.log2(8000 / 100))
print("measured slope dB/oct:", round(slope, 2))
assert -1.9 < slope < -1.1  # PSD -4.5 dB/oct + 3 dB/oct (band width grows) = -1.5
# compare: 'bright' mix vs 'pink' reference -> positive presence/air diff, advice mentions air
c = reflib.compare_to_reference("pink", files["bright"])
print(c["group_diff_db"], c["advice"])
assert c["group_diff_db"]["air"] > 3 and c["group_diff_db"]["sub"] < -3 or c["group_diff_db"]["bass"] < -3
assert any("air" in a for a in c["advice"])
c = reflib.compare_to_reference("pink", files["pink"])
assert all(abs(v) < 1.0 for v in c["group_diff_db"].values()), c["group_diff_db"]
c = reflib.compare_to_reference("pink", files["wide"])
assert c["difference_mix_minus_reference"]["width_pct"] > 30 and any("Stereo width" in a for a in c["advice"])
# target curve = average
tc = reflib.target_curve(["dark", "bright"])
mid = np.array(tc["third_octave_db"][5:25], float)
assert abs(mid.mean() - np.mean([[lib["dark"]["third_octave_db"][i], lib["bright"]["third_octave_db"][i]] for i in range(5, 25)])) < 0.01
assert abs(sum(abs(x) for x in reflib.compare_to_reference(["dark", "bright"], files["pink"])["group_diff_db"].values())) < 6
# AIFF loader vs WAV loader on a real library AIFF
import samples  # noqa: E402
aif = [i["path"] for i in samples.index() if i["path"].lower().endswith(".aiff")][0]
x, s2 = reflib.load_audio(aif)
print("aiff ok", os.path.basename(aif), x.shape, s2, round(float(np.abs(x).max()), 3))
assert np.abs(x).max() > 0.01
# unsupported
for ext in (".mp3", ".flac"):
    try:
        reflib.load_audio("x" + ext)
        raise SystemExit("should fail")
    except ValueError as e:
        print("unsupported ->", e)
# real-ish audio: loops from the sample library (NOT commercial references)
loops = [i for i in samples.index() if i["kind"] == "loop" and i["path"].lower().endswith(".wav")
         and ("Irrupt" in i["name"] or "Hammond" in i["name"] or "Bass" in i["name"])][:4]
for i in loops:
    try:
        print(i["name"], reflib.add_reference(i["path"], "loop:" + i["name"], seconds=30, note="sample-library loop, not a commercial reference"))
    except Exception as e:
        print("skip", i["name"], e)
print(len(reflib.list_references()), "references")
print(reflib.compare_to_reference(["loop:" + loops[0]["name"]], files["pink"])["advice"])
print("ALL OK")
