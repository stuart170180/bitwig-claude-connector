"""Tracks, sends, scenes, launching, grouping, mix snapshots."""
import json
import os
import re
import time

from bwmcp.control import actionsdev
from bwmcp.core import paths
from bwmcp.core.bridge import SETTLE, bw, tool
from bwmcp.core.util import _hex_to_rgb, _set_volume_db
from bwmcp.tools.presets import load_preset


# --- Tracks & mixing ---
@tool()
def create_track(kind: str = "instrument", position: int = -1, name: str | None = None,
                 color: str | None = None, instrument: str | None = None) -> dict:
    """Create a track (kind: instrument, audio or effect; position -1 = end), optionally naming and
    colouring it. instrument: a preset/device name to load (e.g. 'Polysynth', 'Legend 808 Normal Kit',
    'Rhodes'; see search_presets). Returns the new track's info. Effect (FX) tracks appear as sends."""
    if kind not in ("instrument", "audio", "effect"):
        raise ValueError("kind must be instrument, audio or effect")
    before = bw.call("get_session")["tracks"]
    bw.call(f"create_{kind}_track", position=position)
    time.sleep(0.4)
    after = bw.call("get_session")["tracks"]
    if kind == "effect":
        return {"created": "effect track", "sends_now": bw.call("get_track", track_index=0)["sends"] if after else []}
    if len(after) <= len(before):
        raise RuntimeError("Bitwig did not create the track")
    idx = len(before) if position < 0 else position
    if instrument:
        load_preset(instrument, track_index=idx)
    if name or color:
        return set_track(idx, name=name, color=color)
    return bw.call("get_track", track_index=idx)


@tool()
def delete_track(track_index: int) -> str:
    """Delete a track."""
    return bw.call("delete_track", track_index=track_index)


@tool()
def set_track(track_index: int, name: str | None = None, volume: float | None = None,
              volume_db: float | None = None, pan: float | None = None, mute: bool | None = None,
              solo: bool | None = None, arm: bool | None = None, color: str | None = None) -> dict:
    """Change track properties; only given fields change. Returns the track state read back from Bitwig.
    volume_db sets the fader to an exact dB (e.g. -6); volume is the raw normalized 0..1 alternative.
    pan: -1 (left) .. 1 (right). color: hex like '#ff8800'."""
    cmds = []
    if name is not None:
        cmds.append(("set_track_name", {"name": name}))
    if volume is not None:
        cmds.append(("set_track_volume", {"value": volume}))
    if pan is not None:
        cmds.append(("set_track_pan", {"value": (pan + 1) / 2}))
    for key, val in (("mute", mute), ("solo", solo), ("arm", arm)):
        if val is not None:
            cmds.append((f"set_track_{key}", {"value": val}))
    if color is not None:
        r, g, b = _hex_to_rgb(color)
        cmds.append(("set_track_color", {"r": r, "g": g, "b": b}))
    if cmds:
        bw.batch([(c, {"track_index": track_index, **a}) for c, a in cmds])
    if volume_db is not None:
        _set_volume_db(track_index, volume_db)
    time.sleep(SETTLE)
    return bw.call("get_track", track_index=track_index)


@tool()
def set_send(track_index: int, send_index: int, value: float) -> dict:
    """Set a track's send level to an FX track, normalized 0..1."""
    bw.call("set_send", track_index=track_index, send_index=send_index, value=value)
    time.sleep(SETTLE)
    return {"sends": bw.call("get_track", track_index=track_index)["sends"]}


@tool()
def mix(tracks: list[dict]) -> list[dict]:
    """Set many tracks at once. Each item: {"track_index": int, plus any of name, volume, volume_db,
    pan, mute, solo, arm, color}. Returns each track's resulting state."""
    return [set_track(**t) for t in tracks]


@tool()
def select_track(track_index: int) -> str:
    """Select a track (device tools act on the selected track)."""
    return bw.call("select_track", track_index=track_index)


# --- Clip launcher ---
@tool()
def launch(track_index: int | None = None, slot: int | None = None, scene: int | None = None) -> str:
    """Launch a clip (track_index + slot) or a whole scene (scene)."""
    if scene is not None:
        return bw.call("launch_scene", scene=scene)
    return bw.call("launch_clip", track_index=track_index, slot=slot)


@tool()
def stop_clips(track_index: int | None = None) -> str:
    """Stop clips on one track, or all clips if track_index is omitted."""
    if track_index is None:
        return bw.call("stop_all_clips")
    return bw.call("stop_track_clips", track_index=track_index)


@tool()
def set_scene_name(scene: int, name: str) -> str:
    """Rename a scene."""
    return bw.call("set_scene_name", scene=scene, name=name)


# --- Mixer snapshots ---
SNAP_DIR = str(paths.DATA / "snapshots")


def _mixer_state():
    s = bw.call("get_session")
    return {"tempo": s["tempo"], "tracks": [
        {k: t[k] for k in ("index", "name", "volume", "volume_display", "pan", "mute", "solo", "sends")}
        for t in s["tracks"]]}


def _snap_path(name):
    safe = re.sub(r"[^\w\- ]", "_", name).strip()
    if not safe:
        raise ValueError("snapshot name required")
    return os.path.join(SNAP_DIR, safe + ".json")


@tool()
def snapshot(action: str, name: str | None = None, other: str | None = None,
             include_tempo: bool = False) -> dict:
    """Mixer snapshots (volume, pan, mute, solo, sends per track; matched by track name).
    action: save (name), recall (name; include_tempo to restore tempo), list, delete (name),
    diff (name vs current mix, or vs `other` snapshot). Use for A/B mix comparisons and as a safety net
    before big changes (save 'before', then recall it to undo everything)."""
    os.makedirs(SNAP_DIR, exist_ok=True)
    if action == "list":
        return {"snapshots": sorted(f[:-5] for f in os.listdir(SNAP_DIR) if f.endswith(".json"))}
    path = _snap_path(name or "")
    if action == "save":
        state = _mixer_state()
        state["saved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=1)
        return {"saved": name, "tracks": len(state["tracks"])}
    if not os.path.exists(path):
        raise ValueError(f"no snapshot named {name!r}")
    with open(path, encoding="utf-8") as f:
        snap = json.load(f)
    if action == "delete":
        os.remove(path)
        return {"deleted": name}
    live = {t["name"]: t for t in bw.call("get_session")["tracks"]}
    if action == "recall":
        cmds, missing = [], []
        for t in snap["tracks"]:
            cur = live.get(t["name"])
            if not cur:
                missing.append(t["name"])
                continue
            i = cur["index"]
            cmds += [("set_track_volume", {"track_index": i, "value": t["volume"]}),
                     ("set_track_pan", {"track_index": i, "value": t["pan"]}),
                     ("set_track_mute", {"track_index": i, "value": t["mute"]}),
                     ("set_track_solo", {"track_index": i, "value": t["solo"]})]
            cmds += [("set_send", {"track_index": i, "send_index": s["index"], "value": s["value"]})
                     for s in t["sends"]]
        if include_tempo:
            cmds.append(("set_tempo", {"bpm": snap["tempo"]}))
        bw.batch(cmds)
        return {"recalled": name, "tracks": len(snap["tracks"]) - len(missing), "missing_tracks": missing}
    if action == "diff":
        if other:
            with open(_snap_path(other), encoding="utf-8") as f:
                ref = {t["name"]: t for t in json.load(f)["tracks"]}
        else:
            ref = live
        diffs = []
        for t in snap["tracks"]:
            r = ref.get(t["name"])
            if not r:
                diffs.append({"track": t["name"], "change": "missing"})
                continue
            d = {k: [t[k], r[k]] for k in ("volume_display", "mute", "solo") if t[k] != r[k]}
            if abs(t["pan"] - r["pan"]) > 0.005:
                d["pan"] = [round(t["pan"] * 2 - 1, 2), round(r["pan"] * 2 - 1, 2)]
            sd = [(s["name"], s["value"], rs["value"]) for s, rs in zip(t["sends"], r["sends"])
                  if abs(s["value"] - rs["value"]) > 0.005]
            if sd:
                d["sends"] = sd
            if d:
                diffs.append({"track": t["name"], **d})
        return {"compare": f"{name} -> {other or 'current'}", "differences": diffs}
    raise ValueError("action must be save, recall, list, delete or diff")


@tool()
def group_tracks(track_indices: list[int], name: str | None = None) -> dict:
    """Group tracks (flat get_session indices, any combination) into a new group track and optionally name it. Collapsed
    groups between the first and last index aren't supported. Verified from the track bank."""
    return actionsdev.group_tracks(bw, track_indices, name)


@tool()
def ungroup_track(track_index: int) -> dict:
    """Dissolve a group track, keeping its children."""
    return actionsdev.ungroup(bw, track_index)


@tool()
def get_groups() -> list:
    """All group tracks with their direct children."""
    return actionsdev.groups(bw)


@tool()
def select_tracks(track_indices: list[int]) -> dict:
    """Select several tracks at once so a selection-based action can act on them (then run_bitwig_action)."""
    return actionsdev.select_tracks(bw, track_indices)


@tool()
def run_action_on_tracks(track_indices: list[int], action_id: str) -> dict:
    """Select the tracks, then run a track-level action on all of them (e.g. bounce_in_place). Effects of bounce,
    consolidate and normalize cannot be confirmed from the script: check the result in Bitwig."""
    return actionsdev.run_on_tracks(bw, track_indices, action_id)
