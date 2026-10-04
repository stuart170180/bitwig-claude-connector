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


def _device(deep, track_index, device_index, nest=None):
    """(device name, uuid). nest = {"layer": n, "slot_index": k} or {"slot": name, "slot_index": k} reaches a device inside a layer / slot."""
    if nest:
        info = deep.goto(track_index, device_index, **nest)
        name = info["device"]
    else:
        tree = deep.tree(track_index)
        d = next((x for x in tree if x["index"] == device_index), None)
        if d is None:
            raise ValueError(f"no device {device_index} on track {track_index}")
        name = d["name"]
    return name, uuid_of(name)


def read(bw, deep, track_index, device_index, nest=None) -> dict:
    name, u = _device(deep, track_index, device_index, nest)
    if not u:
        raise ValueError(f"{name} is not in the device catalogue")
    deep.goto(track_index, device_index, **(nest or {}))
    time.sleep(0.6)
    try:
        bw.call("deep_display", uuid=u)
        time.sleep(0.4)
        r = bw.call("deep_display", uuid=u)
    except RuntimeError as e:
        raise RuntimeError(f"real units are not available for {name} yet ({e})") from None
    return {"device": name, "values": {k.split("/")[-1]: v["display"] for k, v in r.items() if v["display"] != ""}}


def _guess(lo, hi, vlo, vhi, target, step):
    """Next normalized value to try: interpolate between the bracket ends (log scale when the values span a wide positive range),
    pulled inside the bracket, with plain bisection every third step as a safety net."""
    import math

    if step % 3 == 2 or vlo == vhi:
        return (lo + hi) / 2
    if min(vlo, vhi, target) > 0 and max(vlo, vhi) / min(vlo, vhi) > 8:
        f = (math.log(target) - math.log(vlo)) / (math.log(vhi) - math.log(vlo))
    else:
        f = (target - vlo) / (vhi - vlo)
    f = min(0.95, max(0.05, f))
    return lo + (hi - lo) * f


def set_values(bw, deep, track_index, device_index, targets: dict, nest=None) -> dict:
    """Set parameters in displayed units by searching for the normalized value whose display matches (interpolation search, 4-7 reads each).
    nest reaches a device inside a layer or slot (see _device)."""
    name, u = _device(deep, track_index, device_index, nest)
    deep.goto(track_index, device_index, **(nest or {}))
    time.sleep(0.5)
    out = {}

    def at(pid, x):
        deep.set_values({"CONTENTS/" + pid: x})
        time.sleep(0.22)
        shown = bw.call("deep_display", uuid=u, ids=[pid])["CONTENTS/" + pid]["display"]
        return shown, number(shown)

    for pid, target in targets.items():
        pid = pid.upper()
        _, a = at(pid, 0.0)
        _, b = at(pid, 1.0)
        if a is None or b is None:
            out[pid] = {"error": "not a numeric parameter"}
            continue
        if (target < min(a, b) - 1e-9) or (target > max(a, b) + 1e-9):
            out[pid] = {"error": f"{target} is outside this parameter's range ({a} .. {b})"}
            continue
        lo, hi, vlo, vhi = 0.0, 1.0, a, b
        up = b > a
        best = (0.5, None)
        for step in range(14):
            x = _guess(lo, hi, vlo, vhi, target, step)
            at(pid, x)                                         # the first read after a change can still show the old value
            shown, v = at(pid, x)
            best = (x, shown)
            if v is None:
                break
            if abs(v - target) <= 1e-9 + abs(target) * 0.003:
                break
            if (v < target) == up:
                lo, vlo = x, v
            else:
                hi, vhi = x, v
        shown = at(pid, best[0])[0]
        out[pid] = {"wanted": target, "shown": shown}
    return {"device": name, "set": out}


def ranges(bw, deep, track_index, device_index) -> dict:
    """{PARAMETER: (display at 0, display at 1, number at 0, number at 1)} for every parameter that has display text."""
    name, u = _device(deep, track_index, device_index)
    deep.goto(track_index, device_index)
    time.sleep(0.5)
    real = {x["id"].split("/")[-1] for x in deep.params(None, 400, 0)["params"]}          # ignore guessed ids that are not real parameters
    pids = [k.split("/")[-1] for k in bw.call("deep_display", uuid=u) if k.split("/")[-1] in real]
    cur = {}
    for pid in pids:
        row = []
        for x in (0.0, 1.0):
            deep.set_values({"CONTENTS/" + pid: x})
            time.sleep(0.2)
            bw.call("deep_display", uuid=u, ids=[pid])
            shown = bw.call("deep_display", uuid=u, ids=[pid])["CONTENTS/" + pid]["display"]
            row.append(shown)
        if row[0] != "" or row[1] != "":
            cur[pid] = (row[0], row[1], number(row[0]), number(row[1]))
    return {"device": name, "ranges": cur}
