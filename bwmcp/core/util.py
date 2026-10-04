"""Small helpers shared by several tool modules (colours, dB parsing, writing notes, display-driven parameter setting)."""
import os
import re
import time

from bwmcp.analysis import mastering
from bwmcp.core.bridge import bw
from bwmcp.devices import presets
from bwmcp.library import bookmarks, samples
from bwmcp.music import expert, music, naming


def _hex_to_rgb(color: str):
    c = color.lstrip("#")
    if len(c) != 6:
        raise ValueError("color must be a hex string like #ff8800")
    return [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def _parse_db(display: str) -> float:
    if "inf" in display.lower():
        return -200.0
    m = re.search(r"-?\d+(\.\d+)?", display)
    return float(m.group()) if m else 0.0


def _set_volume_db(track_index: int, db: float):
    """Bitwig's fader curve isn't exposed, so binary-search the normalized value against the dB readout."""
    lo, hi = 0.0, 1.0
    for _ in range(14):
        mid = (lo + hi) / 2
        bw.call("set_track_volume", track_index=track_index, value=mid)
        time.sleep(0.06)
        cur = _parse_db(bw.call("get_track", track_index=track_index)["volume_display"])
        if abs(cur - db) < 0.1:
            return
        lo, hi = (mid, hi) if cur < db else (lo, mid)


WRITE_CHUNK = 300  # notes per message, keeps requests well under the UDP limit


def _write(track_index, slot, notes, length_beats, name=None):
    core = [{k: n[k] for k in ("pitch", "start", "duration", "velocity") if k in n} for n in notes]
    for i in range(0, max(1, len(core)), WRITE_CHUNK):
        bw.call("write_clip", track_index=track_index, slot=slot, notes=core[i:i + WRITE_CHUNK],
                length_beats=length_beats, name=name, replace=(i == 0))
        time.sleep(0.9)  # each write is scheduled inside Bitwig
    # setStep only carries velocity/duration; re-apply any per-note expressions on top.
    expressive = [{k: v for k, v in n.items() if k in expert.EXPR_KEYS or k in ("start", "pitch")}
                  for n in notes if expert.has_expression(n)]
    for i in range(0, len(expressive), 200):
        bw.call("set_note_props", notes=expressive[i:i + 200])
    clips = bw.call("get_track", track_index=track_index)["clips"]
    ok = any(c["slot"] == slot for c in clips)
    return {"track_index": track_index, "slot": slot, "notes": len(notes),
            "length_beats": length_beats, "verified": ok}


def _chords_arg(chords, progression):
    if chords:
        return chords
    if progression:
        if progression not in music.PROGRESSIONS:
            raise ValueError(f"unknown progression; options: {', '.join(music.PROGRESSIONS)}")
        return music.PROGRESSIONS[progression]
    raise ValueError("give chords (e.g. ['i','VI','III','VII'] or ['Am','F','C','G']) or a progression name")


# --- Clip editing ---
def _read_clip(track_index: int, slot: int):
    bw.call("focus_clip", track_index=track_index, slot=slot)
    time.sleep(0.6)
    notes, offset = [], 0
    while True:
        r = bw.call("get_notes", offset=offset, limit=120)
        notes += r["notes"]
        offset += len(r["notes"])
        if not r["notes"] or offset >= r["total"]:
            return notes, r["loop_length"]


# --- Bookmarks ---
def _resolve_sound(name: str, want: str | None = None) -> str:
    """Path, bookmark label, then sample/preset index."""
    if os.path.exists(name):
        return name
    try:
        return bookmarks.find(name)["path"]
    except ValueError:
        pass
    if want == "sample":
        return samples.resolve(name)
    return presets.resolve(name)


def _num(display: str):
    if display is None:
        return None
    d = display.replace("−", "-")
    if "inf" in d.lower():
        return -200.0 if "-" in d else 200.0
    if d.strip().lower() in ("off", "on"):
        return 1.0 if d.strip().lower() == "on" else 0.0
    m = re.search(r"-?\d+(\.\d+)?", d)
    if not m:
        return None
    v = float(m.group())
    if re.search(r"\d\s*k(hz)?\b", d.lower()):
        v *= 1000
    return v


# --- Analysis & arrangement helpers ---
def _is_drum_track(t: dict, devices: list) -> bool:
    return any(d["name"] == "Drum Machine" for d in devices) or \
        naming.classify(t["name"])[0] in ("Drums", "Kick", "Snare", "Clap", "Hats", "Perc")


def mastering_len(path: str) -> float:
    try:
        sr, data = mastering.wavfile.read(path, mmap=True)
        return len(data) / sr
    except Exception:
        return 0.0
