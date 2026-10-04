"""Automation by performance: build plans of parameter moves and run them inside Bitwig (perform.js) while the
transport plays / the arranger records with automation write on, so real automation lanes get written.
Plan values are normalised 0..1 (what Bitwig's API uses). Beats: 4 beats = 1 bar in 4/4.

    from bwmcp.control.performdev import Perform, sweep, volume_ramp
    p = Perform(bw)
    plan = [volume_ramp(track=3, from_value=0.0, to_value=0.8, start_bar=0, bars=2, curve="ease")]
    p.record(plan, total_beats=16)          # arranger record + write, run, stop
"""
import math
import time

BEATS_PER_BAR = 4.0
CURVES = ("linear", "exp", "log", "ease", "ease_in", "ease_out", "hold")


def curve(name: str, t: float) -> float:
    """Shape function 0..1 -> 0..1. Must stay identical to pfCurve in perform.js."""
    if name not in CURVES:
        raise ValueError(f"curve must be one of {CURVES}")
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    if name in ("exp", "ease_in"):
        return (math.exp(4 * t) - 1) / (math.exp(4) - 1)
    if name in ("log", "ease_out"):
        return 1 - (math.exp(4 * (1 - t)) - 1) / (math.exp(4) - 1)
    if name == "ease":
        return t * t * (3 - 2 * t)
    if name == "hold":
        return 0.0
    return t


def value_at(move: dict, beat: float) -> float:
    """Value a move has at an absolute beat (before start: from; after end: to)."""
    if beat < move["start_beat"]:
        return move["from"]
    u = (beat - move["start_beat"]) / move["length_beats"] if move["length_beats"] > 0 else 1.0
    if u >= 1:
        return move["to"]
    return move["from"] + (move["to"] - move["from"]) * curve(move["curve"], u)


def _check01(name, v):
    if not isinstance(v, (int, float)) or not 0 <= v <= 1:
        raise ValueError(f"{name} must be 0..1 (normalised), got {v!r}")


def move(target: dict, from_value: float, to_value: float, start_beat: float, length_beats: float,
         curve_name: str = "linear") -> dict:
    _check01("from_value", from_value)
    _check01("to_value", to_value)
    if curve_name not in CURVES:
        raise ValueError(f"curve must be one of {CURVES}")
    if start_beat < 0 or length_beats <= 0:
        raise ValueError("start_beat must be >= 0 and length_beats > 0")
    return {"target": target, "from": float(from_value), "to": float(to_value), "start_beat": float(start_beat),
            "length_beats": float(length_beats), "curve": curve_name}


def _bars(start_bar, bars):
    return start_bar * BEATS_PER_BAR, bars * BEATS_PER_BAR


def volume_ramp(track, from_value, to_value, start_bar=0, bars=1, curve="linear"):
    s, l = _bars(start_bar, bars)
    return move({"kind": "volume", "track": track}, from_value, to_value, s, l, curve)


def pan_ramp(track, from_value, to_value, start_bar=0, bars=1, curve="linear"):
    s, l = _bars(start_bar, bars)
    return move({"kind": "pan", "track": track}, from_value, to_value, s, l, curve)


def send_ramp(track, send, from_value, to_value, start_bar=0, bars=1, curve="linear"):
    s, l = _bars(start_bar, bars)
    return move({"kind": "send", "track": track, "send": send}, from_value, to_value, s, l, curve)


def remote_ramp(index, from_value, to_value, start_bar=0, bars=1, curve="linear"):
    """Move remote control `index` (0-7, current page) of the device chosen with select={track, device}.
    This is the way to get automation on device parameters (direct parameters are NOT recordable)."""
    s, l = _bars(start_bar, bars)
    return move({"kind": "remote", "index": index}, from_value, to_value, s, l, curve)


def fade_out(track, start_bar, bars, from_value=None, curve="ease"):
    """Fade a track's volume to silence. from_value default 0.8 (about unity)."""
    return volume_ramp(track, 0.8 if from_value is None else from_value, 0.0, start_bar, bars, curve)


def fade_in(track, start_bar, bars, to_value=None, curve="ease"):
    return volume_ramp(track, 0.0, 0.8 if to_value is None else to_value, start_bar, bars, curve)


def sweep(track, device, param_name_or_id, from_value, to_value, bars, start_bar=0, curve="linear", bw=None,
          by="name"):
    """NOTE: direct parameters move but Bitwig does NOT record automation for them (verified); use remote_ramp for
    recordable device automation. Move one parameter of a device. With a `bw` bridge, `param_name_or_id` (a name fragment, e.g. 'Cutoff') is
    resolved to a direct-parameter id by selecting the device and searching its parameters. Without `bw`, pass the
    id (by='id'). Returns (move, select) where select = {track, device} for the plan."""
    s, l = _bars(start_bar, bars)
    pid = param_name_or_id
    if by == "name":
        if bw is None:
            raise ValueError("pass bw to resolve a parameter name, or by='id'")
        pid = resolve_param(bw, track, device, param_name_or_id)
    return move({"kind": "direct", "id": str(pid)}, from_value, to_value, s, l, curve), {"track": track, "device": device}


def resolve_param(bw, track, device, name):
    bw.call("select_track", track_index=track)
    time.sleep(0.7)
    bw.call("select_device", device_index=device)
    time.sleep(0.7)
    info = bw.call("deep_info", filter=name, limit=10)
    hits = info["params"]
    if not hits:
        raise ValueError(f"no parameter matching {name!r} on {info['device']}")
    exact = [h for h in hits if h["name"].lower() == name.lower()]
    return (exact or hits)[0]["id"]


class Perform:
    def __init__(self, bw):
        self.bw = bw

    def run(self, moves, select=None, play=True, from_beat=0.0, stop_at_end=True, mode="latch", touch=True,
            end_beat=None, remote_page=None):
        """Run moves against the playing transport (no arranger record). Automation write is switched on, so lanes
        are written to whatever the transport passes (the parameter write requires playing)."""
        end = end_beat if end_beat is not None else max(m["start_beat"] + m["length_beats"] for m in moves) + 0.5
        a = {"moves": moves, "play": play, "from_beat": from_beat, "stop_at_end": stop_at_end, "mode": mode,
             "touch": touch, "end_beat": end}
        if select:
            a["select"] = select
        if remote_page is not None:
            a["remote_page"] = remote_page
        return self.bw.call("perform_plan", **a)

    def record(self, moves, total_beats, scenes=None, select=None, mode="latch", touch=True):
        """Arranger record + automation write; `scenes` = arranger_start style plan [{scene, start}] (optional)."""
        a = {"moves": moves, "mode": mode, "touch": touch, "total_beats": total_beats}
        if scenes:
            a["scenes"] = scenes
        if select:
            a["select"] = select
        a["end_beat"] = total_beats
        return self.bw.call("perform_record", **a)

    def status(self):
        return self.bw.call("perform_status")

    def abort(self):
        return self.bw.call("perform_abort")

    def wait(self, timeout=120, poll=0.25):
        t0 = time.time()
        while time.time() - t0 < timeout:
            st = self.status()
            if not st["running"]:
                return st
            time.sleep(poll)
        raise TimeoutError("performance still running")

    def replay_samples(self, target, seconds, from_beat=0.0, step=0.05):
        """Verification: play with write OFF and read the target; returns [(position, value)]."""
        bw = self.bw
        bw.call("stop")
        bw.call("set_arranger_record", enabled=False)
        bw.call("set_automation", write=False)
        bw.call("perform_restore_control", target=target)
        bw.call("set_position", beats=from_beat)
        time.sleep(0.3)
        bw.call("play")
        out, t0 = [], time.time()
        while time.time() - t0 < seconds:
            out.append((bw.call("get_transport")["position"], bw.call("perform_read", target=target)))
            time.sleep(step)
        bw.call("stop")
        return out


def sampled_error(move_dict, samples, tolerance=0.05):
    """Compare replay samples with the planned curve: returns (max_abs_error, n_checked) over the move's span."""
    worst, n = 0.0, 0
    s, e = move_dict["start_beat"], move_dict["start_beat"] + move_dict["length_beats"]
    for pos, val in samples:
        if s + 0.25 <= pos <= e - 0.25:
            worst = max(worst, abs(val - value_at(move_dict, pos)))
            n += 1
    return worst, n
