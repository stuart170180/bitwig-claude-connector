"""Offline test of the simultaneous masking analysis (no Bitwig)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bwmcp.analysis import masklive  # noqa: E402


def spec(peak, level=-40.0):
    return [float(max(-90.0, level - 8 * abs(b - peak))) for b in range(24)]


def test_pairs_and_advice():
    r = masklive.analyse({"Kick": spec(5), "Bass": spec(6, -42), "Hat": spec(20, -45), "Pad": spec(12, -50)})
    top = r["pairs"][0]["tracks"]
    assert set(top) == {"Kick", "Bass"}, r["pairs"]                       # the two that share the low bands
    assert not any("Hat" in p["tracks"] for p in r["pairs"])               # nothing else sits near 6 kHz
    assert r["advice"] and "Kick" in r["advice"][0]
    assert all(isinstance(p["score"], float) for p in r["pairs"])          # JSON-safe
    print("ok test_pairs_and_advice")


def test_needs_two_and_silence():
    assert masklive.analyse({"A": spec(3)})["conflicts"] == []
    quiet = masklive.analyse({"A": [-95.0] * 24, "B": [-96.0] * 24})
    assert quiet["conflicts"] == []                                        # below the floor = silence, not masking
    print("ok test_needs_two_and_silence")


def test_band_labels():
    assert masklive.band_label(0).startswith("25-") and masklive.band_label(23).endswith("20.0k Hz")
    assert abs(masklive.EDGES[24] - 20000) < 1e-6 and len(masklive.CENTRES) == 24
    assert np.all(np.diff(masklive.EDGES) > 0)
    print("ok test_band_labels")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("ALL OK")
