"""Offline unit tests: python test_masking.py"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import masking as M

SR = 44100
t = np.arange(SR * 3) / SR
rng = np.random.default_rng(1)


def tone(f, a=0.2):
    # narrow-band noise (about 1/2 octave wide) so it spans several 1/3-oct bands like a real instrument
    from scipy import signal
    sos = signal.butter(4, [f / 1.2, f * 1.2], "band", fs=SR, output="sos")
    n = signal.sosfilt(sos, np.random.default_rng(int(f)).normal(size=len(t)))
    return a * n / np.sqrt(np.mean(n ** 2)) * 0.7 + a * 0.3 * np.sin(2 * np.pi * f * t)


def test_clash_detected_and_priority():
    kick = tone(60) + tone(90, .15)
    bass = tone(70) + tone(85, .18)
    lead = tone(2000, .2) + tone(5000, .1)
    r = M.analyse({"Kick": (kick, SR), "Bass": (bass, SR), "Lead": (lead, SR)})
    assert r["clashes"], "should find kick/bass clash"
    c = r["clashes"][0]
    assert {c["a"], c["b"]} == {"Kick", "Bass"}, c
    assert 40 < c["centre_hz"] < 120
    assert c["fix"]["track"] == "Bass" and c["fix"]["band"]["gain_db"] <= -2   # kick outranks bass by name
    assert not any("Lead" in (x["a"], x["b"]) for x in r["clashes"])


def test_level_difference_reduces_score():
    s_equal = M.analyse({"A": (tone(100), SR), "B": (tone(100), SR)})["score"]
    s_diff = M.analyse({"A": (tone(100), SR), "B": (tone(100, 0.02), SR)})["score"]
    assert s_equal > s_diff
    assert s_diff == 0 or s_diff < s_equal / 2


def test_no_overlap_no_clash():
    r = M.analyse({"A": (tone(100), SR), "B": (tone(4000), SR)})
    assert r["clashes"] == [] and r["score"] == 0


def test_silence_and_short():
    r = M.analyse({"A": (np.zeros(SR), SR), "B": (tone(100), SR), "C": (tone(100)[:200], SR)})
    assert "A" in r["skipped"] and "C" in r["skipped"] and list(r["spectra"]) == ["B"]


def test_noise_overlap():
    n1 = rng.normal(0, .05, len(t)); n2 = rng.normal(0, .05, len(t))
    r = M.analyse({"Pad": (n1, SR), "Lead": (n2, SR)})
    assert r["clashes"] and r["clashes"][0]["fix"]["track"] == "Pad"   # lead outranks pad


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v(); print("ok", k)
