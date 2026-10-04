"""Offline tests: tempo maths for the device preset library and the colour helpers."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from bwmcp.devices import presetlib as p  # noqa: E402


def test_note_ms():
    assert abs(p.note_ms("1/4", 120) - 500.0) < 1e-9
    assert abs(p.note_ms("1/8.", 120) - 375.0) < 1e-9          # dotted eighth
    assert abs(p.note_ms("1/8t", 120) - 500 / 3) < 1e-6        # eighth triplet
    assert abs(p.note_ms("1/64", 120) - 31.25) < 1e-9          # pre-delay rule from the calculator table (120 bpm: 31.25 ms)
    assert abs(p.note_ms("1/1", 120) - 2000.0) < 1e-9


def test_resolve_tempo_following():
    r120 = p.resolve("Reverb", "small_room", 120)
    assert abs(r120["REVERB_TIME"] - 1000.0) < 0.01             # half note at 120 bpm
    r60 = p.resolve("Reverb", "small_room", 60)
    assert abs(r60["REVERB_TIME"] - 2000.0) < 0.01
    hall = p.resolve("Reverb", "hall", 120)
    assert abs(hall["REVERB_TIME"] - 4000.0) < 0.01             # two bars
    assert p.resolve("Reverb", "vocal_plate", 120, as_send=True)["MIX"] == 100
    assert p.resolve("Reverb", "vocal_plate", 120)["MIX"] < 100


def test_unknown_preset():
    try:
        p.resolve("Reverb", "nope", 120)
    except ValueError as e:
        assert "known" in str(e)
        return
    raise AssertionError("expected ValueError")


def test_colour_helpers():
    from bwmcp.tools import pitchcolour as c

    assert c._rgb01_to_hex(*c._hex_to_rgb01("#4dabf7")) == "#4dabf7"
    mid = c._lerp_hsv("#ff0000", "#0000ff", 0.5)                # hue goes the short way round
    assert mid != "#ff0000" and len(mid) == 7
    assert c._lerp_hsv("#336699", "#336699", 0.5) == "#336699"
    assert all(len(v) >= 3 for v in c.GENRE_PALETTES.values())


def test_values_inside_probed_ranges():
    """Every preset value must lie inside the range probed on the real devices (data/device_ranges.json)."""
    import json

    ranges = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "device_ranges.json"), encoding="utf-8"))
    keymap = {"ratio": "RATIO", "attack_ms": "ATTACK", "release_ms": "RELEASE", "threshold_db": "THRESHOLD", "makeup_db": "MAKEUP",
              "knee_pct": "SMOOTH", "mix_pct": "MIX"}
    bad = []
    for dev, presets in p.PRESETS.items():
        for name in presets:
            for key, v in p.resolve(dev, name, 110).items():
                rng = ranges.get(dev, {}).get(keymap.get(key, key.upper()))
                if not rng or rng[2] is None or rng[3] is None:
                    continue
                lo, hi = sorted((rng[2], rng[3]))
                if not lo - 1e-9 <= v <= hi + 1e-9:
                    bad.append((dev, name, key, v, (lo, hi)))
    assert not bad, bad


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("ALL OK")
