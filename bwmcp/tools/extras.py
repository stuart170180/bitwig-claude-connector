"""Extras found by the API exploration: master recorder, project state, undo/redo, UI layout, project notes, last-clicked parameter,
transport extras, a picture of Bitwig's window, and a read-only report on project files."""
import time

from mcp.server.mcpserver import Image

from bwmcp.analysis import capture
from bwmcp.control import actionsdev, screenshot
from bwmcp.core.bridge import bw, deep, tool
from bwmcp.devices import units as devunits
from bwmcp.library import projectfile


@tool()
def record_master(action: str = "capture", seconds: float = 10.0) -> dict:
    """Record Bitwig's own master output to a WAV, no Windows loopback and any audio driver. action: start, stop, status, or
    capture (record `seconds`, keep the file and return its path; play the song first). The analysis tools (analyze_master and
    the others with source='live') already use this recorder automatically. Files land in the project's master-recordings
    folder and can get big; delete the ones you do not need."""
    if action == "start":
        return {"result": bw.call("rec_start")}
    if action == "stop":
        return {"result": bw.call("rec_stop")}
    if action == "status":
        return bw.call("rec_status")
    if action == "capture":
        if seconds <= 0:
            raise ValueError("seconds must be > 0")
        t0 = time.time()
        bw.call("rec_start")
        try:
            time.sleep(seconds)
        finally:
            bw.call("rec_stop")
        path = None
        for _ in range(30):
            time.sleep(0.2)
            path = capture.find_recording(t0)
            if path:
                break
        if not path:
            raise RuntimeError("the recorder produced no file")
        return {"file": path, "seconds": seconds}
    raise ValueError("action must be start, stop, status or capture")


@tool()
def project_state() -> dict:
    """Quick state of the open project: name, whether undo / redo are available, whether the audio engine is active, and
    whether any track is soloed, muted or armed (handy before a mix audit: a forgotten solo ruins every measurement)."""
    return bw.call("proj_state")


@tool()
def undo_redo(action: str = "undo", steps: int = 1) -> dict:
    """Undo or redo in Bitwig (action: undo or redo), up to 20 steps. Returns the new undo/redo availability."""
    if action not in ("undo", "redo"):
        raise ValueError("action must be undo or redo")
    for _ in range(max(1, min(int(steps), 20))):
        bw.call("app_undo" if action == "undo" else "app_redo")
        time.sleep(0.25)
    st = bw.call("proj_state")
    return {"done": action, "steps": steps, "can_undo": st["can_undo"], "can_redo": st["can_redo"]}


@tool()
def ui_layout(arranger: dict | None = None, mixer: dict | None = None) -> dict:
    """Show or hide parts of Bitwig's arranger and mixer, or just read them (call with no arguments).
    arranger keys: cue_markers, follow (playback follow), double_row (tall track rows) can be changed; timeline, launcher, io,
    fx_tracks are read-only here. mixer keys (all changeable): launcher, crossfade, devices, io, meters, sends.
    Example: ui_layout(mixer={"meters": True, "io": False})."""
    result = {}
    if arranger or mixer:
        result["changed"] = bw.call("ui_set", arranger=arranger or {}, mixer=mixer or {})
        time.sleep(0.8)
    result["now"] = bw.call("ui_get")
    return result


@tool()
def project_notes(action: str = "get", notes: str | None = None, genre: str | None = None, mix_target: str | None = None) -> dict:
    """Claude's per-project notebook, stored inside the Bitwig project (it shows in Bitwig's controller settings, so you can
    read and edit it too). Fields: notes (500 characters), genre, mix_target (e.g. '-14 LUFS'). action: get or set.
    Use it to remember decisions per song, such as the genre for sidechain_setup or the loudness goal."""
    if action == "set":
        bw.call("note_set", notes=notes, genre=genre, mix_target=mix_target)
        time.sleep(1.0)            # Bitwig applies a settings change a moment after it is set
    elif action != "get":
        raise ValueError("action must be get or set")
    return bw.call("note_get")


@tool()
def last_clicked() -> dict:
    """The parameter you last touched in Bitwig (name, value, display text), e.g. after you move a knob and ask 'what is
    this one?'. Empty name = nothing touched yet in this session."""
    return bw.call("last_clicked")


@tool()
def transport_extras(punch_in: bool | None = None, punch_out: bool | None = None, pre_roll: str | None = None,
                     loop_start: float | None = None, loop_length: float | None = None) -> dict:
    """Read or set punch in/out, count-in pre-roll (none, one_bar, two_bars, four_bars) and the arranger loop range (beats).
    Call with no arguments to read. Returns the state after a short wait."""
    args = {k: v for k, v in dict(punch_in=punch_in, punch_out=punch_out, pre_roll=pre_roll, loop_start=loop_start,
                                  loop_length=loop_length).items() if v is not None}
    bw.call("transport_extras", **args)
    time.sleep(0.5)
    return bw.call("transport_extras")


@tool()
def look_at_bitwig(max_width: int = 1600) -> list:
    """A picture of Bitwig's window right now, for reading what the API cannot show: FX track names and faders, which sidechain
    source a compressor uses, gain-reduction and level meters, device displays. Read-only (nothing is clicked, focus does not
    change). Bitwig must not be minimized."""
    png, title, size = screenshot.capture(max_width)
    return [Image(data=png, format="png"), f"{title} ({size[0]}x{size[1]})"]


@tool()
def project_file_report(path: str | None = None) -> dict:
    """Read-only report on a Bitwig project FILE, without opening it: the Bitwig version that saved it, the stock devices it uses,
    audio files it references (and which are missing on disk), plug-ins, presets, and how much disk its folder uses (master
    recordings, bounces, auto-backups). path = a .bwproject file; default = the most recently changed project in your
    Documents\\Bitwig Studio\\Projects. It cannot read the track tree or parameter values."""
    return projectfile.report(path)


@tool()
def device_units(track_index: int, device_index: int, set: dict | None = None) -> dict:
    """Read a device's parameters in real units ('125 ms', '-12.0 dB', '3.08 kHz', ...) and optionally set them in those units.
    Works for Compressor+, Delay+, Reverb, Peak Limiter, Tool, De-Esser, Gate, Saturator (EQ+ has eq_set). set = {PARAM_ID:
    number}, ids as in the result, e.g. {"FEEDBACK": 40, "HICUT": 6000}: time in ms, frequency in Hz, otherwise the displayed
    unit (dB, %). Non-numeric choices (modes, on/off) can only be read here; use deep_set for them."""
    result = devunits.read(bw, deep, track_index, device_index)
    if set:
        result["changed"] = devunits.set_values(bw, deep, track_index, device_index, set)["set"]
        result["values"] = devunits.read(bw, deep, track_index, device_index)["values"]
    return result


EDIT_ACTIONS = {   # friendly name -> Bitwig action id (from list_bitwig_actions)
    "consolidate": "Consolidate", "split": "Split", "reverse": "reverse", "normalize": "normalize",
    "bounce_in_place": "bounce_in_place", "bounce_pre_fader": "bounce_in_place_pre_fader", "bounce_post_fader": "bounce_in_place_post_fader",
    "quantize": "quantize_again", "quantize_audio": "quantize_audio_again", "quantize_length": "fixed_length", "quantize_to_key": "quantize_to_key",
    "fade_in_to_here": "fade_in", "fade_out_from_here": "fade_out", "reset_fades": "reset_fades",
    "stretch_to_project_tempo": "stretch_to_project_tempo", "detect_tempo": "stretch_to_analyzed_tempo",
    "merge_duplicate_patterns": "merge_duplicate_patterns", "transpose_semitone_up": "transpose_semitone_up",
    "transpose_semitone_down": "transpose_semitone_down", "transpose_octave_up": "transpose_octave_up", "transpose_octave_down": "transpose_octave_down", "zoom_to_fit": "arranger_zoom_to_fit_selection_or_all",
    # from the user guide (v5.3): slicing at repeats (chapter 12), take selection (comping), global groove, unwrap
    "slice_in_place": "slice_in_place", "slice_at_repeats": "slice_at_repeats", "next_take": "select_next_take", "previous_take": "select_previous_take",
    "toggle_groove": "toggle_groove", "unwrap": "unwrap",
}


@tool()
def edit_action(action: str, track_indices: list[int] | None = None) -> dict:
    """Run a common editing command in Bitwig on the current selection (or on track_indices, which are selected first).
    action: consolidate, split, reverse, normalize, bounce_in_place, bounce_pre_fader, bounce_post_fader, quantize,
    quantize_audio, quantize_length, quantize_to_key, fade_in_to_here, fade_out_from_here, reset_fades, stretch_to_project_tempo,
    detect_tempo, merge_duplicate_patterns, zoom_to_fit, slice_in_place, slice_at_repeats, next_take, previous_take, toggle_groove, unwrap, transpose_semitone_up/down, transpose_octave_up/down (clips or notes selected in the Arrange view or editor). These act on what is selected in the Arrange view (clips need to be
    selected there); Bitwig does not report back whether anything changed, so check with get_session or look_at_bitwig."""
    if action not in EDIT_ACTIONS:
        raise ValueError(f"unknown action '{action}'; use one of {sorted(EDIT_ACTIONS)}")
    if track_indices:
        actionsdev.run_on_tracks(bw, track_indices, EDIT_ACTIONS[action])
    else:
        actionsdev.action_run(bw, EDIT_ACTIONS[action])
    return {"ran": action, "action_id": EDIT_ACTIONS[action], "note": "effect is not reported by Bitwig; verify visually or with get_session"}


@tool()
def engine_recover(wait_seconds: float = 60.0, normal_tracks: int = 2) -> dict:
    """Bring Bitwig's audio engine back after it crashed. While the engine is down the controller script cannot answer, so this
    presses Cancel on Bitwig's crash dialog (never Send Report), deletes the crashed track (only when the window clearly shows its 'Device
    missing' panel), clicks 'Activate Audio Engine' and waits for the script to return. normal_tracks = how many tracks the project had
    before the crash. Safe to call when everything is fine: it then does nothing."""
    from bwmcp.control import uiclick

    def state():
        try:
            return bool(bw.call("engine", action="state")["active"])
        except Exception:
            return None

    if state():
        return {"engine": "active", "clicked": False}
    clicked = False
    t0 = time.time()
    steps = uiclick.recover_after_crash(normal_tracks=normal_tracks)      # dialog -> delete the crashed track -> activate
    clicked = "engine" in steps
    while time.time() - t0 < wait_seconds:
        if state() is None or state() is False:
            clicked = uiclick.reactivate_engine() or clicked
        if state():
            return {"engine": "active", "clicked": clicked, "steps": steps, "seconds": round(time.time() - t0, 1)}
        time.sleep(2.5)
    return {"engine": "still down", "clicked": clicked, "hint": "Bitwig may be showing a dialog; look with look_at_bitwig"}
