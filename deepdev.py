"""Deep device access: walk into nested chains (Mid-Side Split's Mid/Side slots, layers), read and set every
parameter, build mid/side EQ. Talks to the controller script's deep_* commands (script v6.0+).

Bitwig only lets a script act on its selected ("cursor") device, so every call first selects its way to the device
(track -> top-level device -> slot/layer -> device within it) and waits for Bitwig to follow."""
import math
import time
from pathlib import Path

import presets

STEP = 0.7          # seconds for a selection change to reach the script
EQ_UUID_DEVICE = "EQ+"
EQ_TYPES = ["Off", "Low-cut 1P", "Low-cut 2P", "Low-cut 4P", "Low-cut 6P", "Low-cut 8P", "Low-shelf", "Bell",
            "High-cut 1P", "High-cut 2P", "High-cut 4P", "High-cut 6P", "High-cut 8P", "High-shelf", "Notch"]
TYPE_ALIASES = {"off": 0, "bell": 7, "peak": 7, "low-shelf": 6, "lowshelf": 6, "high-shelf": 13, "highshelf": 13,
                "notch": 14, "low-cut": 3, "lowcut": 3, "highpass": 3, "high-pass": 3, "hp": 3,
                "high-cut": 10, "highcut": 10, "lowpass": 10, "low-pass": 10, "lp": 10}
MID_SIDE = "Mid-Side Split"


def type_value(t) -> int:
    """Band type -> step 0..14. Accepts a number, an exact name from EQ_TYPES, or an alias like 'bell', 'low-cut'
    (low-cut / high-cut default to 4 poles; use 'Low-cut 2P' etc. for others)."""
    if isinstance(t, (int, float)):
        if not 0 <= int(t) <= 14:
            raise ValueError("band type number must be 0-14")
        return int(t)
    key = str(t).strip().lower()
    for i, n in enumerate(EQ_TYPES):
        if n.lower() == key:
            return i
    if key in TYPE_ALIASES:
        return TYPE_ALIASES[key]
    raise ValueError(f"unknown band type {t!r}; use one of: {', '.join(EQ_TYPES)} (or bell, low-cut, high-cut, ...)")


def freq_to_norm(hz: float) -> float:
    if not 20 <= hz <= 20000:
        raise ValueError("freq_hz must be 20-20000")
    return math.log10(hz / 20) / 3


def norm_to_freq(x: float) -> float:
    return 20 * 1000 ** x


def gain_to_norm(db: float) -> float:
    if not -30 <= db <= 30:
        raise ValueError("gain_db must be -30..30")
    return 0.5 + db / 60


def norm_to_gain(x: float) -> float:
    return (x - 0.5) * 60


# Q: 0.02 .. 1 .. 40, measured from the device (lower half is a slightly different curve than the upper half)
_Q_PTS = [(0.0, 0.02), (0.25, 0.16), (0.5, 1.0), (1.0, 40.0)]


def q_to_norm(q: float) -> float:
    if not 0.02 <= q <= 40:
        raise ValueError("q must be 0.02-40")
    if q >= 1:
        return 0.5 + 0.5 * math.log(q) / math.log(40)
    for (x0, q0), (x1, q1) in zip(_Q_PTS, _Q_PTS[1:]):
        if q0 <= q <= q1:
            return x0 + (x1 - x0) * math.log(q / q0) / math.log(q1 / q0)
    return 0.5


def norm_to_q(x: float) -> float:
    if x >= 0.5:
        return 40 ** (2 * x - 1)
    for (x0, q0), (x1, q1) in zip(_Q_PTS, _Q_PTS[1:]):
        if x0 <= x <= x1:
            return q0 * (q1 / q0) ** ((x - x0) / (x1 - x0))
    return 1.0


class Deep:
    def __init__(self, bw):
        self.bw = bw

    # ---- navigation -------------------------------------------------------------------------------------------
    def goto(self, track_index, device_index, slot=None, slot_index=0, layer=None):
        """Select a device. track_index -1 = master. slot/layer = nested chain to enter; slot_index = which device in it."""
        bw = self.bw
        if track_index == -1:
            bw.call("select_master")
        else:
            bw.call("select_track", track_index=track_index)
        time.sleep(STEP)
        bw.call("select_device", device_index=device_index)
        time.sleep(STEP)
        top = bw.call("deep_info", limit=0)
        if slot is not None or layer is not None:
            if slot is not None:
                if slot not in top["slots"]:
                    raise ValueError(f"{top['device']} has no slot {slot!r} (slots: {top['slots']})")
                bw.call("deep_nav", action="first_in_slot", slot=slot)
            else:
                bw.call("deep_nav", action="first_in_layer", layer=layer)
            time.sleep(STEP)
            info = bw.call("deep_info", limit=0)
            if not info["nested"]:
                raise ValueError(f"that chain inside {top['device']} is empty (insert a device first)")
            for _ in range(slot_index):
                bw.call("deep_nav", action="next")
                time.sleep(STEP)
            info = bw.call("deep_info", limit=0)
            if info["position"] != slot_index:
                raise ValueError(f"no device at position {slot_index} in that chain")
            return info
        return top

    def up(self):
        self.bw.call("deep_nav", action="parent")
        time.sleep(STEP)

    # ---- inspection -------------------------------------------------------------------------------------------
    def tree(self, track_index):
        """Top-level devices of a track (or master) with what's inside any nested chains."""
        bw = self.bw
        if track_index == -1:
            bw.call("select_master")
        else:
            bw.call("select_track", track_index=track_index)
        time.sleep(STEP)
        out = []
        for d in bw.call("list_devices")["devices"]:
            node = {"index": d["index"], "name": d["name"], "enabled": d["enabled"]}
            bw.call("select_device", device_index=d["index"])
            time.sleep(STEP)
            info = bw.call("deep_info", limit=0)
            chains = {}
            for slot in info["slots"]:
                chains[slot] = self._chain(lambda s=slot: bw.call("deep_nav", action="first_in_slot", slot=s))
                bw.call("select_device", device_index=d["index"])
                time.sleep(STEP)
            for lay in info["layers"]:
                chains[lay["name"] or f"layer {lay['index']}"] = self._chain(
                    lambda i=lay["index"]: bw.call("deep_nav", action="first_in_layer", layer=i))
                bw.call("select_device", device_index=d["index"])
                time.sleep(STEP)
            if chains:
                node["chains"] = chains
            out.append(node)
        return out

    def _chain(self, enter):
        bw = self.bw
        enter()
        time.sleep(STEP)
        info = bw.call("deep_info", limit=0)
        if not info["nested"]:
            return []
        devices = []
        while True:
            devices.append({"position": info["position"], "name": info["device"], "enabled": info["enabled"]})
            bw.call("deep_nav", action="next")
            time.sleep(STEP)
            nxt = bw.call("deep_info", limit=0)
            if nxt["position"] <= info["position"] or len(devices) > 30:
                break
            info = nxt
        return devices

    # ---- parameters -------------------------------------------------------------------------------------------
    def params(self, filt=None, limit=80, offset=0):
        return self.bw.call("deep_info", filter=filt, limit=limit, offset=offset)

    def set_values(self, values: dict):
        """values: {parameter id or exact/partial name: normalized 0..1}. Returns the read-back values."""
        bw = self.bw
        info = bw.call("deep_info", limit=500)
        byid = {p["id"]: p for p in info["params"]}
        byname = {}
        for p in info["params"]:
            byname.setdefault(p["name"].lower(), []).append(p["id"])
        done = {}
        for key, val in values.items():
            if key in byid:
                pid = key
            else:
                hits = byname.get(str(key).lower()) or [i for n, ids in byname.items() if str(key).lower() in n for i in ids]
                if len(hits) != 1:
                    raise ValueError(f"{key!r} matches {len(hits)} parameters on {info['device']}; use deep_params to see ids")
                pid = hits[0]
            bw.call("deep_set", id=pid, value=val)
            done[pid] = val
        time.sleep(0.4)
        after = {p["id"]: p["value"] for p in bw.call("deep_info", limit=500)["params"]}
        return {pid: {"set": v, "now": after.get(pid)} for pid, v in done.items()}

    def eq_band(self, band, type=None, freq_hz=None, gain_db=None, q=None, enabled=None):
        if not 1 <= band <= 8:
            raise ValueError("band must be 1-8")
        vals = {}
        if type is not None:
            vals[f"CONTENTS/TYPE{band}"] = type_value(type) / 14
        if freq_hz is not None:
            vals[f"CONTENTS/FREQ{band}"] = freq_to_norm(freq_hz)
        if gain_db is not None:
            vals[f"CONTENTS/GAIN{band}"] = gain_to_norm(gain_db)
        if q is not None:
            vals[f"CONTENTS/Q{band}"] = q_to_norm(q)
        if enabled is not None:
            vals[f"CONTENTS/ENABLE{band}"] = 1.0 if enabled else 0.0
        self.set_values(vals)
        return self.eq_state(band)

    def eq_state(self, band=None):
        """Band settings of the selected EQ+ in real units."""
        bw = self.bw
        info = bw.call("deep_info", limit=500)
        if info["device"] != "EQ+":
            raise ValueError(f"selected device is {info['device']!r}, not EQ+")
        v = {p["id"]: p["value"] for p in info["params"]}
        types = bw.call("deep_eq_types")
        bands = []
        for b in range(1, 9):
            if band and b != band:
                continue
            bands.append({
                "band": b, "type": types[b - 1]["display"], "on": bool(round(v.get(f"CONTENTS/ENABLE{b}", 1))),
                "freq_hz": round(norm_to_freq(v[f"CONTENTS/FREQ{b}"]), 1),
                "gain_db": round(norm_to_gain(v[f"CONTENTS/GAIN{b}"]), 2),
                "q": round(norm_to_q(v[f"CONTENTS/Q{b}"]), 2),
            })
        return bands

    # ---- editing ----------------------------------------------------------------------------------------------
    def insert(self, track_index, device, slot=None, where="end", device_index=None, by_uuid=False):
        """Insert a device by name/path. slot=None: top level (end of chain, or before device_index).
        slot given: into that slot of top-level device `device_index`."""
        bw = self.bw
        ref = self._uuid(device) if by_uuid else presets.resolve(device, None)
        if track_index == -1:
            bw.call("select_master")
        else:
            bw.call("select_track", track_index=track_index)
        time.sleep(STEP)
        if slot is None:
            if by_uuid:
                bw.call("deep_insert_uuid", uuid=ref, where="start" if where == "start" else "end")
                time.sleep(1.2)
                return
            args = {"path": ref}
            if where == "start":
                args["where"] = "start"
            elif device_index is not None and where == "before":
                args["before_device"] = device_index
            bw.call("insert_file", **args)
        else:
            if device_index is None:
                raise ValueError("device_index (the Mid-Side Split etc.) is required with slot")
            bw.call("select_device", device_index=device_index)
            time.sleep(STEP)
            bw.call("deep_nav", action="select_slot", slot=slot)
            time.sleep(STEP + 0.3)
            if by_uuid:
                bw.call("deep_insert_uuid", uuid=ref, where="slot_end")
            else:
                bw.call("deep_insert_file", where="slot_end", path=ref)
        time.sleep(1.2)

    @staticmethod
    def _uuid(name):
        import json
        ids = json.load(open(Path(__file__).resolve().parent / "bitwig_device_ids.json", encoding="utf-8"))
        hits = [u for u, n in ids.items() if n.lower() == name.lower()]
        if len(hits) != 1:
            raise ValueError(f"no single Bitwig device named {name!r} (use device_catalog)")
        return hits[0]

    def delete(self, track_index, device_index, slot=None, slot_index=0):
        if slot is None:
            self.goto(track_index, device_index)
        else:
            self.goto(track_index, device_index, slot=slot, slot_index=slot_index)
        self.bw.call("deep_delete")
        time.sleep(0.8)
