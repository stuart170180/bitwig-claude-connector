"""Offline checks for the native app's logic: tempo, key, stretch, waveform peaks, the app/MCP file link. No Bitwig, no window."""
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bwapp.audio import decode, process, tempo  # noqa: E402
from bwmcp.core import appbridge  # noqa: E402

SR = 44100


def loop(bpm, beats):
    x = np.zeros(int(SR * 60 / bpm * beats))
    beat = int(SR * 60 / bpm)
    for b in range(beats):
        i = int(b * SR * 60 / bpm)
        t = np.arange(4000) / SR
        x[i:i + 4000] += np.exp(-np.arange(4000) / 600) * np.sin(2 * np.pi * 60 * t)
        j = i + beat // 2
        x[j:j + 1500] += np.random.default_rng(b).standard_normal(1500) * np.exp(-np.arange(1500) / 200) * 0.3
    return x


def test_tempo_onsets():
    for bpm in (90, 100, 124, 140):
        est, _ = tempo.estimate_bpm(loop(bpm, 11), SR)
        assert abs(est - bpm) < 1.5, (bpm, est)
    print("ok test_tempo_onsets")


def test_tempo_whole_bars():
    r = tempo.analyse(loop(124, 8), SR)
    assert abs(r["bpm"] - 124) < 0.01 and r["bars"] == 2 and r["method"] == "whole bars", r
    print("ok test_tempo_whole_bars")


def test_one_shot_has_no_tempo():
    assert tempo.estimate_bpm(np.random.default_rng(1).standard_normal(int(SR * 0.4)) * 0.1, SR)[0] is None
    print("ok test_one_shot_has_no_tempo")


def test_key():
    t = np.arange(SR * 4) / SR
    x = sum(np.sin(2 * np.pi * f * t) for f in (174.6, 207.7, 261.6, 349.2))
    assert process.detect_key(x, SR)[0] == "F minor"
    print("ok test_key")


def test_stretch_length():
    d = np.zeros((SR * 2, 2), np.float32)
    d[:, 0] = np.sin(2 * np.pi * 220 * np.arange(SR * 2) / SR)
    y = process.stretch(d, SR, 1.25, 0)
    assert abs(len(y) / len(d) - 1 / 1.25) < 0.03
    assert process.stretch(d, SR, 1.0, 0) is d
    print("ok test_stretch_length")


def test_peaks():
    m = np.sin(np.linspace(0, 50, 10000)).astype(np.float32)
    p = decode.peaks(m, 100)
    assert p.shape == (100, 2) and p[:, 0].min() >= -1.001 and p[:, 1].max() <= 1.001 and (p[:, 1] >= p[:, 0]).all()
    print("ok test_peaks")


def test_app_link():
    for f in (appbridge.LATEST, appbridge.CMD):
        f.unlink(missing_ok=True)
    assert appbridge.read_latest() is None
    appbridge.write_latest({"momentary": -14.2})
    assert appbridge.read_latest()["momentary"] == -14.2
    time.sleep(0.05)
    assert appbridge.read_latest(max_age=0.01) is None            # stale frames mean "app not running"
    appbridge.send("target", name="club")
    c = appbridge.take()
    assert c["cmd"] == "target" and c["args"] == {"name": "club"} and appbridge.take() is None
    appbridge.LATEST.unlink(missing_ok=True)
    print("ok test_app_link")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("ALL OK")
