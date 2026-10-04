"""Clips and notes: writing, editing, transforming, chords, variations, MIDI files, arranger clips."""
import time

from bwmcp.control import arrclipsdev
from bwmcp.core.bridge import SETTLE, bw, tool
from bwmcp.core.util import _chords_arg, _hex_to_rgb, _is_drum_track, _read_clip, _write
from bwmcp.devices import presets
from bwmcp.music import expert, midifile, music
from bwmcp.tools.presets import load_preset
from bwmcp.tools.tracks import create_track


@tool()
def delete_clip(track_index: int, slot: int) -> str:
    """Delete the clip in a launcher slot."""
    return bw.call("delete_clip", track_index=track_index, slot=slot)


@tool()
def write_notes(track_index: int, slot: int, notes: list[dict], length_beats: float = 4,
                name: str | None = None) -> dict:
    """Write MIDI notes into a launcher slot (clip created if empty; existing notes replaced).
    notes: [{"pitch": 60, "start": 0.0, "duration": 0.5, "velocity": 100}], times in beats,
    resolution 1/32 note."""
    return _write(track_index, slot, notes, length_beats, name)


@tool()
def write_drums(track_index: int, slot: int, style: str = "house", bars: int = 2, fill: bool = True,
                swing: float = 0.0, humanize: float = 0.3, seed: int | None = None) -> dict:
    """Generate a drum loop (GM mapping, matches Bitwig's Drum Machine: kick=36/C1, snare=38,
    clap=39, closed hat=42, open hat=46). styles: house, techno, hiphop, trap, dnb, breakbeat, rock,
    funk, reggaeton, garage. fill adds a roll in the last bar; swing 0..1; humanize 0..1."""
    notes = music.drum_pattern(style, bars, fill, swing, humanize, seed)
    return _write(track_index, slot, notes, bars * 4, f"{style} drums")


@tool()
def write_bass(track_index: int, slot: int, chords: list[str] | None = None, progression: str | None = None,
               key: str = "A", scale: str = "minor", style: str = "root", bars_per_chord: float = 1,
               octave: int = 1, seed: int | None = None) -> dict:
    """Generate a bassline following chords. chords: roman numerals relative to key/scale
    (['i','VI','III','VII'], 'ii7', 'bVII') or names (['Am','F','C','G']); or a preset progression
    (pop, sad, jazz, minor_epic, house, andalusian, dark). styles: root, eighths, offbeat, octave,
    walking, syncopated."""
    ch = _chords_arg(chords, progression)
    notes = music.bassline(ch, key, scale, style, bars_per_chord, octave, seed)
    return _write(track_index, slot, notes, len(ch) * 4 * bars_per_chord, f"bass {style}")


@tool()
def write_chords(track_index: int, slot: int, chords: list[str] | None = None, progression: str | None = None,
                 key: str = "C", scale: str = "major", rhythm: str = "sustained", bars_per_chord: float = 1,
                 octave: int = 4) -> dict:
    """Generate a voice-led chord progression. Chords as in write_bass. rhythms: sustained, stabs,
    pulse, arp_up, arp_updown, strum. scales: major, minor, dorian, phrygian, lydian, mixolydian,
    harmonic_minor, pentatonic_major, pentatonic_minor, blues."""
    ch = _chords_arg(chords, progression)
    notes = music.chord_progression(ch, key, scale, rhythm, bars_per_chord, octave)
    return _write(track_index, slot, notes, len(ch) * 4 * bars_per_chord, f"chords {rhythm}")


@tool()
def write_melody(track_index: int, slot: int, chords: list[str] | None = None, progression: str | None = None,
                 key: str = "C", scale: str = "major", bars_per_chord: float = 1, octave: int = 5,
                 density: float = 0.5, seed: int | None = None) -> dict:
    """Generate a chord-aware melody (chord tones on beats, stepwise motion between).
    density 0..1 controls how busy it is; change seed for a different take."""
    ch = _chords_arg(chords, progression)
    notes = music.melody(ch, key, scale, bars_per_chord, octave, density, seed)
    return _write(track_index, slot, notes, len(ch) * 4 * bars_per_chord, "melody")


@tool()
def sketch_song(key: str = "A", scale: str = "minor", tempo: float | None = None,
                drum_style: str = "house", progression: str | list[str] = "minor_epic",
                sections: list[dict] | None = None, seed: int | None = None,
                load_instruments: bool = True) -> dict:
    """Build a whole song sketch in the clip launcher: one scene per section, one track per part.
    Creates (or reuses by name) instrument tracks Drums, Bass, Chords, Lead, loads a genre-appropriate
    factory sound on each new track (drum kit, bass, pad/keys, lead), names scenes and writes every clip.
    sections: [{"name": "Intro", "parts": ["drums", "chords"], "variation": "build"|"alt"}];
    default is Intro / Verse / Build / Drop / Breakdown / Drop 2 / Outro. Launch scenes in order to play."""
    chords = progression if isinstance(progression, list) else _chords_arg(None, progression)
    sections = sections or [
        {"name": "Intro", "parts": ["drums", "chords"]},
        {"name": "Verse", "parts": ["drums", "bass", "chords"]},
        {"name": "Build", "parts": ["drums", "bass", "chords", "lead"], "variation": "build"},
        {"name": "Drop", "parts": ["drums", "bass", "chords", "lead"]},
        {"name": "Breakdown", "parts": ["chords", "lead"]},
        {"name": "Drop 2", "parts": ["drums", "bass", "chords", "lead"], "variation": "alt"},
        {"name": "Outro", "parts": ["drums", "chords"]},
    ]
    if tempo:
        bw.call("set_tempo", bpm=tempo)

    parts = {"drums": ("Drums", "#e4572e"), "bass": ("Bass", "#4c6ef5"),
             "chords": ("Chords", "#2fb380"), "lead": ("Lead", "#f2b134")}
    needed = [p for p in parts if any(p in s.get("parts", []) for s in sections)]
    existing = {t["name"]: t["index"] for t in bw.call("get_session")["tracks"]}
    idx, loaded = {}, {}
    for p in needed:
        name, color = parts[p]
        if name in existing:
            idx[p] = existing[name]
        else:
            idx[p] = create_track("instrument", name=name, color=color)["index"]
            if load_instruments:
                sound = presets.default_sound(p, drum_style)
                load_preset(sound, track_index=idx[p])
                loaded[name] = sound

    four_floor = drum_style in ("house", "techno", "garage")
    results = []
    for si, sec in enumerate(sections):
        bw.call("set_scene_name", scene=si, name=sec["name"])
        var = sec.get("variation")
        s = None if seed is None else seed + si
        calm = sec["name"].lower() in ("intro", "breakdown", "outro")
        for p in sec.get("parts", []):
            t = idx[p]
            if p == "drums":
                r = write_drums(t, si, drum_style, bars=len(chords), fill=var == "build", seed=s)
            elif p == "bass":
                style = "syncopated" if var == "alt" else "offbeat" if four_floor else "eighths"
                r = write_bass(t, si, chords, key=key, scale=scale, style=style, seed=s)
            elif p == "chords":
                rhythm = "sustained" if calm else "arp_up" if var == "build" else "stabs"
                r = write_chords(t, si, chords, key=key, scale=scale, rhythm=rhythm)
            elif p == "lead":
                r = write_melody(t, si, chords, key=key, scale=scale, density=0.7 if var == "build" else 0.5,
                                 seed=(seed or 0) + (7 if var == "alt" else 0))
            else:
                raise ValueError(f"unknown part {p!r}; use drums, bass, chords, lead")
            results.append({"section": sec["name"], "part": p, **r})
    return {"tracks": {p: idx[p] for p in needed}, "scenes": [s["name"] for s in sections],
            "instruments_loaded": loaded,
            "clips_written": len(results), "unverified": [r for r in results if not r["verified"]],
            "next": "Launch scene 0, 1, 2... in order (launch(scene=0))."}


@tool()
def get_clip_notes(track_index: int, slot: int) -> dict:
    """Read every note in a launcher clip (pitch, start, duration, velocity; beats, 1/32 resolution),
    plus its loop length and estimated key."""
    notes, length = _read_clip(track_index, slot)
    return {"length_beats": length, "count": len(notes), "key_estimate": music.detect_key(notes), "notes": notes}


@tool()
def edit_clip(track_index: int, slot: int, operation: str, grid: float = 0.25, strength: float = 1.0,
              swing: float = 0.0, semitones: int = 0, key: str | None = None, scale: str = "major",
              amount: float = 1.0, offset: int = 0, compress: float = 0.0, timing: float = 0.01,
              velocity: int = 10, factor: float = 2.0, times: int = 2, seed: int | None = None) -> dict:
    """Edit an existing clip's notes in place. operations:
    quantize (grid beats e.g. 0.25 = 1/16, strength 0..1, swing 0..1), humanize (timing beats, velocity),
    transpose (semitones), scale_correct (key, scale), reverse, stretch (factor: 2 = half speed,
    0.5 = double speed), legato, velocity (amount x, offset +, compress 0..1 toward mean),
    repeat (times: loop the clip content N times), double (= repeat 2). Returns before/after counts."""
    notes, length = _read_clip(track_index, slot)
    if not notes:
        raise RuntimeError("clip is empty or could not be read")
    new_len = length
    if operation == "quantize":
        out = music.quantize(notes, grid, strength, swing)
    elif operation == "humanize":
        out = music.humanize(notes, timing, velocity, seed)
    elif operation == "transpose":
        out = music.transpose(notes, semitones)
    elif operation == "scale_correct":
        if not key:
            key, scale = music.detect_key(notes)[0]["key"], music.detect_key(notes)[0]["scale"]
        out = music.scale_correct(notes, key, scale)
    elif operation == "reverse":
        out = music.reverse(notes, length)
    elif operation == "stretch":
        out, new_len = music.stretch(notes, factor), length * factor
    elif operation == "legato":
        out = music.legato(notes, length)
    elif operation == "velocity":
        out = music.scale_velocity(notes, amount, offset, compress)
    elif operation in ("repeat", "double"):
        n = 2 if operation == "double" else times
        out, new_len = music.repeat(notes, length, n), length * n
    else:
        raise ValueError("unknown operation")
    res = _write(track_index, slot, out, new_len)
    return {"operation": operation, "notes_before": len(notes), "notes_after": len(out),
            "length_beats": new_len, "verified": res["verified"],
            **({"key": key, "scale": scale} if operation == "scale_correct" else {})}


@tool()
def note_expressions(track_index: int, slot: int, select: dict | None = None, set: dict | None = None,
                     ramp: dict | None = None, randomize: dict | None = None, seed: int | None = None) -> dict:
    """Shape Bitwig per-note expressions on selected notes (they're kept by all other edits).
    Properties: velocity (1-127), release_velocity (0-127), velocity_spread (0..1), gain (0..1, 0 = default),
    pan (-1..1), timbre (-1..1), pressure (0..1; Bitwig doesn't report it back, so unverified),
    transpose (micro-pitch in semitones, e.g. 0.5),
    chance (0..1 probability), muted (bool), repeat ({"count": 3, "curve": -1..1, "velocity_curve": -1..1,
    "velocity_end": -1..1}; count 0 = off; ratchets), recurrence ({"length": 4, "mask": 5} = play on cycles
    1 and 3 of 4; mask is a bitfield), occurrence ('ALWAYS', 'FIRST', 'NOT_FIRST', 'PREV', 'NOT_PREV',
    'PREV_CHANNEL', 'NOT_PREV_CHANNEL', 'PREV_KEY', 'NOT_PREV_KEY', 'FILL', 'NOT_FILL').
    set: fixed values; ramp: {"velocity": [40, 120]} across the selection (crescendo, pan sweep...);
    randomize: {"timbre": 0.3, "velocity": 12} adds +/- amount. select: optional note filter, e.g. {"pitch": [36, 36]} (range) or {"pitches": [36, 38]},
    {"start": [0, 8]} beats, {"velocity": [0, 80]}, {"beat": [0, 2]} (beats 1 & 3 of each bar),
    {"offbeat": true}, {"every": 2, "offset": 1}, {"chance": 0.5}, {"top": true} / {"bottom": true}
    (highest/lowest note of each chord). Keys combine with AND; omit to edit every note."""
    notes, _ = _read_clip(track_index, slot)
    chosen = expert.select(notes, select, seed)
    if not chosen:
        raise RuntimeError("no notes matched the selection")
    updates = expert.shape(chosen, set, ramp, randomize, seed)
    res = {"updated": 0, "not_found": []}
    for i in range(0, len(updates), 200):
        r = bw.call("set_note_props", notes=updates[i:i + 200])
        res["updated"] += r["updated"]
        res["not_found"] += r["not_found"]
    # Expression-only changes don't fire note events, so force a fresh read to verify.
    after = {(n["start"], n["pitch"]): n for n in _read_clip(track_index, slot)[0]}
    sample_after = [after.get((u["start"], u["pitch"])) for u in updates[:3]]
    return {"selected": len(chosen), **res, "example_after": sample_after}


@tool()
def transform_notes(track_index: int, slot: int, operation: str, select: dict | None = None,
                    semitones: int = 0, beats: float = 0.0, intervals: list[int] | None = None,
                    key: str | None = None, scale: str = "major", axis: float | None = None,
                    rate: float = 0.25, pattern: str = "up", gate: float = 0.9, amount: float = 0.03,
                    direction: str = "down", division: float = 0.25, length: float | None = None,
                    factor: float | None = None, spread: int = 2, mode: str = "drop2", inversion: int = 1,
                    accent_pattern: str = "x...", boost: int = 25, keep: float = 0.5,
                    seed: int | None = None) -> dict:
    """Advanced edits on selected notes (per-note expressions are preserved). operations:
    transpose (semitones), nudge (beats, +/-), delete, mute, unmute,
    harmonize (intervals in scale steps: [2] = 3rd above, [2, 4] = triad, [-7] = octave below; key/scale,
    detected if omitted), invert (mirror around axis pitch), arpeggiate (rate beats, pattern
    up/down/updown/random, gate), strum (amount beats, direction down/up), flam (amount = grace offset),
    chop (division beats), set_length (length beats, or factor), randomize_pitch (spread steps, in key if
    given), voicing (mode close/open/drop2/drop3/inversion/spread_octaves, inversion n), accent
    (accent_pattern of x . - per 16th, boost), thin (keep 0..1 of notes). select: optional note filter, e.g. {"pitch": [36, 36]} (range) or {"pitches": [36, 38]},
    {"start": [0, 8]} beats, {"velocity": [0, 80]}, {"beat": [0, 2]} (beats 1 & 3 of each bar),
    {"offbeat": true}, {"every": 2, "offset": 1}, {"chance": 0.5}, {"top": true} / {"bottom": true}
    (highest/lowest note of each chord). Keys combine with AND; omit to edit every note."""
    notes, length_beats = _read_clip(track_index, slot)
    if not notes:
        raise RuntimeError("clip is empty or could not be read")
    chosen = expert.select(notes, select, seed)
    if not chosen:
        raise RuntimeError("no notes matched the selection")

    # Native moves/deletes keep everything Bitwig stores on the note.
    if operation in ("transpose", "nudge"):
        moves = [{"start": n["start"], "pitch": n["pitch"], "d_pitch": semitones if operation == "transpose" else 0,
                  "d_start": beats if operation == "nudge" else 0} for n in chosen]
        # move in an order that never lands on a note that hasn't moved yet
        rev = (semitones > 0) if operation == "transpose" else (beats > 0)
        moves.sort(key=lambda m: (m["pitch"], m["start"]) if operation == "transpose" else (m["start"], m["pitch"]),
                   reverse=rev)
        bw.call("move_notes", notes=moves)
        return {"operation": operation, "notes": len(moves)}
    if operation == "delete":
        bw.call("delete_notes", notes=[{"start": n["start"], "pitch": n["pitch"]} for n in chosen])
        return {"operation": operation, "deleted": len(chosen)}
    if operation in ("mute", "unmute"):
        bw.call("set_note_props", notes=[{"start": n["start"], "pitch": n["pitch"], "muted": operation == "mute"}
                                         for n in chosen])
        return {"operation": operation, "notes": len(chosen)}

    if operation in ("harmonize", "randomize_pitch") and not key and operation == "harmonize":
        k = music.detect_key(notes)[0]
        key, scale = k["key"], k["scale"]
    ops = {
        "harmonize": lambda: expert.harmonize(notes, chosen, intervals or [2], key, scale),
        "invert": lambda: expert.invert(notes, chosen, axis),
        "arpeggiate": lambda: expert.arpeggiate(notes, chosen, rate, pattern, gate, seed),
        "strum": lambda: expert.strum(notes, chosen, amount, direction),
        "flam": lambda: expert.flam(notes, chosen, amount),
        "chop": lambda: expert.chop(notes, chosen, division, gate),
        "set_length": lambda: expert.set_length(notes, chosen, length, factor or 1.0),
        "randomize_pitch": lambda: expert.randomize_pitch(notes, chosen, spread, key, scale, seed),
        "voicing": lambda: expert.voicing(notes, chosen, mode, inversion),
        "accent": lambda: expert.accent(notes, chosen, accent_pattern, 0.25, boost),
        "thin": lambda: expert.thin(notes, chosen, keep, seed),
    }
    if operation not in ops:
        raise ValueError(f"unknown operation {operation!r}")
    out = [n for n in ops[operation]() if 0 <= n["start"] < length_beats + 1e-6]
    res = _write(track_index, slot, out, length_beats)
    return {"operation": operation, "selected": len(chosen), "notes_before": len(notes), "notes_after": len(out),
            "verified": res["verified"], **({"key": key, "scale": scale} if operation == "harmonize" else {})}


@tool()
def clip_settings(track_index: int, slot: int, loop_start: float | None = None, loop_length: float | None = None,
                  loop_enabled: bool | None = None, play_start: float | None = None, play_stop: float | None = None,
                  shuffle: bool | None = None, accent: float | None = None, launch_mode: str | None = None,
                  launch_quantization: str | None = None, name: str | None = None, color: str | None = None,
                  show_in_editor: bool = False) -> dict:
    """Read or change a launcher clip's settings: loop start/length (beats), loop on/off, play start/stop,
    groove shuffle on/off, accent (0..1), launch_mode (default, from_start, continue_or_from_start,
    continue_or_synced, synced), launch_quantization (default, none, 8, 4, 2, 1, 1/2, 1/4, 1/8, 1/16),
    name, color (hex). show_in_editor opens it in Bitwig's detail editor. Returns the settings after."""
    bw.call("focus_clip", track_index=track_index, slot=slot)
    time.sleep(0.4)
    args = {k: v for k, v in dict(loop_start=loop_start, loop_length=loop_length, loop_enabled=loop_enabled,
                                  play_start=play_start, play_stop=play_stop, shuffle=shuffle, accent=accent,
                                  launch_mode=launch_mode, launch_quantization=launch_quantization,
                                  name=name).items() if v is not None}
    if color:
        args["color"] = _hex_to_rgb(color)
    if args:
        bw.call("set_clip_settings", **args)
        time.sleep(SETTLE)
    if show_in_editor:
        bw.call("show_clip_in_editor")
    return bw.call("get_clip_settings")


@tool()
def write_euclidean(track_index: int, slot: int, layers: list[dict], steps_per_beat: int = 4, bars: int = 1) -> dict:
    """Polyrhythmic Euclidean patterns. layers: [{"pitch": 36, "pulses": 4, "steps": 16, "rotation": 0,
    "velocity": 110, "accent_first": true, "chance": 1.0}, ...]. Each layer spreads `pulses` hits as evenly
    as possible over `steps` (each step = 1/steps_per_beat beats), looping to fill `bars`. Different step
    counts per layer create polymeters (e.g. 3 over 16 against 4 over 16, or 5/12)."""
    length = bars * 4
    notes = []
    step_len = 1 / steps_per_beat
    for L in layers:
        if not (1 <= L.get("steps", 0) <= 64) or not (0 <= L.get("pulses", -1) <= L["steps"]):
            raise ValueError(f"layer {L}: need 1 <= steps <= 64 and 0 <= pulses <= steps")
    layers = [L for L in layers if L["pulses"] > 0]
    for L in layers:
        pat = expert.euclid(L["pulses"], L["steps"], L.get("rotation", 0))
        total = int(length / step_len)
        for i in range(total):
            if pat[i % len(pat)]:
                first = (i % len(pat)) == next(j for j, b in enumerate(pat) if b)
                v = L.get("velocity", 100) + (15 if first and L.get("accent_first", True) else 0)
                n = {"pitch": L["pitch"], "start": i * step_len, "duration": step_len * 0.9, "velocity": min(127, v)}
                if L.get("chance", 1) < 1:
                    n["chance"] = L["chance"]
                notes.append(n)
    return _write(track_index, slot, notes, length, "euclidean")


@tool()
def detect_chords(track_index: int, slot: int, resolution: float | None = None) -> dict:
    """Name the chords in a clip (with inversions, e.g. 'C/E'), plus the clip's key and Roman numerals.
    resolution: beats per chord slot (default: per bar, or per half bar when harmony moves faster)."""
    notes, length = _read_clip(track_index, slot)
    if not notes:
        raise RuntimeError("clip is empty")
    key = music.detect_key(notes)[0]
    chords = music.detect_chords(notes, length, resolution)
    for c in chords:
        c["roman"] = music.roman(c["chord"], key["key"], key["scale"])
        c["bar"] = int(c["start"] // 4) + 1
    return {"key": f"{key['key']} {key['scale']}", "confidence": key["confidence"], "chords": chords,
            "progression": " - ".join(c["chord"] or "rest" for c in chords)}


@tool()
def make_variation(track_index: int, slot: int, to_slot: int, kind: str = "mutate", amount: float = 0.3,
                   seed: int | None = None) -> dict:
    """Write a variation of a clip into another slot (for fills, transitions and evolving loops).
    kind: mutate (shift some notes in pitch/time, kept in the clip's key), sparse (drop notes, keep
    downbeats), busy (add ghost notes), fill (last beat becomes a roll), syncopate (push hits a 16th early).
    amount 0..1 = how much changes; change seed for another take."""
    from bwmcp.music import variations
    notes, length = _read_clip(track_index, slot)
    if not notes:
        raise RuntimeError("source clip is empty")
    k = music.detect_key(notes)[0] if kind == "mutate" else None
    out = variations.variation(notes, length, kind, amount, k and k["key"], k["scale"] if k else "major", seed)
    res = _write(track_index, to_slot, out, length, f"{kind} var")
    return {"from_slot": slot, "to_slot": to_slot, "kind": kind, "notes_before": len(notes),
            "notes_after": len(out), "verified": res["verified"]}


@tool()
def transpose_project(semitones: int, include_drums: bool = False, track_indices: list[int] | None = None) -> dict:
    """Transpose every MIDI clip in the project (or the given tracks) by semitones, keeping all per-note
    expressions. Drum tracks (Drum Machine or drum-named) are skipped unless include_drums - transposing
    drums would swap kit pieces."""
    session = bw.call("get_session", with_clips=True)
    original = session["selected_track"]["index"]
    done, skipped = [], []
    for t in session["tracks"]:
        if track_indices is not None and t["index"] not in track_indices:
            continue
        if t["type"] == "Audio" or not t.get("clips"):
            continue
        bw.call("select_track", track_index=t["index"])
        time.sleep(0.2)
        if not include_drums and _is_drum_track(t, bw.call("list_devices")["devices"]):
            skipped.append(t["name"])
            continue
        for c in t["clips"]:
            r = transform_notes(t["index"], c["slot"], "transpose", semitones=semitones)
            done.append({"track": t["name"], "slot": c["slot"], "notes": r["notes"]})
    if original is not None and original >= 0:
        bw.call("select_track", track_index=original)
    return {"semitones": semitones, "clips_transposed": len(done), "skipped_drum_tracks": skipped, "clips": done}


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
def get_arranger_clip_notes(limit: int = 200) -> dict:
    """Notes, loop and name of the ARRANGER clip currently selected in Bitwig (select one in the Arrange view first;
    it reports exists=false when none is focused). Same 1/32 grid as launcher clips. Limitation: it follows Bitwig's own
    selection and could not be pointed at a clip recorded by record_arrangement from the script, so select the clip by hand."""
    info = arrclipsdev.arrclip_info(bw)
    if not info.get("exists"):
        return {"exists": False, "hint": "no arranger clip is selected: click one in Bitwig's Arrange view first", "info": info}
    return {"info": info, **arrclipsdev.arrclip_notes(bw, limit=limit)}


@tool()
def edit_arranger_clip(operation: str, notes: list[dict] | None = None, name: str | None = None,
                       length_beats: float | None = None, semitones: int = 0) -> dict:
    """Edit the arranger clip currently selected in Bitwig. operation: write (replace its notes with `notes`, optional
    length_beats), clear, rename (name), transpose (semitones), quantize, duplicate, duplicate_content. Select the clip in
    the Arrange view first. Not verified against arrangement playback in live tests: read it back with get_arranger_clip_notes."""
    if not arrclipsdev.arrclip_info(bw).get("exists"):
        raise ValueError("no arranger clip is selected: click one in Bitwig's Arrange view first")
    if operation == "write":
        return {"result": arrclipsdev.arrclip_write(bw, notes or [], True, length_beats)}
    if operation == "clear":
        return {"result": arrclipsdev.arrclip_clear(bw)}
    if operation == "rename":
        return {"result": arrclipsdev.arrclip_set_name(bw, name or "")}
    if operation in ("transpose", "quantize", "duplicate", "duplicate_content"):
        extra = {"semitones": semitones} if operation == "transpose" else {}
        return {"result": arrclipsdev.arrclip_op(bw, operation, **extra)}
    raise ValueError("operation must be write, clear, rename, transpose, quantize, duplicate or duplicate_content")
