"""Offline test of the BW Remote VST receiver: signed packets, key lookup by key id, tampering, and reading the shared-memory audio ring."""
import hashlib
import hmac
import json
import struct
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bwmcp.analysis import vstfeed  # noqa: E402

tmp = Path(tempfile.mkdtemp())
vstfeed.data_dir = lambda: tmp           # keep the real %APPDATA% folder untouched


def packet(key, **extra):
    body = {"v": 1, "kid": vstfeed.kid_of(key), "seq": 1, "peak": [-6.0, -6.5], "playing": True}
    body.update(extra)
    text = json.dumps(body)
    sig = hmac.new(key.encode(), text.encode(), hashlib.sha256).hexdigest()
    return '{"sig":"' + sig + '","body":' + text + "}", text


def test_packets():
    key = "ab" * 32
    (vstfeed.keys_dir() / "vst_key_1.txt").write_text(key)
    f = vstfeed.Feed()
    assert f.handle(packet(key)[0]) and f.ok == 1 and f.latest["peak"] == [-6.0, -6.5]
    good, body = packet(key)
    assert not f.handle(good.replace("-6.0", "-9.0")) and f.bad == 1             # tampered body
    assert not f.handle(packet("cd" * 32)[0]) and f.unknown == 1                  # key we have never seen
    late = "ef" * 32                                                                # a plug-in instance that started after us
    (vstfeed.keys_dir() / "vst_key_2.txt").write_text(late)
    f._rescanned = 0
    assert f.handle(packet(late)[0]) and f.ok == 2
    assert not f.handle("garbage") and not f.handle('{"sig":"x","body":{') and f.bad >= 2
    print("ok test_packets")


def test_ring():
    sr, cap = 1000, 5000
    p = vstfeed._capture_file()
    header = b"BWRC" + struct.pack("<III", 1, 2, sr) + struct.pack("<QQ", cap, 7500) + b"\0" * (vstfeed.HEADER - 32)
    frames = np.zeros((cap, 2), dtype="<f4")
    for abs_frame in range(2500, 7500):                                              # ring holds the newest 5000 frames
        frames[abs_frame % cap] = (abs_frame / 10000.0, -abs_frame / 10000.0)
    p.write_bytes(header + frames.tobytes())
    x, rate = vstfeed.read_audio(1.0, wait=False)
    assert rate == sr and x.shape == (1000, 2)
    assert abs(x[-1, 0] - 7499 / 10000.0) < 1e-6 and abs(x[0, 1] + 6500 / 10000.0) < 1e-6
    y, _ = vstfeed.read_frames(6000, 500)
    assert y.shape == (500, 2) and abs(y[0, 0] - 0.6) < 1e-6
    assert vstfeed.read_frames(1000, 10)[0] is None                                  # already overwritten
    assert vstfeed.read_frames(7400, 500)[0] is None                                 # not written yet
    try:
        vstfeed.read_audio(10.0, wait=False)
        raise AssertionError("asking for more than the ring holds must fail")
    except ValueError:
        pass
    print("ok test_ring")


if __name__ == "__main__":
    test_packets()
    test_ring()
    print("ALL OK")
