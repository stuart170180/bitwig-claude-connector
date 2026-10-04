"""Audio pitch controls (Pitch Shifter device, tuning correction) and colour controls (tracks and clips: roles, rainbow, gradient, mono, palettes)."""
import colorsys
import time

from bwmcp.analysis import capture
from bwmcp.core.bridge import bw, deep, tool
from bwmcp.devices import units as devunits
from bwmcp.music import naming, pitch
from bwmcp.tools.clips import clip_settings
from bwmcp.tools.session import transport
from bwmcp.tools.tracks import set_track

# ======================================================================================================================
# audio pitch
# ======================================================================================================================


def _find_device(track_index: int, name: str):
    return next((d["index"] for d in deep.tree(track_index) if d["name"] == name), None)


@tool()
def pitch_shift(track_index: int, semitones: float = 0.0, cents: float = 0.0, mix_pct: float | None = None,
                grain_rate_hz: float | None = None) -> dict:
    """Shift the pitch of a whole track with Bitwig's Pitch Shifter (added if the track has none): semitones plus fine cents
    (+-24 st range). mix_pct 100 = fully shifted, lower blends with the original (a quick harmony/thickener). grain_rate_hz sets the
    shifter's grain rate. IMPORTANT: the shifter only produces frequencies on a grid equal to its grain rate (measured: at 10 Hz a +1 st shift of a
    220 Hz tone landed on 220 or 250 Hz, at 1 Hz it was within 1 Hz). Use 1 to 2 Hz for fine (cents) or exact shifts, 10 Hz or more for big shifts
    on drums and transients. Works on audio and instrument tracks. Returns what Bitwig shows."""
    idx = _find_device(track_index, "Pitch Shifter")
    if idx is None:
        deep.insert(track_index, "Pitch Shifter", None, "end", None, True)
        time.sleep(1.0)
        idx = _find_device(track_index, "Pitch Shifter")
    targets = {"PITCH": semitones + cents / 100.0}
    if mix_pct is not None:
        targets["MIX"] = mix_pct
    if grain_rate_hz is not None:
        targets["GRAIN_RATE"] = grain_rate_hz
    res = devunits.set_values(bw, deep, track_index, idx, targets)
    return {"track_index": track_index, "device_index": idx, "set": res["set"], "now": devunits.read(bw, deep, track_index, idx)["values"]}


@tool()
def fix_tuning(track_index: int, seconds: float = 8.0, threshold_cents: float = 8.0, apply: bool = True) -> dict:
    """Measure how far a track's tuning is from A=440 and correct it. The track is soloed, Bitwig plays for `seconds` (it starts the
    transport if it is stopped) while the master recorder captures it, the tuning offset in cents is measured on the audio, and when it is
    off by more than threshold_cents a Pitch Shifter (grain rate 1 Hz, the only setting that keeps cents-level accuracy) is set to the opposite
    fine-tune. Accuracy is about 1 Hz, so a low note can remain several cents off. apply=False only measures.
    Needs pitched material (a sample, vocal, chords or a synth), and playback from a clip or the arrangement."""
    sess = bw.call("get_session")
    was_playing = bool(sess["playing"])
    solo_state = next(t["solo"] for t in sess["tracks"] if t["index"] == track_index)
    set_track(track_index, solo=True)
    try:
        if not was_playing:
            transport("play")
            time.sleep(0.6)
        x, sr, _src = capture.capture_live(seconds)
    finally:
        if not was_playing:
            transport("stop")
        set_track(track_index, solo=bool(solo_state))
    pt = pitch.poly_tuning(x, sr)
    if not pt:
        raise RuntimeError("no pitched content found (is the track playing during the capture?)")
    off = pt["offset_cents"]
    out = {"offset_cents": off, "confidence": pt["confidence"], "a4_hz": pt["a4_hz"], "threshold_cents": threshold_cents}
    if pt["confidence"] < 0.35:
        out["note"] = "low confidence: little tonal content or deliberately detuned material; not applied"
        return out
    if abs(off) > threshold_cents and apply:
        existing = _find_device(track_index, "Pitch Shifter")          # the measurement already includes any shift we made earlier
        current = 0.0
        if existing is not None:
            current = devunits.number(devunits.read(bw, deep, track_index, existing)["values"].get("PITCH", "0")) or 0.0
        out["applied"] = pitch_shift(track_index, current - off / 100.0, 0.0, mix_pct=100, grain_rate_hz=1.0)["now"]
    else:
        out["applied"] = None if abs(off) > threshold_cents else "in tune, nothing to do"
    return out


# ======================================================================================================================
# colours
# ======================================================================================================================
GENRE_PALETTES = {
    "trance": ["#7c4dff", "#00e5ff", "#ff4081", "#18ffff", "#b388ff"],
    "house": ["#ff9800", "#ffc107", "#ff5722", "#8d6e63", "#ffab40"],
    "techno": ["#e53935", "#9e9e9e", "#616161", "#ff1744", "#bdbdbd"],
    "dnb": ["#00e676", "#1de9b6", "#2979ff", "#76ff03", "#00b0ff"],
    "lofi": ["#d7ccc8", "#a5d6a7", "#ffcc80", "#b0bec5", "#f48fb1"],
    "ambient": ["#4db6ac", "#9fa8da", "#80deea", "#b39ddb", "#a5d6a7"],
    "hiphop": ["#ffd54f", "#8d6e63", "#455a64", "#ff7043", "#9575cd"],
    "pop": ["#ff4081", "#40c4ff", "#ffeb3b", "#69f0ae", "#ff6e40"],
    "jazz": ["#795548", "#ffb300", "#5d4037", "#00897b", "#8d6e63"],
    "sunset": ["#ff6f61", "#ffa07a", "#ffd166", "#ef476f", "#9d4edd"],
    "ocean": ["#023e8a", "#0077b6", "#00b4d8", "#48cae4", "#90e0ef"],
    "forest": ["#2d6a4f", "#40916c", "#52b788", "#74c69d", "#95d5b2"],
}
WARM_ROLES = {"Drums", "Kick", "Snare", "Hats", "Percussion", "808", "Bass", "Brass", "FX"}


def _hex_to_rgb01(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _rgb01_to_hex(r, g, b):
    return "#%02x%02x%02x" % tuple(round(max(0, min(1, v)) * 255) for v in (r, g, b))


def _lerp_hsv(a: str, b: str, t: float) -> str:
    ha, sa, va = colorsys.rgb_to_hsv(*_hex_to_rgb01(a))
    hb, sb, vb = colorsys.rgb_to_hsv(*_hex_to_rgb01(b))
    dh = ((hb - ha + 0.5) % 1) - 0.5                               # shortest way round the hue wheel
    return _rgb01_to_hex(*colorsys.hsv_to_rgb((ha + dh * t) % 1, sa + (sb - sa) * t, va + (vb - va) * t))


def schemes():
    return {"roles": "colour by detected role (drums, bass, pad, lead, vocal, keys, FX ...)",
            "rainbow": "evenly spaced hues across the tracks", "gradient": "smooth blend from `base` to `end`",
            "mono": "shades of `base`, dark to light", "warm_cool": "warm colours for rhythm and bass, cool for harmony and melody",
            "palette": f"cycle a named palette ({', '.join(GENRE_PALETTES)})"}


@tool()
def colour_schemes() -> dict:
    """The colouring schemes color_tracks understands and the named palettes (genres and moods)."""
    return {"schemes": schemes(), "palettes": GENRE_PALETTES}


def _track_text(t, devices):
    names = [t["name"]] + [d["name"] for d in devices]
    return " ".join(names)


@tool()
def color_tracks(scheme: str = "roles", track_indices: list[int] | None = None, base: str = "#4dabf7", end: str = "#f783ac",
                 palette: str = "trance") -> dict:
    """Colour tracks in one go. scheme: roles (by what each track is), rainbow, gradient (base -> end), mono (shades of base),
    warm_cool (warm = drums/bass/FX, cool = pads/keys/leads), palette (cycle a named palette, see colour_schemes).
    track_indices default = every track (effect tracks and master are not reachable from the API). Returns the colour given to each."""
    if scheme not in schemes():
        raise ValueError(f"scheme must be one of {list(schemes())}")
    if scheme == "palette" and palette not in GENRE_PALETTES:
        raise ValueError(f"palette must be one of {list(GENRE_PALETTES)}")
    tracks = [t for t in bw.call("get_session")["tracks"] if track_indices is None or t["index"] in track_indices]
    n = max(1, len(tracks))
    out = {}
    for k, t in enumerate(tracks):
        if scheme == "roles":
            try:
                devs = deep.tree(t["index"])
            except Exception:
                devs = []
            role, colour = naming.classify(_track_text(t, devs))
            colour = colour or "#868e96"
        elif scheme == "rainbow":
            colour = _rgb01_to_hex(*colorsys.hsv_to_rgb(k / n, 0.65, 0.95))
        elif scheme == "gradient":
            colour = _lerp_hsv(base, end, k / max(1, n - 1))
        elif scheme == "mono":
            h, s, v = colorsys.rgb_to_hsv(*_hex_to_rgb01(base))
            colour = _rgb01_to_hex(*colorsys.hsv_to_rgb(h, s, 0.45 + 0.5 * k / max(1, n - 1)))
        elif scheme == "warm_cool":
            devs = deep.tree(t["index"])
            role, _c = naming.classify(_track_text(t, devs))
            warm = role in WARM_ROLES
            h = (0.02 + 0.09 * ((k * 7) % 5) / 4) if warm else (0.45 + 0.22 * ((k * 7) % 5) / 4)
            colour = _rgb01_to_hex(*colorsys.hsv_to_rgb(h, 0.7, 0.95))
        else:
            pal = GENRE_PALETTES[palette]
            colour = pal[k % len(pal)]
        set_track(t["index"], color=colour)
        out[f"{t['index']} {t['name']}"] = colour
    return {"scheme": scheme, "coloured": out}


@tool()
def color_clips(track_index: int, color: str, slots: list[int] | None = None) -> dict:
    """Give a track's launcher clips a colour (hex, e.g. '#ff8800'). slots default = every clip on the track."""
    clips = bw.call("get_track", track_index=track_index)["clips"]
    todo = [c["slot"] for c in clips if slots is None or c["slot"] in slots]
    for s in todo:
        clip_settings(track_index, s, color=color)
    return {"track_index": track_index, "coloured_slots": todo, "color": color}
