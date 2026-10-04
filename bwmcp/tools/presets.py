"""Preset search and loading, plus automatic track naming when something is loaded."""
import os
import time

from bwmcp.core.bridge import SETTLE, bw, tool
from bwmcp.core.util import _hex_to_rgb, _read_clip
from bwmcp.devices import presets
from bwmcp.music import naming


# --- Presets & instruments ---
@tool()
def search_presets(query: str, kind: str | None = None, limit: int = 20) -> list[dict]:
    """Search the factory/user preset library and built-in devices by name or pack
    (e.g. 'pad', '808 kit', 'rhodes', 'EQ+', 'Analog Waves bass'). kind: 'preset' or 'device'."""
    return [{"name": p["name"], "type": p["type"], "pack": p["pack"]} for p in presets.search(query, kind, limit)]


@tool()
def load_preset(name: str, track_index: int | None = None, where: str = "end") -> dict:
    """Load a preset or built-in device (Polysynth, Drum Machine, EQ+, Compressor, Reverb...) onto a
    track by name or file path. where: 'end' (after existing devices) or 'start'. Verified by
    listing the track's devices afterwards."""
    path = presets.resolve(name)
    if track_index is not None:
        bw.call("select_track", track_index=track_index)
        time.sleep(SETTLE)
    before = len(bw.call("list_devices")["devices"])
    bw.call("insert_file", path=path, where=where)
    for _ in range(12):  # sample-based presets can take a moment
        time.sleep(0.25)
        devs = bw.call("list_devices")
        if len(devs["devices"]) > before:
            time.sleep(0.3)  # let the preset name arrive before naming the track
            idx = track_index if track_index is not None else bw.call("get_session")["selected_track"]["index"]
            renamed = _auto_name_one(idx, path)
            return {"loaded": os.path.basename(path), "track": renamed or devs["track"],
                    "devices": bw.call("list_devices")["devices"], "auto_named": bool(renamed)}
    raise RuntimeError(f"Bitwig did not load {path}")


@tool()
def refresh_preset_index() -> dict:
    """Rescan the disk for presets (after installing packages or saving new presets)."""
    return {"indexed": len(presets.index(refresh=True))}


# --- Auto naming ---
AUTO_NAME_ON_LOAD = True  # rename default-named tracks ("Inst 3", "Audio 2") when something is loaded


def _track_profile(t: dict, analyze_notes: bool):
    bw.call("select_track", track_index=t["index"])
    time.sleep(0.2)
    devices = bw.call("list_devices")["devices"]
    clips = bw.call("get_track", track_index=t["index"])["clips"]
    notes = None
    if analyze_notes and not any(d.get("preset") for d in devices) and clips and t["type"] != "Audio":
        notes, _ = _read_clip(t["index"], clips[0]["slot"])
    return devices, clips, notes


@tool()
def auto_name_tracks(track_indices: list[int] | None = None, style: str = "smart", only_default_names: bool = False,
                     color: bool = True, analyze_notes: bool = True, dry_run: bool = False) -> dict:
    """Rename tracks from what's on them: the loaded preset/instrument, sample or clip names, or (for bare
    MIDI tracks) the notes themselves (drums vs bass vs chords vs lead). style: smart ('Bass - Rippin'
    Bass'), role ('Bass'), source ('Rippin' Bass'). color=True also colours by role. only_default_names
    leaves tracks you've already named alone. dry_run shows the plan without renaming. Duplicate names get
    numbered. Restores your track selection afterwards."""
    session = bw.call("get_session")
    original = session["selected_track"]["index"]
    tracks = [t for t in session["tracks"] if track_indices is None or t["index"] in track_indices]
    plans = []
    for t in tracks:
        if only_default_names and not naming.is_default(t["name"]):
            plans.append({"index": t["index"], "old": t["name"], "new": None, "reason": "already named"})
            continue
        devices, clips, notes = _track_profile(t, analyze_notes)
        name, col, reason = naming.suggest(t, devices, clips, notes, style)
        plans.append({"index": t["index"], "old": t["name"], "new": name, "color": col, "reason": reason})
    for p, n in zip(plans, naming.dedupe([p["new"] for p in plans])):
        p["new"] = n
    if not dry_run:
        cmds = []
        for p in plans:
            if p["new"] and p["new"] != p["old"]:
                cmds.append(("set_track_name", {"track_index": p["index"], "name": p["new"]}))
            if color and p["new"] and p.get("color"):
                r, g, b = _hex_to_rgb(p["color"])
                cmds.append(("set_track_color", {"track_index": p["index"], "r": r, "g": g, "b": b}))
        if cmds:
            bw.batch(cmds)
            time.sleep(SETTLE)
    if original is not None and original >= 0:
        bw.call("select_track", track_index=original)
    return {"dry_run": dry_run, "renamed": sum(1 for p in plans if p["new"] and p["new"] != p["old"]),
            "tracks": plans}


def _auto_name_one(track_index: int, loaded_path: str | None = None):
    """Called after loading a sound: rename only if the track still has a default name. Bitwig itself
    renames a default track to the preset's name on load, so that counts as default too."""
    if not AUTO_NAME_ON_LOAD or track_index is None or track_index < 0:  # master/unknown: leave alone
        return None
    t = bw.call("get_track", track_index=track_index)
    stem = os.path.splitext(os.path.basename(loaded_path))[0] if loaded_path else None
    if not (naming.is_default(t["name"]) or (stem and t["name"] == stem)):
        return None
    r = auto_name_tracks([track_index], analyze_notes=False)
    return r["tracks"][0]["new"]
