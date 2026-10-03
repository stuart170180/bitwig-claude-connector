"""Arranger-clip access (arrangerclips.js). All functions take the `bw` bridge (server.bw).
Status: the arranger cursor clip exists and is readable/writable, but in live tests it could not be pointed at the
clip that record_arrangement recorded (see REPORT.md)."""
import time

SETTLE = 1.4


def select_arranger(bw, track_index):
    """Best-effort: select the track, focus the arranger timeline panel and Select All (the only known route)."""
    bw.call("select_track", track_index=track_index); time.sleep(.6)
    bw.call("action_run", id="focus_or_toggle_arranger"); time.sleep(.8)   # toggles: run once only
    bw.call("action_run", id="Select All"); time.sleep(.8)


def arrclip_info(bw):
    return bw.call("arrclip_info")


def arrclip_notes(bw, refresh=True, limit=120):
    """Notes of the arranger cursor clip (same 1/32 grid and refresh trick as launcher clips)."""
    if refresh:
        bw.call("arrclip_refresh"); time.sleep(SETTLE)
    out, off = bw.call("arrclip_notes", offset=0, limit=limit), 0
    notes = list(out["notes"])
    while len(notes) < out["total"]:
        off = len(notes)
        notes += bw.call("arrclip_notes", offset=off, limit=limit)["notes"]
    out["notes"] = notes
    return out


def arrclip_write(bw, notes, replace=True, length_beats=None):
    return bw.call("arrclip_write", notes=notes, replace=replace, length_beats=length_beats)


def arrclip_clear(bw):
    return bw.call("arrclip_clear")


def arrclip_set_name(bw, name):
    return bw.call("arrclip_set_name", name=name)


def arrclip_op(bw, op, **kw):
    """op: duplicate | duplicate_content | show_in_editor | quantize | transpose | launch | return_to_arrangement"""
    return bw.call("arrclip_op", op=op, **kw)


def return_to_arrangement(bw):
    """Tracks that had a launcher clip launched keep playing the launcher until this is called; recorded arranger
    content is silent otherwise."""
    return arrclip_op(bw, "return_to_arrangement")
