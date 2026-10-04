"""Real-unit read and set for stock devices whose display text the controller script can reach (Compressor+, EQ+ via its own tools,
Delay+, Reverb, Peak Limiter, Tool, De-Esser, Gate, Saturator; see DISP_DEVICES in deep.js). Values are shown as Bitwig shows them
('125 ms', '-12.0 dB', '3.08 kHz'); setting finds the normalized value whose displayed number matches by bisection.
Units for setting: time in ms, frequency in Hz, everything else as displayed (dB, %, ratio N for 1:N)."""
import json
import re
import time

from bwmcp.core import paths


def _ids():
    return json.load(open(paths.DATA / "bitwig_device_ids.json", encoding="utf-8"))


def uuid_of(device_name: str):
    return next((u for u, n in _ids().items() if n == device_name), None)


def number(text: str):
    """Displayed text -> a number in ms / Hz / the displayed unit; None for non-numeric (e.g. 'Fade', 'Off')."""
    t = text or ""
    if re.search(r"-\s*inf", t, re.I):
        return -1e9
    if re.search(r"inf", t, re.I):
        return 1e9
    m = re.findall(r"[-+]?\d+(?:\.\d+)?", t)
    if not m:
        return None
    v = float(m[-1])
    if re.search(r"khz", t, re.I):
        return v * 1000
    if re.search(r"\d\s*s\b", t) and "ms" not in t:
        return v * 1000
    return v


def _device(deep, track_index, device_index):
    tree = deep.tree(track_index)
    d = next((x for x in tree if x["index"] == device_index), None)
    if d is None:
        raise ValueError(f"no device {device_index} on track {track_index}")
    u = uuid_of(d["name"])
    return d["name"], u


def read(bw, deep, track_index, device_index) -> dict:
    name, u = _device(deep, track_index, device_index)
    if not u:
        raise ValueError(f"{name} is not in the device catalogue")
    deep.goto(track_index, device_index)
    time.sleep(0.6)
    try:
        bw.call("deep_display", uuid=u)
        time.sleep(0.4)
        r = bw.call("deep_display", uuid=u)
    except RuntimeError as e:
        raise RuntimeError(f"real units are not available for {name} yet ({e})") from None
    return {"device": name, "values": {k.split("/")[-1]: v["display"] for k, v in r.items() if v["display"] != ""}}


def set_values(bw, deep, track_index, device_index, targets: dict) -> dict:
    name, u = _device(deep, track_index, device_index)
    deep.goto(track_index, device_index)
    time.sleep(0.6)
    out = {}

    def at(pid, x):
        deep.set_values({"CONTENTS/" + pid: x})
        time.sleep(0.25)
        return bw.call("deep_display", uuid=u, ids=[pid])["CONTENTS/" + pid]["display"]

    for pid, target in targets.items():
        pid = pid.upper()
        a, b = number(at(pid, 0.0)), number(at(pid, 1.0))
        if a is None or b is None:
            out[pid] = {"error": "not a numeric parameter"}
            continue
        up, lo, hi, best = b > a, 0.0, 1.0, (0.5, None)
        for _ in range(12):
            mid = (lo + hi) / 2
            at(pid, mid)
            shown = at(pid, mid)
            v = number(shown)
            best = (mid, shown)
            if v is not None and abs(v - target) <= 1e-9 + abs(target) * 0.004:
                break
            if (v < target) == up:
                lo = mid
            else:
                hi = mid
        shown = at(pid, best[0])
        out[pid] = {"wanted": target, "shown": shown}
    return {"device": name, "set": out}
