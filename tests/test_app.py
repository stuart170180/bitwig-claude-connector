"""Offline checks for the native app's logic: tempo, key, stretch, waveform peaks, the app/MCP file link. No Bitwig, no window."""
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bwapp.audio import decode, process, tempo  # noqa: E402
from bwmcp.core import appbridge  # noqa: E402

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
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
    import tempfile
    tmp = Path(tempfile.mkdtemp())                                   # never touch the real link folder: the running app writes there
    appbridge.LINK, appbridge.LATEST, appbridge.CMD = tmp, tmp / "app_latest.json", tmp / "app_cmd.json"
    assert appbridge.read_latest() is None
    appbridge.write_latest({"momentary": -14.2})
    assert appbridge.read_latest()["momentary"] == -14.2
    time.sleep(0.05)
    assert appbridge.read_latest(max_age=0.01) is None            # stale frames mean "app not running"
    appbridge.send("target", name="club")
    c = appbridge.take()
    assert c["cmd"] == "target" and c["args"] == {"name": "club"} and appbridge.take() is None
    print("ok test_app_link")


def test_circle_links_chords():
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    import sounddevice as sd
    from bwapp.links import LINK
    from bwapp.panels.chords import Chords
    from bwapp.panels.circle import Circle
    app = QApplication.instance() or QApplication([])
    sd.play = lambda *a, **k: None                                  # silent
    c, ch = Circle(), Chords()
    c.resize(420, 520)
    c.show()
    cen, r = c.dims()

    def click(i, ring):
        a = math.radians(-90 + 30 * i)
        QTest.mouseClick(c, Qt.LeftButton, Qt.NoModifier, QPoint(int(cen.x() + r * ring * math.cos(a)), int(cen.y() + r * ring * math.sin(a))))
    click(1, 0.85)                                                   # G major
    assert c.sel == (1, False) and (ch.key.currentText(), ch.scale.currentText()) == ("G", "major")
    click(9, 0.55)                                                   # C minor (inner ring)
    assert c.sel == (9, True) and (ch.key.currentText(), ch.scale.currentText()) == ("C", "minor")
    assert "I Eb" in c.info.text()                                   # C minor shares its notes with Eb major
    LINK.progression.emit("I, V, vi, IV")
    assert ch.chords.text() == "I, V, vi, IV" and len(ch.last["voicings"]) == 4
    app.processEvents()
    print("ok test_circle_links_chords")


def test_lights():
    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from bwapp import status
    status.work.run = lambda fn, cb, *a, **k: None                    # no Bitwig needed

    class Fake(QObject):
        frame = Signal(dict)
        status = Signal(str, str)
    f = Fake()
    L = status.Lights(f)
    assert L.audio.colour == status.RED                                # nothing yet
    f.status.emit("capturing", "BW Remote VST3")
    L.refresh_audio()
    assert L.audio.colour == status.AMBER                              # source up, no data yet
    f.frame.emit({"momentary": -120.7})
    L.refresh_audio()
    assert L.audio.colour == status.AMBER                              # silent
    f.frame.emit({"momentary": -14.0})
    L.refresh_audio()
    assert L.audio.colour == status.GREEN
    L.last_frame -= 5
    L.refresh_audio()
    assert L.audio.colour == status.AMBER                              # stalled
    f.status.emit("cannot capture: x", "")
    L.refresh_audio()
    assert L.audio.colour == status.RED
    L._pinged({"ms": 3.2, "script": "6.2", "project": "T"}, None)
    assert L.bitwig.colour == status.GREEN and L.project.text() == "T"
    L._pinged(None, "No reply")
    assert L.bitwig.colour == status.RED
    app.processEvents()
    print("ok test_lights")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("ALL OK")
