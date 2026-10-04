"""One-off: move the four worker features (midi, reference, masking, actions, perform) into the connector and add their tools."""
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
F = REPO / "research" / "features"


def edit(path, pairs):
    s = Path(path).read_text(encoding="utf-8")
    nl = "\r\n" if "\r\n" in s else "\n"
    for a, b in pairs:
        a, b = a.replace("\n", nl), b.replace("\n", nl)
        assert a in s, (str(path), a[:70])
        s = s.replace(a, b, 1)
    Path(path).write_text(s, encoding="utf-8", newline="")


# ---- modules into the repo root (paths fixed for their new home)
for src, dst in [("midi/midifile.py", "midifile.py"), ("reference/reflib.py", "reflib.py"),
                 ("masking/masking.py", "masking.py"), ("actions/actionsdev.py", "actionsdev.py"),
                 ("perform/performdev.py", "performdev.py")]:
    shutil.copy(F / src, REPO / dst)

edit(REPO / "reflib.py", [
    ('ROOT = Path(__file__).resolve().parents[3]\nsys.path.insert(0, str(ROOT))\nimport mastering  # noqa: E402\n\nLIB = Path(__file__).resolve().parent / "library.json"',
     'import mastering  # noqa: E402\n\nLIB = Path(__file__).resolve().parent / "references.json"'),
    ("import struct\nimport sys\nimport time", "import struct\nimport time"),
])
edit(REPO / "masking.py", [
    ('HERE = os.path.dirname(os.path.abspath(__file__))\nROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))\nif ROOT not in sys.path:\n    sys.path.insert(0, ROOT)\n', ''),
    ("import os\nimport sys\nimport time", "import time"),
])
for name in ("midifile.py",):
    pass

TOOLS = '''
# --- MIDI files, reference library, masking finder, Bitwig actions, automation by performance ---
import actionsdev
import masking
import midifile
import performdev
import reflib


@tool()
def inspect_midi_file(path: str) -> dict:
    """Summarise a .mid file: tracks (name, note count, channels), tempo map, time signatures, length in beats."""
    m = midifile.read_midi(path)
    tracks = [{"index": i, "name": t.get("name"), "notes": len(t["notes"]),
               "channels": sorted({n["channel"] for n in t["notes"]})} for i, t in enumerate(m["tracks"])]
    return {"tracks": [t for t in tracks if t["notes"]], "tempos": m["tempos"], "time_signatures": m["time_signatures"],
            "ticks_per_beat": m.get("ticks_per_beat")}


@tool()
def import_midi_file(path: str, track_index: int, slot: int, midi_track: int | str = 0, name: str | None = None) -> dict:
    """Load a .mid file into a launcher clip. midi_track = which non-empty MIDI track (0, 1, ...), 'all' to merge them, or
    'ch10' style to take one channel (ch10 = General MIDI drums). Clip length rounds up to whole bars. The file's tempo
    is reported but not applied. Waits for Bitwig to finish writing and reports the notes it holds."""
    r = midifile.import_midi(path, track_index, slot, midi_track, name)
    clip = midifile.read_clip_settled(track_index, slot, expect=r.get("notes"))
    r["notes_in_bitwig"] = clip["count"]
    return r


@tool()
def export_clip_midi(track_index: int, slot: int, path: str) -> dict:
    """Write a launcher clip to a Standard MIDI File at the project tempo (waits for the clip to settle first)."""
    return midifile.export_clip_midi(track_index, slot, path)


@tool()
def add_reference(path: str, label: str, start: float = 0.0, seconds: float = 120.0, note: str = "") -> dict:
    """Analyse a reference track (WAV or AIFF; convert MP3/FLAC first) and store it in the reference library under a
    label: loudness, true peak, crest, loudness range, width, mid/side bands and a 1/3-octave tonal balance."""
    return reflib.add_reference(path, label, start, seconds, note)


@tool()
def list_references() -> list:
    """The stored reference tracks with their headline numbers."""
    return reflib.list_references()


@tool()
def remove_reference(label: str) -> dict:
    """Delete a stored reference."""
    return {"removed": reflib.remove_reference(label)}


@tool()
def reference_target(labels: list[str] | None = None) -> dict:
    """Averaged tonal balance and headline numbers of several references (default: all stored): a target to mix toward."""
    return reflib.target_curve(labels)


@tool()
def compare_to_library(label: str, source: str = "live", seconds: float = 20.0, start: float = 0.0) -> dict:
    """Compare a mix to a stored reference (or several: comma-separated labels, averaged). source = 'live' (what is
    playing, needs WASAPI capture) or a WAV/AIFF path. Returns loudness, crest, width and per-band tonal differences
    (mix minus reference) with plain advice. Use full songs as references: single loops give extreme differences."""
    return reflib.compare_to_reference(label, source, seconds, start)


@tool()
def masking_report(track_indices: list[int] | None = None, seconds: float = 5.0) -> dict:
    """Find frequency clashes between tracks: solos each track in turn while the song plays (audible!), captures it, and
    scores where two tracks both carry energy in the same band. Returns ranked findings and the EQ cut it would make.
    Playback must be running. Use a capture of at least one loop length. About 'seconds' + 0.4 s per track."""
    rep = masking.report(track_indices, seconds)
    rep.pop("_spectra", None)
    return {"summary": masking.format_report(rep), **{k: v for k, v in rep.items() if k != "spectra"}}


@tool()
def masking_fix(track_indices: list[int] | None = None, seconds: float = 5.0, max_fixes: int = 2,
                min_score: float = 0.5) -> dict:
    """Run masking_report, then apply the proposed EQ cuts for the worst clashes (inserting EQ+ where needed, one band
    each) and re-measure. Returns what was cut and the clash score before and after; the 'after' number can be noisy
    if the capture doesn't cover a full loop."""
    rep = masking.report(track_indices, seconds)
    res = masking.apply(rep, max_fixes, min_score)
    if res.get("after_report"):
        res["after_report"].pop("_spectra", None)
        res["after_report"].pop("spectra", None)
    return res


@tool()
def list_bitwig_actions(filter: str | None = None, limit: int = 50) -> dict:
    """Search Bitwig's ~780 built-in actions (category, id, name, 'blocked' if the safety deny-list refuses it)."""
    return actionsdev.action_list(bw, filter, limit)


@tool()
def run_bitwig_action(action_id: str) -> dict:
    """Run a Bitwig action by id on the current selection or focus. Dangerous ones (quit, close or switch project,
    delete everything, generic Delete) are refused. Results are not always visible to the script: check get_session."""
    return actionsdev.action_run(bw, action_id)


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


def _perform_move(m: dict) -> tuple[dict, dict | None]:
    p, kind = m["param"], m["param"]
    a, b = m["from"], m["to"]
    sb, bars, cv = m.get("start_bar", 0), m.get("bars", 1), m.get("curve", "linear")
    t = m.get("track_index")
    if kind == "volume":
        return performdev.volume_ramp(t, a, b, sb, bars, cv), None
    if kind == "pan":
        return performdev.pan_ramp(t, a, b, sb, bars, cv), None
    if kind == "send":
        return performdev.send_ramp(t, m.get("send", 0), a, b, sb, bars, cv), None
    if kind == "remote":
        if m.get("device_index") is None:
            raise ValueError("a remote move needs device_index")
        return performdev.remote_ramp(m.get("remote_index", 0), a, b, sb, bars, cv), {"track": t, "device": m["device_index"]}
    raise ValueError(f"param must be volume, pan, send or remote, not {p!r}")


@tool()
def perform_plan(moves: list[dict], total_bars: float | None = None, record: bool = True,
                 scenes: list[dict] | None = None) -> dict:
    """Write real automation by performing it: the script moves parameters in time while Bitwig records the arranger
    with automation write on, then the lanes replay on their own. Runs in REAL TIME and is audible. moves: [{"param":
    "volume"|"pan"|"send"|"remote", "track_index": n, "from": 0-1, "to": 0-1, "start_bar": 0, "bars": 2,
    "curve": linear|exp|log|ease|ease_in|ease_out|hold, "send": 0, "device_index": d, "remote_index": 0-7}]; values are
    Bitwig's normalized 0..1. Device automation goes through the 8 remote controls (page 0): direct parameters move
    but are not recordable. All remote moves in one plan must target the same device. Recording overwrites existing
    lane content. scenes: optional [{"scene": n, "start": beat}] launches during the take."""
    built = [_perform_move(m) for m in moves]
    selects = {(s["track"], s["device"]) for _, s in built if s}
    if len(selects) > 1:
        raise ValueError("remote moves in one plan must target the same track and device")
    select = {"track": next(iter(selects))[0], "device": next(iter(selects))[1]} if selects else None
    plan = [b for b, _ in built]
    end_beat = max(x["start_beat"] + x["length_beats"] for x in plan)
    total = (total_bars * 4) if total_bars else end_beat + 1
    perf = performdev.Perform(bw)
    if record:
        perf.record(plan, total, scenes=scenes, select=select)
    else:
        perf.run(plan, select=select)
    tempo = bw.call("get_session")["tempo"]
    st = perf.wait(timeout=total / tempo * 60 + 30)
    return {"recorded": record, "moves": len(plan), "beats": total, "status": st}


@tool()
def perform_ramp(track_index: int, param: str, from_value: float, to_value: float, start_bar: float = 0, bars: float = 2,
                 curve: str = "linear", send: int = 0, device_index: int | None = None, remote_index: int = 0,
                 record: bool = True) -> dict:
    """One automated move (see perform_plan): param = volume, pan, send (send index) or remote (device_index +
    remote_index 0-7). Example: a 4-bar filter rise on a synth = param 'remote', device_index 0, remote_index 0 (the first
    knob on the device's current page), from 0.2 to 0.9. Real time and audible; overwrites existing lane content."""
    return perform_plan([{"param": param, "track_index": track_index, "from": from_value, "to": to_value,
                          "start_bar": start_bar, "bars": bars, "curve": curve, "send": send,
                          "device_index": device_index, "remote_index": remote_index}], record=record)


@tool()
def perform_status() -> dict:
    """State of a running perform_plan / perform_ramp."""
    return performdev.Perform(bw).status()


@tool()
def perform_abort() -> dict:
    """Stop a running automation performance (turns record and write off)."""
    return performdev.Perform(bw).abort()

'''
edit(REPO / "server.py", [('if __name__ == "__main__":', TOOLS + 'if __name__ == "__main__":')])
edit(REPO / "make_docs.py", [('    ("Arrangement", ["record_arrangement"]),',
 '''    ("Arrangement", ["record_arrangement", "perform_plan", "perform_ramp", "perform_status", "perform_abort"]),
    ("MIDI files & references", ["inspect_midi_file", "import_midi_file", "export_clip_midi", "add_reference",
                                 "list_references", "remove_reference", "reference_target", "compare_to_library"]),
    ("Mix problem-solving", ["masking_report", "masking_fix"]),
    ("Bitwig actions & grouping", ["list_bitwig_actions", "run_bitwig_action", "group_tracks", "ungroup_track",
                                   "get_groups", "select_tracks", "run_action_on_tracks"]),''')])
s = (REPO / ".gitignore").read_text(encoding="utf-8")
(REPO / ".gitignore").write_text(s.rstrip("\n") + "\nreferences.json\nresearch/features/*/scratch/\nresearch/features/**/library.json\n", encoding="utf-8")
print("integrated")
