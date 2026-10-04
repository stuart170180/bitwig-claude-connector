"""Chord library and voicing engine: parse any common chord symbol, build it in many voicing styles (jazz, pop, EDM, ambient), keep it
inside a pitch range and voice-lead a whole progression by smallest total movement.

Definitions follow standard practice (see docs/CHORDS_AND_VOICINGS.md): drop-2 drops the second note from the top of a close 4-note
chord down an octave, drop-3 the third from the top, shell voicings keep root + 3rd + 7th, rootless voicings (Bill Evans A/B) leave the root to
the bass, quartal voicings stack fourths, upper-structure triads put a major triad on top of a dominant's 3rd and 7th."""
import re

# ---- chord library: intervals in semitones from the root (9 = 14, 11 = 17, 13 = 21) -----------------------------------------------
CHORD_TYPES = {
    "": [0, 4, 7], "6": [0, 4, 7, 9], "69": [0, 4, 7, 9, 14], "maj7": [0, 4, 7, 11], "maj9": [0, 4, 7, 11, 14], "maj13": [0, 4, 7, 11, 14, 21],
    "maj7#11": [0, 4, 7, 11, 18], "add9": [0, 4, 7, 14], "m": [0, 3, 7], "m6": [0, 3, 7, 9], "m69": [0, 3, 7, 9, 14], "m7": [0, 3, 7, 10],
    "m9": [0, 3, 7, 10, 14], "m11": [0, 3, 7, 10, 14, 17], "m13": [0, 3, 7, 10, 14, 21], "madd9": [0, 3, 7, 14], "mMaj7": [0, 3, 7, 11],
    "7": [0, 4, 7, 10], "9": [0, 4, 7, 10, 14], "11": [0, 4, 7, 10, 14, 17], "13": [0, 4, 7, 10, 14, 21], "7b9": [0, 4, 7, 10, 13],
    "7#9": [0, 4, 7, 10, 15], "7b5": [0, 4, 6, 10], "7#5": [0, 4, 8, 10], "7#11": [0, 4, 7, 10, 18], "7b13": [0, 4, 7, 10, 20],
    "7alt": [0, 4, 8, 10, 13], "7sus4": [0, 5, 7, 10], "9sus4": [0, 5, 7, 10, 14], "dim": [0, 3, 6], "dim7": [0, 3, 6, 9], "m7b5": [0, 3, 6, 10],
    "aug": [0, 4, 8], "aug7": [0, 4, 8, 10], "sus2": [0, 2, 7], "sus4": [0, 5, 7], "5": [0, 7],
}
ALIASES = {"maj": "", "M": "", "major": "", "min": "m", "-": "m", "minor": "m", "M7": "maj7", "Maj7": "maj7", "Δ": "maj7", "Δ7": "maj7",
           "min7": "m7", "-7": "m7", "mi7": "m7", "min9": "m9", "-9": "m9", "min11": "m11", "-11": "m11", "min6": "m6", "-6": "m6",
           "dom7": "7", "dom": "7", "ø": "m7b5", "ø7": "m7b5", "m7-5": "m7b5", "°": "dim", "o": "dim", "°7": "dim7", "o7": "dim7",
           "+": "aug", "+7": "aug7", "sus": "sus4", "M9": "maj9", "Maj9": "maj9", "M13": "maj13", "mM7": "mMaj7", "m(maj7)": "mMaj7",
           "7(b9)": "7b9", "7(#9)": "7#9", "7-9": "7b9", "7+9": "7#9", "7+5": "7#5", "7-5": "7b5", "alt": "7alt", "6/9": "69", "m6/9": "m69"}
NOTE_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
PC_NAME = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def parse_symbol(symbol: str):
    """'Cmaj7', 'F#m9', 'Bb7#9', 'Dm7/G' -> (root_pc, bass_pc or None, quality, intervals)."""
    s = symbol.strip()
    m = re.fullmatch(r"([A-Ga-g])([#b]?)(.*?)(?:/([A-Ga-g][#b]?))?", s)
    if not m:
        raise ValueError(f"can't parse chord {symbol!r}")
    letter, acc, qual, bass = m.groups()
    root = (NOTE_PC[letter.upper()] + (1 if acc == "#" else -1 if acc == "b" else 0)) % 12
    qual = ALIASES.get(qual, qual)
    if qual not in CHORD_TYPES:
        raise ValueError(f"unknown chord quality {qual!r} in {symbol!r}; known: {sorted(CHORD_TYPES, key=len)}")
    bass_pc = None
    if bass:
        bass_pc = (NOTE_PC[bass[0].upper()] + (1 if bass[1:] == "#" else -1 if bass[1:] == "b" else 0)) % 12
    return root, bass_pc, qual, CHORD_TYPES[qual]


# ---- helpers on interval sets ---------------------------------------------------------------------------------------------------
def _find(iv, lo, hi):
    """First interval (mod 12) in the half-open range [lo, hi) among the chord tones, or None."""
    for i in iv:
        if lo <= i % 12 < hi:
            return i
    return None


def _parts(iv):
    """Role -> interval: third (or sus), fifth, seventh (or None)."""
    return {"third": _find(iv, 2, 6), "fifth": _find(iv, 6, 9), "seventh": _find(iv, 10, 12) if _find(iv, 10, 12) is not None else (9 if 9 in iv and 3 in iv and 6 in iv else None)}


def _close(iv):
    return sorted(set(iv))


def _drop(close4, which):
    """Drop the n-th note from the top (2 = second from top) an octave down."""
    v = sorted(close4)
    for w in which:
        v[-w] -= 12
    return sorted(v)


def _four(iv):
    """Four chord tones for drop voicings: root, third, fifth, seventh/sixth (or the next tension for triads)."""
    p = _parts(iv)
    seventh = p["seventh"]
    if seventh is None:
        seventh = 9 if 9 in iv else 14 if 14 in iv else 12            # sixth, ninth or the octave
    tones = [0, p["third"] if p["third"] is not None else 5, p["fifth"] if p["fifth"] is not None else 7, seventh]
    return sorted(set(tones)) if len(set(tones)) == 4 else sorted(set(tones) | {12})


def build(iv, style: str):
    """Intervals (relative to the root) of the chord in `style`; the caller places the result in a register."""
    p = _parts(iv)
    third = p["third"] if p["third"] is not None else 4
    fifth = p["fifth"] if p["fifth"] is not None else 7
    seventh = p["seventh"]
    minor = third % 12 == 3
    dominant = seventh is not None and seventh % 12 == 10 and third % 12 == 4
    if style == "close":
        return _close(iv)
    if style == "open":                                           # lift every second note an octave: wide, pad-like
        v = _close(iv)
        return sorted(x + 12 if k % 2 == 1 else x for k, x in enumerate(v))
    if style == "drop2":
        return _drop(_four(iv), [2])
    if style == "drop3":
        return _drop(_four(iv), [3])
    if style == "drop2and4":
        return _drop(_four(iv), [2, 4])
    if style == "shell":                                          # root, 3rd, 7th (7th below the 3rd)
        s = seventh if seventh is not None else fifth
        return sorted([0, s, third + 12])
    if style == "rootless_a":                                     # 3 5 7 9
        s = seventh if seventh is not None else 9
        nine = 13 if 13 in iv else 15 if 15 in iv else 14
        return sorted([third, fifth, s, nine])
    if style == "rootless_b":                                     # 7 9 3 5
        s = seventh if seventh is not None else 9
        return sorted([s - 12, 2, third, fifth])
    if style == "quartal":                                        # stacked fourths from a chord-dependent starting note
        start = 14 if minor else (fifth if dominant else third)
        return [start + 5 * k for k in range(4)]
    if style == "so_what":                                        # three fourths + a major third on top (Miles Davis, So What)
        return [14, 19, 24, 29, 33] if minor else [third + 5 * k for k in range(5)]
    if style == "ust":                                            # upper-structure triad (II) over a dominant's 3rd and 7th
        if not dominant:
            return _drop(_four(iv), [2])
        return sorted([third, seventh, 14, 18, 21])
    if style == "cluster":                                        # tight seconds around the chord
        return sorted({0, 2, third, fifth})
    if style == "power":
        return [0, 7, 12]
    if style == "pad":                                            # low root + the chord above
        return sorted(set([-12] + _close(iv)))
    if style == "spread":                                         # root and fifth low, tensions high: wide ambient pad
        top = seventh if seventh is not None else 14
        nine = 14 if 14 > top else 26
        return sorted(set([-12, fifth - 12, third, top, nine]))
    if style == "neo_soul":                                       # R 7 3 5 9: root low, 7th, then a 9th chord stacked above
        s = seventh if seventh is not None else 11 if not minor else 10
        return sorted([0, s, third + 12, fifth + 12, 14 + 12])
    if style == "edm_stab":                                       # root octave + close triad + root on top
        return sorted([-12, 0, third, fifth, 12])
    if style == "supersaw":                                       # trance: doubled root, triad, upper octave triad
        return sorted([-12, 0, third, fifth, 12, third + 12])
    if style == "gospel":                                         # open 6/9 or 9 feel: root, 5, 9, 3 on top, 7
        s = seventh if seventh is not None else 9
        return sorted([0, fifth, s, 14 + 12, third + 12])
    if style == "triad_stack":                                    # a triad with the same triad above in another inversion
        return sorted([0, third, fifth, third + 12, fifth + 12, 24])
    raise ValueError(f"unknown voicing style {style!r}; use one of {sorted(STYLES)}")


STYLES = {
    "close": "plain stacked chord, root position (inversions allowed when voice-leading)",
    "open": "every second note up an octave: wide, pad-like",
    "drop2": "second note from the top dropped an octave: the classic jazz piano / guitar voicing",
    "drop3": "third from the top dropped: wide, good under a melody",
    "drop2and4": "second and fourth from the top dropped: very open, big-band feel",
    "shell": "root, 7th and 3rd only: light, leaves room for a melody and bass",
    "rootless_a": "3 5 7 9 (Bill Evans A): for a pianist with a bassist",
    "rootless_b": "7 9 3 5 (Bill Evans B): the second rootless shape",
    "quartal": "stacked fourths: modern, ambiguous, McCoy Tyner",
    "so_what": "three fourths and a major third on top (Miles Davis, So What)",
    "ust": "upper-structure triad over a dominant's 3rd and 7th: tension harmony",
    "cluster": "tight seconds: dense, ambient",
    "power": "root, fifth, octave: rock, big-room leads",
    "pad": "low root and a close chord above: warm pads",
    "spread": "root and fifth low, tensions high: ambient / cinematic",
    "neo_soul": "root, 7th, then 3 5 9 above: lush neo-soul / lo-fi keys",
    "edm_stab": "octave root with a close triad: house and techno stabs",
    "supersaw": "doubled root with triad and upper triad: trance and uplifting EDM",
    "gospel": "open 6/9 and 9 colours with the third on top",
    "triad_stack": "a triad with the same triad above it in another inversion: bright layered synth chords",
}
GENRE_STYLES = {
    "jazz": ["drop2", "rootless_a", "rootless_b", "shell", "ust"], "bebop": ["shell", "drop2"], "neo_soul": ["neo_soul", "rootless_a", "gospel"],
    "gospel": ["gospel", "drop2"], "lofi": ["neo_soul", "rootless_b", "shell"], "rnb": ["neo_soul", "drop2", "open"],
    "pop": ["open", "pad", "close"], "rock": ["power", "close"], "house": ["edm_stab", "close", "pad"], "deep_house": ["neo_soul", "rootless_a", "pad"],
    "techno": ["edm_stab", "power", "cluster"], "trance": ["supersaw", "pad", "triad_stack"], "progressive": ["pad", "spread", "triad_stack"],
    "big_room": ["supersaw", "power"], "dubstep": ["power", "cluster"], "dnb": ["pad", "neo_soul", "shell"], "hiphop": ["shell", "neo_soul", "cluster"],
    "trap": ["cluster", "shell", "pad"], "ambient": ["spread", "quartal", "cluster", "pad"], "cinematic": ["spread", "open", "quartal"],
    "classical": ["close", "open"], "funk": ["shell", "drop2"], "disco_funk": ["shell", "drop2", "close"], "reggaeton": ["close", "pad"],
}


# ---- placement and voice-leading -----------------------------------------------------------------------------------------------------
INVERTIBLE = {"close", "cluster"}


def place(rel, root_pc: int, center: int = 60):
    """Move the voicing (intervals relative to the root) so its middle note sits near `center`."""
    base = root_pc + 12 * (center // 12)
    pitches = [base + i for i in rel]
    mid = sum(pitches) / len(pitches)
    shift = round((center - mid) / 12) * 12
    return sorted(p + shift for p in pitches)


def _candidates(rel, root_pc, style, center, low, high):
    """[(pitches, own_cost)]: every inversion (where the style allows) in three octaves, inside [low, high]. Root position near the
    centre is cheapest, so a lone chord comes out in root position."""
    out = []
    shapes = [(list(rel), 0)]
    if style in INVERTIBLE:
        cur = sorted(rel)
        for inv in range(1, len(cur)):
            cur = sorted(cur[1:] + [cur[0] + 12])
            shapes.append((cur, inv))
    for sh, inv in shapes:
        base = place(sh, root_pc, center)
        for oct_shift in (-12, 0, 12):
            c = [p + oct_shift for p in base]
            if min(c) >= low and max(c) <= high:
                out.append((c, 0.6 * inv + abs(sum(c) / len(c) - center) * 0.15))
    return out or [(place(rel, root_pc, center), 0.0)]


def _move_cost(a, b):
    if not a:
        return 0.0
    n = min(len(a), len(b))
    pa = sorted(a)[-n:] if len(a) > n else sorted(a)
    pb = sorted(b)
    top_a, top_b = pa[-n:], pb[-n:]
    cost = sum(abs(x - y) for x, y in zip(top_a, top_b)) / n
    cost += abs(sorted(a)[-1] - sorted(b)[-1]) * 0.3 + abs(len(a) - len(b)) * 0.5            # smooth top line, similar density
    return cost


def voice_progression(symbols, style: str = "close", center: int = 60, low: int = 36, high: int = 96, voice_lead: bool = True,
                      add_bass: bool = False, bass_octave: int = 2):
    """List of voicings (lists of MIDI pitches), one per chord. Roman numerals must be resolved to symbols first (see resolve())."""
    if style not in STYLES:
        raise ValueError(f"unknown voicing style {style!r}; use one of {sorted(STYLES)}")
    chords = [parse_symbol(s) for s in symbols]
    cands = []
    for root, bass, _q, iv in chords:
        cands.append(_candidates(build(iv, style), root, style, center, low, high))
    if voice_lead and len(chords) > 1:                                      # dynamic programming over candidate voicings
        best = [[(cands[0][j][1], None) for j in range(len(cands[0]))]]
        for i in range(1, len(cands)):
            row = []
            for cj, own in cands[i]:
                row.append(min((best[i - 1][k][0] + _move_cost(ck, cj) + own, k) for k, (ck, _o) in enumerate(cands[i - 1])))
            best.append(row)
        j = min(range(len(cands[-1])), key=lambda k: best[-1][k][0])
        path = [j]
        for i in range(len(cands) - 1, 0, -1):
            j = best[i][j][1]
            path.append(j)
        path.reverse()
        voiced = [cands[i][path[i]][0] for i in range(len(cands))]
    else:
        voiced = [min(c, key=lambda t: t[1])[0] for c in cands]
    if add_bass:
        out = []
        for (root, bass, _q, _iv), v in zip(chords, voiced):
            b = (bass if bass is not None else root) + 12 * (bass_octave + 1)
            out.append(sorted([b] + [p for p in v if p > b + 4]))
        voiced = out
    return voiced


def describe(pitches) -> str:
    return " ".join(f"{PC_NAME[p % 12]}{p // 12 - 1}" for p in sorted(pitches))


def resolve(chords, key: str = "C", scale: str = "major"):
    """Chord names or roman numerals (I, vi, V7, ii9, bVII, i7 ...) -> chord symbols such as 'Dm7'."""
    from bwmcp.music import music

    out = []
    for c in chords:
        try:
            parse_symbol(c)
            out.append(c)
            continue
        except ValueError:
            pass
        pitches = music.parse_chord(c, key, scale, 4)
        root = pitches[0] % 12
        rel = sorted({(p - pitches[0]) % 24 for p in pitches})
        pcs = {r % 12 for r in rel}
        best = max(CHORD_TYPES.items(), key=lambda kv: (len(pcs & {i % 12 for i in kv[1]}) - 1.5 * len(pcs ^ {i % 12 for i in kv[1]}) / 2, -len(kv[1])))
        out.append(PC_NAME[root] + best[0])
    return out
