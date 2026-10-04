"""Recipes: save a track's whole device chain (devices + every parameter value) under a name, and rebuild it on any
track later. Stored as JSON in recipes/. Top-level Bitwig devices only (plugins can't be re-inserted by name).
Needs the deep device access (deepdev.py)."""
import json
import re
import time
from pathlib import Path

from bwmcp.core import paths
from bwmcp.devices import deepdev

DIR = paths.DATA / "recipes"
SKIP_IDS = ("SOLO", "SELECTED_BAND", "MAX_Y", "RANGE_Y", "DECIBEL_RANGE", "TILT")  # UI/view state, not sound


def _path(name: str) -> Path:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()).strip("_")
    if not slug:
        raise ValueError("recipe name must contain letters or numbers")
    return DIR / f"{slug}.json"


def list_all():
    DIR.mkdir(exist_ok=True)
    out = []
    for p in sorted(DIR.glob("*.json")):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
            out.append({"name": r["name"], "devices": [d["name"] for d in r["devices"]], "note": r.get("note", "")})
        except (OSError, ValueError, KeyError):
            continue
    return out


def delete(name):
    p = _path(name)
    if not p.exists():
        raise ValueError(f"no recipe named {name!r}")
    p.unlink()


def save(deep, track_index, name, note=""):
    """Capture the chain of a track (-1 = master)."""
    bw = deep.bw
    if track_index == -1:
        bw.call("select_master")
    else:
        bw.call("select_track", track_index=track_index)
    time.sleep(deepdev.STEP)
    devices, skipped = [], []
    for d in bw.call("list_devices")["devices"]:
        if d["plugin"]:
            skipped.append(f"{d['name']} (third-party plugin)")
            continue
        deep.goto(track_index, d["index"])
        info = deep.params(None, 500)
        vals = {p["id"]: p["value"] for p in info["params"]
                if not any(s in p["id"] for s in SKIP_IDS) and isinstance(p["value"], (int, float))}
        devices.append({"name": d["name"], "enabled": d["enabled"], "values": vals})
    if not devices:
        raise ValueError("nothing to save: no Bitwig devices on that track")
    DIR.mkdir(exist_ok=True)
    _path(name).write_text(json.dumps({"name": name, "note": note, "devices": devices}, indent=1), encoding="utf-8")
    return {"saved": name, "devices": [d["name"] for d in devices], "skipped": skipped}


def apply(deep, name, track_index, replace=False):
    """Rebuild a recipe on a track (appended after what's there; replace=True removes the track's devices first)."""
    p = _path(name)
    if not p.exists():
        raise ValueError(f"no recipe named {name!r} (use action 'list')")
    rec = json.loads(p.read_text(encoding="utf-8"))
    bw = deep.bw
    if replace:
        if track_index == -1:
            bw.call("select_master")
        else:
            bw.call("select_track", track_index=track_index)
        time.sleep(deepdev.STEP)
        for d in reversed(bw.call("list_devices")["devices"]):
            deep.delete(track_index, d["index"])
    start = len(bw.call("list_devices")["devices"]) if not replace else 0
    for i, dev in enumerate(rec["devices"]):
        deep.insert(track_index, dev["name"], None, "end", None)
        pos = start + i
        deep.goto(track_index, pos)
        got = bw.call("deep_info", limit=0)["device"]
        if got != dev["name"]:
            raise RuntimeError(f"expected {dev['name']} at position {pos} but found {got}")
        deep.set_values(dev["values"])
        if not dev.get("enabled", True):
            bw.call("set_device_enabled", enabled=False)
    return {"applied": name, "track_index": track_index, "devices": [d["name"] for d in rec["devices"]]}
