"""Music-theory helpers and pattern generators. All times are in beats (1 beat = quarter note)."""
import random
import re

NOTE_NAMES = {"C": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3, "E": 4, "F": 5, "F#": 6, "GB": 6,
              "G": 7, "G#": 8, "AB": 8, "A": 9, "A#": 10, "BB": 10, "B": 11}

SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "pentatonic_major": [0, 2, 4, 7, 9],
    "pentatonic_minor": [0, 3, 5, 7, 10],
    "blues": [0, 3, 5, 6, 7, 10],
}

# General MIDI drum map (Bitwig's Drum Machine default layout starts at C1 = 36).
DRUMS = {"kick": 36, "rim": 37, "snare": 38, "clap": 39, "closed_hat": 42, "low_tom": 45,
         "open_hat": 46, "mid_tom": 47, "crash": 49, "high_tom": 50, "ride": 51, "shaker": 70}

# Drum styles: per-instrument 16-step grids (one bar of 16ths). x = hit, o = ghost/soft.
DRUM_STYLES = {
    "house":     {"kick": "x...x...x...x...", "clap": "....x.......x...", "closed_hat": "..x...x...x...x.", "open_hat": "......o.......o."},
    "techno":    {"kick": "x...x...x...x...", "rim": "..o...o..o....o.", "closed_hat": "xoxoxoxoxoxoxoxo", "clap": "....x.......x..."},
    "hiphop":    {"kick": "x......x.x......", "snare": "....x.......x...", "closed_hat": "x.x.x.x.x.x.x.x."},
    "trap":      {"kick": "x.......x.x.....", "snare": "........x.......", "closed_hat": "xxxxxxxxxxxoxxxo"},
    "dnb":       {"kick": "x.........x.....", "snare": "....x.......x...", "closed_hat": "x.x.x.x.x.x.x.x."},
    "breakbeat": {"kick": "x.....x...x.....", "snare": "....x..o.o..x...", "closed_hat": "x.x.x.x.x.x.x.x."},
    "rock":      {"kick": "x.......x.x.....", "snare": "....x.......x...", "closed_hat": "x.x.x.x.x.x.x.x.", "crash": "x..............."},
    "funk":      {"kick": "x..x..x...x..x..", "snare": "....x..o.o..x..o", "closed_hat": "xoxoxoxoxoxoxoxo"},
    "reggaeton": {"kick": "x...x...x...x...", "snare": "...x..x....x..x.", "closed_hat": "x.x.x.x.x.x.x.x."},
    "garage":    {"kick": "x.........x.....", "snare": "....x.......x...", "closed_hat": "..x..x.x..x..x.x", "shaker": "xoxoxoxoxoxoxoxo"},
}


def parse_key(key: str) -> int:
    """'A', 'F#', 'Bb' -> pitch class."""
    k = key.strip().upper()
    if k not in NOTE_NAMES:
        raise ValueError(f"unknown key {key!r}; use e.g. C, F#, Bb")
    return NOTE_NAMES[k]


def scale_notes(key: str, scale: str, octave: int) -> list[int]:
    if scale not in SCALES:
        raise ValueError(f"unknown scale {scale!r}; options: {', '.join(SCALES)}")
    root = 12 * (octave + 1) + parse_key(key)
    return [root + i for i in SCALES[scale]]


def degree_pitch(key: str, scale: str, octave: int, degree: int) -> int:
    """Scale degree (0-based, may exceed scale length or go negative) to MIDI pitch."""
    sc = SCALES[scale]
    octs, idx = divmod(degree, len(sc))
    return 12 * (octave + 1 + octs) + parse_key(key) + sc[idx]


ROMAN = {"i": 0, "ii": 1, "iii": 2, "iv": 3, "v": 4, "vi": 5, "vii": 6}


def parse_chord(symbol: str, key: str, scale: str, octave: int) -> list[int]:
    """Roman numeral (I, vi, V7, ii9, bVII) diatonic to key/scale, or absolute name (Am, F#m7, Cmaj7, Gsus4)."""
    s = symbol.strip()
    m = re.fullmatch(r"([b#]?)([ivIV]+)(7|9|sus2|sus4)?", s)
    if m and m.group(2).lower() in ROMAN:
        acc, numeral, ext = m.groups()
        deg = ROMAN[numeral.lower()]
        if acc:  # borrowed chord: build major/minor triad from shifted root
            root = degree_pitch(key, "major", octave, deg) + (-1 if acc == "b" else 1)
            third = 4 if numeral.isupper() else 3
            pitches = [root, root + third, root + 7]
        else:
            pitches = [degree_pitch(key, scale, octave, deg + i) for i in (0, 2, 4)]
            if ext in ("7", "9"):
                pitches.append(degree_pitch(key, scale, octave, deg + 6))
            if ext == "9":
                pitches.append(degree_pitch(key, scale, octave, deg + 8))
            if ext == "sus2":
                pitches[1] = degree_pitch(key, scale, octave, deg + 1)
            if ext == "sus4":
                pitches[1] = degree_pitch(key, scale, octave, deg + 3)
        return pitches
    m = re.fullmatch(r"([A-Ga-g][#b]?)(m|min|maj7|m7|7|dim|aug|sus2|sus4|maj|add9|m9|maj9)?", s)
    if not m:
        raise ValueError(f"can't parse chord {symbol!r}")
    root = 12 * (octave + 1) + parse_key(m.group(1))
    quality = m.group(2) or "maj"
    shapes = {"maj": [0, 4, 7], "m": [0, 3, 7], "min": [0, 3, 7], "7": [0, 4, 7, 10], "maj7": [0, 4, 7, 11],
              "m7": [0, 3, 7, 10], "dim": [0, 3, 6], "aug": [0, 4, 8], "sus2": [0, 2, 7], "sus4": [0, 5, 7],
              "add9": [0, 4, 7, 14], "m9": [0, 3, 7, 10, 14], "maj9": [0, 4, 7, 11, 14]}
    return [root + i for i in shapes[quality]]


def voice_lead(prev: list[int] | None, chord: list[int]) -> list[int]:
    """Choose the inversion of `chord` closest to the previous voicing."""
    if not prev:
        return chord
    center = sum(prev) / len(prev)
    best, best_cost = chord, None
    for inv in range(len(chord)):
        v = sorted(chord[inv:] + [p + 12 for p in chord[:inv]])
        for shift in (-12, 0, 12):
            cand = [p + shift for p in v]
            cost = abs(sum(cand) / len(cand) - center)
            if best_cost is None or cost < best_cost:
                best, best_cost = cand, cost
    return best


def _humanize(notes, amount, rng):
    if amount <= 0:
        return notes
    for n in notes:
        n["velocity"] = max(1, min(127, int(n["velocity"] + rng.uniform(-20, 20) * amount)))
    return notes


def drum_pattern(style: str = "house", bars: int = 1, fill: bool = True, swing: float = 0.0,
                 humanize: float = 0.3, seed: int | None = None) -> list[dict]:
    if style not in DRUM_STYLES:
        raise ValueError(f"unknown style {style!r}; options: {', '.join(DRUM_STYLES)}")
    rng = random.Random(seed)
    notes = []
    for bar in range(bars):
        last = fill and bars > 1 and bar == bars - 1
        for inst, grid in DRUM_STYLES[style].items():
            for step, ch in enumerate(grid):
                if ch == ".":
                    continue
                if last and step >= 12 and inst not in ("kick", "closed_hat"):
                    continue  # make room for the fill
                start = bar * 4 + step * 0.25
                if swing and step % 2 == 1:
                    start += 0.25 * swing * 0.5
                notes.append({"pitch": DRUMS[inst], "start": start, "duration": 0.125,
                              "velocity": 110 if ch == "x" else 60})
        if last:  # snare/tom roll over the last beat
            for i, inst in enumerate(["snare", "snare", "high_tom", "mid_tom", "snare", "low_tom", "snare", "snare"]):
                notes.append({"pitch": DRUMS[inst], "start": bar * 4 + 3 + i * 0.125, "duration": 0.125,
                              "velocity": 70 + i * 6})
    return _humanize(notes, humanize, rng)


def bassline(chords: list[str], key: str = "A", scale: str = "minor", style: str = "root",
             bars_per_chord: float = 1, octave: int = 1, seed: int | None = None) -> list[dict]:
    """styles: root (whole notes), eighths, offbeat (house), octave, walking, syncopated."""
    rng = random.Random(seed)
    notes = []
    span = 4 * bars_per_chord
    for ci, sym in enumerate(chords):
        chord = parse_chord(sym, key, scale, octave)
        root, fifth = chord[0], chord[2] if len(chord) > 2 else chord[0] + 7
        t0 = ci * span
        if style == "root":
            notes.append({"pitch": root, "start": t0, "duration": span * 0.95, "velocity": 100})
        elif style == "eighths":
            for i in range(int(span * 2)):
                notes.append({"pitch": root, "start": t0 + i * 0.5, "duration": 0.4, "velocity": 100 if i % 2 == 0 else 80})
        elif style == "offbeat":
            for b in range(int(span)):
                notes.append({"pitch": root, "start": t0 + b + 0.5, "duration": 0.35, "velocity": 105})
        elif style == "octave":
            for i in range(int(span * 2)):
                notes.append({"pitch": root + (12 if i % 2 else 0), "start": t0 + i * 0.5, "duration": 0.4, "velocity": 100})
        elif style == "walking":
            nxt = parse_chord(chords[(ci + 1) % len(chords)], key, scale, octave)[0]
            pool = [root, fifth, chord[1], nxt - 1 if nxt > root else nxt + 1]
            for b in range(int(span)):
                p = root if b == 0 else (pool[3] if b == int(span) - 1 else rng.choice(pool[:3]))
                notes.append({"pitch": p, "start": t0 + b, "duration": 0.9, "velocity": 95})
        elif style == "syncopated":
            for off in [0, 0.75, 1.5, 2.5, 3.25]:
                for rep in range(int(bars_per_chord) or 1):
                    t = t0 + rep * 4 + off
                    if t < t0 + span:
                        notes.append({"pitch": rng.choice([root, root, fifth, root + 12]), "start": t,
                                      "duration": 0.3, "velocity": 100})
        else:
            raise ValueError("bass style must be root, eighths, offbeat, octave, walking or syncopated")
    return notes


def chord_progression(chords: list[str], key: str = "C", scale: str = "major", rhythm: str = "sustained",
                      bars_per_chord: float = 1, octave: int = 4, voicings: list[list[int]] | None = None) -> list[dict]:
    """rhythms: sustained, stabs (offbeat 8ths), pulse (quarters), arp_up, arp_updown, strum.
    voicings: optional ready-made pitch lists, one per chord (see music/voicings.py); otherwise inversions are voice-led."""
    notes, prev = [], None
    span = 4 * bars_per_chord
    for ci, sym in enumerate(chords):
        voiced = voicings[ci] if voicings else voice_lead(prev, parse_chord(sym, key, scale, octave))
        prev = voiced
        t0 = ci * span
        if rhythm == "sustained":
            notes += [{"pitch": p, "start": t0, "duration": span * 0.98, "velocity": 85} for p in voiced]
        elif rhythm == "stabs":
            for b in range(int(span)):
                notes += [{"pitch": p, "start": t0 + b + 0.5, "duration": 0.25, "velocity": 100} for p in voiced]
        elif rhythm == "pulse":
            for b in range(int(span)):
                notes += [{"pitch": p, "start": t0 + b, "duration": 0.8, "velocity": 95 if b % 2 == 0 else 80} for p in voiced]
        elif rhythm in ("arp_up", "arp_updown"):
            seq = voiced + [voiced[0] + 12]
            if rhythm == "arp_updown":
                seq = seq + seq[-2:0:-1]
            for i in range(int(span * 4)):
                notes.append({"pitch": seq[i % len(seq)], "start": t0 + i * 0.25, "duration": 0.22,
                              "velocity": 100 if i % 4 == 0 else 80})
        elif rhythm == "strum":
            notes += [{"pitch": p, "start": t0 + i * 0.03, "duration": span * 0.95 - i * 0.03, "velocity": 90 - i * 4}
                      for i, p in enumerate(voiced)]
        else:
            raise ValueError("rhythm must be sustained, stabs, pulse, arp_up, arp_updown or strum")
    return notes


def melody(chords: list[str], key: str = "C", scale: str = "major", bars_per_chord: float = 1,
           octave: int = 5, density: float = 0.5, seed: int | None = None) -> list[dict]:
    """Chord-aware melody: chord tones on strong beats, stepwise scale motion between."""
    rng = random.Random(seed)
    notes = []
    span = 4 * bars_per_chord
    pool = scale_notes(key, scale, octave) + [p + 12 for p in scale_notes(key, scale, octave)]
    cur = pool[len(pool) // 3]
    for ci, sym in enumerate(chords):
        tones = {p % 12 for p in parse_chord(sym, key, scale, octave)}
        t = 0.0
        while t < span:
            strong = t % 1 == 0
            dur = rng.choice([0.5, 0.5, 1.0, 0.25, 1.5]) if density < 0.7 else rng.choice([0.25, 0.5, 0.5])
            dur = min(dur, span - t)
            if rng.random() < density or t == 0:
                if strong:
                    cands = [p for p in pool if p % 12 in tones and abs(p - cur) <= 7] or [cur]
                    cur = min(cands, key=lambda p: abs(p - cur) + rng.random() * 3)
                else:
                    i = min(range(len(pool)), key=lambda k: abs(pool[k] - cur))
                    cur = pool[max(0, min(len(pool) - 1, i + rng.choice([-1, 1, 1, -2, 2])))]
                notes.append({"pitch": cur, "start": ci * span + t, "duration": dur * 0.9,
                              "velocity": 100 if strong else 85})
            t += dur
    return notes


# Preset progressions for quick song sketches.
PROGRESSIONS = {
    "pop": ["I", "V", "vi", "IV"],
    "sad": ["vi", "IV", "I", "V"],
    "jazz": ["ii7", "V7", "I7", "vi7"],
    "minor_epic": ["i", "VI", "III", "VII"],
    "house": ["i7", "iv7", "v7", "i7"],
    "andalusian": ["i", "VII", "VI", "V"],
    "dark": ["i", "iv", "i", "v"],
}


# --- Clip editing: pure functions over note lists ---------------------------------------------

def quantize(notes, grid=0.25, strength=1.0, swing=0.0):
    out = []
    for n in notes:
        target = round(n["start"] / grid) * grid
        if swing and round(target / grid) % 2 == 1:
            target += grid * swing * 0.5
        out.append({**n, "start": n["start"] + (target - n["start"]) * strength})
    return out


def humanize(notes, timing=0.01, velocity=10, seed=None):
    rng = random.Random(seed)
    return [{**n, "start": max(0.0, n["start"] + rng.uniform(-timing, timing)),
             "velocity": max(1, min(127, round(n["velocity"] + rng.uniform(-velocity, velocity))))} for n in notes]


def transpose(notes, semitones):
    return [{**n, "pitch": n["pitch"] + semitones} for n in notes if 0 <= n["pitch"] + semitones <= 127]


def scale_correct(notes, key, scale):
    allowed = {(parse_key(key) + i) % 12 for i in SCALES[scale]}
    out = []
    for n in notes:
        p = n["pitch"]
        if p % 12 not in allowed:  # snap to nearest scale tone, preferring down on ties
            p = min((p + d for d in (-1, 1, -2, 2) if (p + d) % 12 in allowed), key=lambda x: abs(x - n["pitch"]))
        out.append({**n, "pitch": p})
    return out


def reverse(notes, length):
    return [{**n, "start": max(0.0, length - n["start"] - n["duration"])} for n in notes]


def stretch(notes, factor):
    return [{**n, "start": n["start"] * factor, "duration": n["duration"] * factor} for n in notes]


def legato(notes, length):
    starts = sorted({n["start"] for n in notes})
    nxt = {s: (starts[i + 1] if i + 1 < len(starts) else length) for i, s in enumerate(starts)}
    return [{**n, "duration": max(0.05, nxt[n["start"]] - n["start"])} for n in notes]


def scale_velocity(notes, amount=1.0, offset=0, compress=0.0):
    """amount multiplies, offset adds; compress 0..1 pulls velocities toward their mean."""
    if not notes:
        return notes
    mean = sum(n["velocity"] for n in notes) / len(notes)
    out = []
    for n in notes:
        v = n["velocity"] + (mean - n["velocity"]) * compress
        out.append({**n, "velocity": max(1, min(127, round(v * amount + offset)))})
    return out


def repeat(notes, length, times=2):
    return [{**n, "start": n["start"] + length * k} for k in range(times) for n in notes]


# Krumhansl-Schmuckler key profiles
_MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
_PC_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def detect_key(notes):
    """Duration-weighted Krumhansl-Schmuckler key estimate. Returns the top 3 candidates."""
    hist = [0.0] * 12
    for n in notes:
        hist[n["pitch"] % 12] += n["duration"]
    if not any(hist):
        return []

    def corr(a, b):
        ma, mb = sum(a) / 12, sum(b) / 12
        num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
        den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
        return num / den if den else 0

    res = []
    for root in range(12):
        for name, prof in (("major", _MAJOR), ("minor", _MINOR)):
            rotated = prof[-root:] + prof[:-root]
            res.append({"key": _PC_NAMES[root], "scale": name, "confidence": round(corr(hist, rotated), 3)})
    return sorted(res, key=lambda r: -r["confidence"])[:3]


# --- Chord detection -----------------------------------------------------------------------------

_CHORD_SHAPES = {  # name suffix -> intervals from root
    "": [0, 4, 7], "m": [0, 3, 7], "7": [0, 4, 7, 10], "maj7": [0, 4, 7, 11], "m7": [0, 3, 7, 10],
    "dim": [0, 3, 6], "m7b5": [0, 3, 6, 10], "aug": [0, 4, 8], "sus2": [0, 2, 7], "sus4": [0, 5, 7],
    "6": [0, 4, 7, 9], "m6": [0, 3, 7, 9], "add9": [0, 2, 4, 7], "9": [0, 2, 4, 7, 10], "m9": [0, 2, 3, 7, 10],
    "5": [0, 7],
}


def name_chord(pitches):
    """Best chord name for a set of MIDI pitches (bass note decides inversions: 'C/E')."""
    pcs = {p % 12 for p in pitches}
    if len(pcs) < 2:
        return _PC_NAMES[next(iter(pcs))] if pcs else None
    bass = min(pitches) % 12
    best, best_score = None, -99
    for root in range(12):
        for suffix, shape in _CHORD_SHAPES.items():
            tones = {(root + i) % 12 for i in shape}
            hit = len(pcs & tones)
            score = hit * 2 - len(pcs - tones) * 2 - len(tones - pcs) + (0.5 if root == bass else 0) - len(shape) * 0.1
            if score > best_score:
                best, best_score = (root, suffix), score
    root, suffix = best
    name = _PC_NAMES[root] + suffix
    return name if bass == root else f"{name}/{_PC_NAMES[bass]}"


def detect_chords(notes, length, resolution=None):
    """Chord per segment. resolution in beats (default: 1 bar, or 2 beats if harmony moves faster)."""
    if not notes:
        return []

    def segs(res):
        out = []
        t = 0.0
        while t < length - 1e-6:
            sounding = [n["pitch"] for n in notes if n["start"] < t + res and n["start"] + n["duration"] > t + 1e-3]
            out.append({"start": t, "chord": name_chord(sounding) if sounding else None})
            t += res
        return out
    if resolution:
        result = segs(resolution)
    else:
        bars, halves = segs(4.0), segs(2.0)
        changes = sum(1 for i in range(0, len(halves) - 1, 2) if halves[i]["chord"] != halves[i + 1]["chord"])
        result = halves if changes > len(bars) / 3 else bars
    merged = []
    for s in result:  # collapse repeats
        if merged and merged[-1]["chord"] == s["chord"]:
            continue
        merged.append(s)
    return merged


def roman(chord: str, key: str, scale: str):
    """Roman numeral of a chord name relative to a key (e.g. 'Am' in C major -> 'vi')."""
    if not chord:
        return None
    m = re.match(r"([A-G][#b]?)(.*?)(/.*)?$", chord)
    root = parse_key(m.group(1))
    q = m.group(2)
    deg = (root - parse_key(key)) % 12
    names = {0: "I", 1: "bII", 2: "II", 3: "bIII", 4: "III", 5: "IV", 6: "bV", 7: "V", 8: "bVI", 9: "VI",
             10: "bVII", 11: "VII"}
    if scale in ("minor", "dorian", "phrygian", "harmonic_minor", "pentatonic_minor"):
        names.update({3: "III", 8: "VI", 10: "VII"})
    r = names[deg]
    minor = q.startswith("m") and not q.startswith("maj")
    r = r.lower() if minor or q.startswith("dim") else r
    return r + ("°" if q.startswith("dim") else "") + (q[1:] if minor else q)
