"""Compressor+ in real units. Bitwig never sends display text for direct parameters, so the controller script reads it through a
device-specific parameter object (deep_display, Compressor+ only for now). Gain reduction is NOT exposed by the API."""
import re
import time

COMP_UUID = "42b32cd2-6275-4ff1-970f-4fac71d15ad9"
KEYS = {"attack_ms": "ATTACK", "release_ms": "RELEASE", "ratio": "RATIO", "threshold_db": "THRESHOLD", "makeup_db": "MAKEUP",
        "input_db": "INPUT", "knee_pct": "SMOOTH", "mix_pct": "MIX"}
SHOW = ["ATTACK", "RELEASE", "RATIO", "THRESHOLD", "SMOOTH", "MAKEUP", "INPUT", "MIX", "LINK_MODE", "GR_MODE"]


def num(text):
    """'1:2.50' -> 2.5, '-12.0 dB' -> -12.0, '4.74 ms' -> 4.74, '1.2 s' -> 1200 (ms)"""
    if re.search(r"-\s*inf", text or "", re.I):
        return -1e9
    if re.search(r"inf", text or "", re.I):
        return 1e9
    m = re.findall(r"-?\d+(?:\.\d+)?", text or "")
    if not m:
        return None
    v = float(m[-1])
    return v * 1000 if re.search(r"\d\s*s\b", text or "") and "ms" not in text else v


def read(bw, deep, track_index, device_index):
    deep.goto(track_index, device_index)
    time.sleep(0.6)
    bw.call("deep_display", uuid=COMP_UUID)
    time.sleep(0.4)
    r = bw.call("deep_display", uuid=COMP_UUID)
    return {k.split("/")[-1]: v["display"] for k, v in r.items() if k.split("/")[-1] in SHOW}


def set_units(bw, deep, track_index, device_index, **units):
    """Set Compressor+ values in real units by bisecting the normalized value until the displayed number matches."""
    deep.goto(track_index, device_index)
    time.sleep(0.6)
    out = {}
    for key, target in units.items():
        if key not in KEYS:
            raise ValueError(f"unknown {key}; use {list(KEYS)}")
        pid = KEYS[key]
        lo, hi, best = 0.0, 1.0, None
        # direction: compare displayed numbers at both ends
        def at(x):
            deep.set_values({"CONTENTS/" + pid: x})
            time.sleep(0.25)
            return num(bw.call("deep_display", uuid=COMP_UUID, ids=[pid])["CONTENTS/" + pid]["display"])
        a, b = at(0.0), at(1.0)
        if a is None or b is None:
            raise RuntimeError(f"cannot read {pid} display")
        up = b > a
        for _ in range(11):
            mid = (lo + hi) / 2
            v = at(mid)
            time.sleep(0.05)
            v = at(mid)   # second read: the first can still show the previous value
            best = (mid, v)
            if abs(v - target) < 1e-9 + abs(target) * 0.005:
                break
            if (v < target) == up:
                lo = mid
            else:
                hi = mid
        deep.set_values({"CONTENTS/" + pid: best[0]})
        time.sleep(0.3)
        out[key] = {"wanted": target, "got": num(bw.call("deep_display", uuid=COMP_UUID, ids=[pid])["CONTENTS/" + pid]["display"])}
    return out
