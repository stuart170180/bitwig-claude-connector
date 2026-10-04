"""Session, transport, tempo, groove, cue markers, project save and arrangement recording."""
import time

from bwmcp.control import arrclipsdev
from bwmcp.core.bridge import SETTLE, bw, tool


# --- Session / transport ---
@tool()
def get_session(with_clips: bool = False) -> dict:
    """Overview: tempo, transport, selected track, tracks (index, name, colour, mute/solo/arm,
    volume, pan, sends) and scenes. with_clips=True also lists filled clip-launcher slots."""
    return bw.call("get_session", with_clips=with_clips)


@tool()
def get_track(track_index: int) -> dict:
    """Detailed info for one track including sends and launcher clips."""
    return bw.call("get_track", track_index=track_index)


@tool()
def health_check() -> dict:
    """Check the Bitwig connection, script version and any API features missing in this Bitwig version. Also reports the
    connector (Python package) version."""
    import bwmcp

    return {**bw.call("capabilities"), "connector_version": bwmcp.__version__}


@tool()
def transport(action: str) -> str:
    """Control playback. action: play, stop, record, undo, redo."""
    if action not in ("play", "stop", "record", "undo", "redo"):
        raise ValueError("action must be play, stop, record, undo or redo")
    return bw.call(action)


@tool()
def set_tempo(bpm: float) -> dict:
    """Set project tempo in BPM (verified by reading back)."""
    bw.call("set_tempo", bpm=bpm)
    time.sleep(SETTLE)
    return {"tempo": bw.call("get_session")["tempo"]}


@tool()
def set_position(beats: float) -> str:
    """Move the play head to a position in beats (4 beats = 1 bar in 4/4)."""
    return bw.call("set_position", beats=beats)


@tool()
def set_metronome(enabled: bool) -> str:
    """Turn the metronome on or off."""
    return bw.call("set_metronome", enabled=enabled)


# --- Transport, groove & markers ---
@tool()
def get_transport() -> dict:
    """Full transport state: tempo, time signature, arranger loop, punch in/out, arranger record,
    automation write mode, launch quantization, groove settings and cue markers."""
    return bw.call("get_transport")


@tool()
def set_transport(loop_enabled: bool | None = None, loop_start: float | None = None,
                  loop_length: float | None = None, time_signature: str | None = None,
                  punch_in: bool | None = None, punch_out: bool | None = None,
                  launch_quantization: str | None = None, arranger_record: bool | None = None,
                  automation_write: bool | None = None, automation_mode: str | None = None) -> dict:
    """Change transport settings; only given fields change. Loop positions in beats.
    time_signature like '3/4' or '7/8'. launch_quantization: none, 8, 4, 2, 1, 1/2, 1/4, 1/8, 1/16.
    automation_mode: latch, touch, write. Returns the resulting transport state."""
    cmds = []
    if any(v is not None for v in (loop_enabled, loop_start, loop_length)):
        cmds.append(("set_loop", {"enabled": loop_enabled, "start": loop_start, "length": loop_length}))
    if time_signature:
        num, den = (int(x) for x in time_signature.split("/"))
        cmds.append(("set_time_signature", {"numerator": num, "denominator": den}))
    if punch_in is not None or punch_out is not None:
        cmds.append(("set_punch", {"punch_in": punch_in, "punch_out": punch_out}))
    if launch_quantization:
        cmds.append(("set_launch_quantization", {"value": launch_quantization}))
    if arranger_record is not None:
        cmds.append(("set_arranger_record", {"enabled": arranger_record}))
    if automation_write is not None or automation_mode:
        cmds.append(("set_automation", {"write": automation_write, "mode": automation_mode}))
    if cmds:
        bw.batch(cmds)
    time.sleep(SETTLE)
    t = bw.call("get_transport")
    t.pop("groove", None)
    return t


@tool()
def set_groove(enabled: bool | None = None, shuffle_amount: float | None = None,
               shuffle_rate: str | None = None, accent_amount: float | None = None) -> dict:
    """Bitwig's global groove. shuffle_amount and accent_amount 0..1 (0.5 shuffle = none, higher =
    swing). shuffle_rate '1/8' or '1/16'. Returns the groove state."""
    args = {}
    if enabled is not None:
        args["enabled"] = 1.0 if enabled else 0.0
    if shuffle_amount is not None:
        args["shuffle_amount"] = shuffle_amount
    if shuffle_rate is not None:
        args["shuffle_rate"] = 0.0 if shuffle_rate == "1/8" else 1.0
    if accent_amount is not None:
        args["accent_amount"] = accent_amount
    bw.call("set_groove", **args)
    time.sleep(SETTLE)
    return bw.call("get_transport")["groove"]


@tool()
def cue_markers(action: str = "list", index: int | None = None) -> dict | str:
    """Arranger cue markers. action: list, add (at play head), jump (to marker index)."""
    if action == "add":
        bw.call("add_cue_marker")
        time.sleep(SETTLE)
    elif action == "jump":
        return bw.call("launch_cue_marker", index=index)
    return {"cue_markers": bw.call("get_transport")["cue_markers"]}


@tool()
def save_project() -> str:
    """Save the current Bitwig project (same as Ctrl+S)."""
    return bw.call("save_project")


# --- Arrangement recording ---
@tool()
def record_arrangement(action: str = "start", scenes: list | None = None, bars: int = 4,
                       wait: bool | None = None) -> dict:
    """Turn launcher scenes into a real arrangement. Bitwig's API can't place arranger clips directly, so
    this records them: it starts arranger record and launches each scene on the bar, stopping tracks that
    have no clip in that scene (so a breakdown really drops the drums). Timing runs inside Bitwig.
    action: start, status, abort.
    scenes: scene numbers in song order, repeats allowed ([0, 1, 2, 3, 3, 4, 5, 6]), or dicts
    {"scene": 3, "bars": 8}; default = every scene that contains clips, in order. bars = bars per scene
    (sketch_song clips are 4 bars). The playhead restarts at 0 and the song plays out loud in real time;
    existing arranger content on the recorded tracks is overwritten. wait: block until finished (default:
    only when it takes under ~40 s; otherwise poll with action='status')."""
    if action == "status":
        return bw.call("arranger_status")
    if action == "abort":
        bw.call("arranger_abort")
        return bw.call("arranger_status")
    if action != "start":
        raise ValueError("action must be start, status or abort")
    session = bw.call("get_session", with_clips=True)
    filled = {c["slot"] for t in session["tracks"] for c in t.get("clips", [])}
    if scenes is None:
        scenes = sorted(filled)
    if not scenes:
        raise RuntimeError("no scenes contain clips - build something first (e.g. sketch_song)")
    items = [{"scene": x, "bars": bars} if isinstance(x, int) else {"scene": int(x["scene"]), "bars": int(x.get("bars", bars))}
             for x in scenes]
    empty = [i["scene"] for i in items if i["scene"] not in filled]
    if empty:
        raise ValueError(f"scenes {sorted(set(empty))} have no clips")
    names = {s["index"]: s["name"] for s in session["scenes"]}
    plan, beat = [], 0
    for i in items:
        plan.append({"scene": i["scene"], "start": beat})
        beat += i["bars"] * 4
    seconds = beat / session["tempo"] * 60
    bw.call("arranger_start", plan=plan, total_beats=beat)
    out = {"sections": [{"scene": i["scene"], "name": names.get(i["scene"]), "bars": i["bars"], "start_bar": p["start"] // 4 + 1}
                        for i, p in zip(items, plan)],
           "total_bars": beat // 4, "duration_s": round(seconds), "tempo": session["tempo"]}
    if wait is None:
        wait = seconds <= 40
    if not wait:
        return {**out, "state": "recording", "next": "poll record_arrangement(action='status') until phase is 'done'"}
    deadline = time.time() + seconds * 1.3 + 15
    while time.time() < deadline:
        time.sleep(0.5)
        st = bw.call("arranger_status")
        if not st["running"]:
            break
    else:
        bw.call("arranger_abort")
        raise RuntimeError("recording did not finish in time and was aborted")
    st = bw.call("arranger_status")
    if st["phase"] != "done":
        raise RuntimeError(f"recording ended early: {st['phase']} {st.get('error') or ''}")
    late = [x for x in st["launched"] if x["at_position"] > x["start_beat"] + 0.05]
    try:  # tracks keep playing their launcher clips until told to follow the arranger again
        bw.call("arrclip_op", op="return_to_arrangement")
    except RuntimeError:
        pass
    return {**out, "state": "done", "launches": len(st["launched"]) + 1, "late_launches": late,
            "note": "Recorded into the arranger and tracks returned to the arrangement. Open Bitwig's Arrange view to see the clips."}


@tool()
def return_to_arrangement() -> dict:
    """Make every track follow the arrangement again. After launching clips, a track keeps playing its launcher clip
    and ignores the arranger (recorded arranger content is silent) until this is called. record_arrangement now calls it."""
    return {"result": arrclipsdev.return_to_arrangement(bw)}
