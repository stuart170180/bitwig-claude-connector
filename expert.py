"""Expert note editing: selection filters, expression shaping and advanced transforms.
Notes are dicts with pitch/start/duration/velocity plus optional Bitwig expression fields."""
import random

import music

EXPR_KEYS = ("release_velocity", "velocity_spread", "gain", "pan", "timbre", "pressure", "transpose",
             "muted", "chance", "repeat", "occurrence", "recurrence")
EXPR_DEFAULTS = {"velocity_spread": 0, "gain": 0, "pan": 0, "timbre": 0, "pressure": 0, "transpose": 0,
                 "muted": False, "chance": 1}


# --- Selection ----------------------------------------------------------------------------------

def select(notes, sel: dict | None, seed=None):
    """Filter notes. sel keys (all optional, combined with AND):
    pitch: [lo, hi] or [p1, p2, ...] (list of >2 or explicit 'pitches')
    pitches: exact list; start: [lo, hi] beats; velocity: [lo, hi];
    beat: positions within the bar in beats, e.g. [0, 2] = beats 1 and 3; offbeat: true = not on a beat;
    every: n (every nth note in time order) with optional offset; chance: 0..1 random subset;
    top / bottom: true = highest / lowest note of each chord; bar_length: beats per bar (default 4)."""
    if not sel:
        return list(notes)
    rng = random.Random(seed)
    bar = sel.get("bar_length", 4)
    out = sorted(notes, key=lambda n: (n["start"], n["pitch"]))
    if "pitch" in sel:
        p = sel["pitch"]
        out = [n for n in out if (p[0] <= n["pitch"] <= p[1] if len(p) == 2 else n["pitch"] in p)]
    if "pitches" in sel:
        out = [n for n in out if n["pitch"] in sel["pitches"]]
    if "start" in sel:
        out = [n for n in out if sel["start"][0] <= n["start"] < sel["start"][1]]
    if "velocity" in sel:
        out = [n for n in out if sel["velocity"][0] <= n["velocity"] <= sel["velocity"][1]]
    if "beat" in sel:
        out = [n for n in out if any(abs((n["start"] % bar) - b) < 1e-3 for b in sel["beat"])]
    if sel.get("offbeat"):
        out = [n for n in out if abs(n["start"] - round(n["start"])) > 1e-3]
    if sel.get("top") or sel.get("bottom"):
        groups = {}
        for n in out:
            groups.setdefault(round(n["start"], 3), []).append(n)
        pick = max if sel.get("top") else min
        out = [pick(g, key=lambda n: n["pitch"]) for g in groups.values()]
    if "every" in sel:
        off = sel.get("offset", 0)
        out = [n for i, n in enumerate(out) if (i - off) % sel["every"] == 0 and i >= off]
    if "chance" in sel:
        out = [n for n in out if rng.random() < sel["chance"]]
    return out


def same(a, b):
    return a["pitch"] == b["pitch"] and abs(a["start"] - b["start"]) < 1e-6


def has_expression(n):
    return any(k in n and n[k] != EXPR_DEFAULTS.get(k) for k in EXPR_KEYS if k != "release_velocity") or \
        n.get("release_velocity", n["velocity"]) != n["velocity"]


# --- Expression shaping -------------------------------------------------------------------------

def shape(notes, set_: dict | None = None, ramp: dict | None = None, randomize: dict | None = None,
          seed=None):
    """Return per-note property updates. set_: fixed values; ramp: {prop: [from, to]} across the
    selection in time order; randomize: {prop: amount} adds +/- amount (velocity in MIDI units)."""
    rng = random.Random(seed)
    ordered = sorted(notes, key=lambda n: (n["start"], n["pitch"]))
    span = (ordered[-1]["start"] - ordered[0]["start"]) if len(ordered) > 1 else 0
    updates = []
    for n in ordered:
        u = {"start": n["start"], "pitch": n["pitch"]}
        if set_:
            u.update(set_)
        if ramp:
            t = (n["start"] - ordered[0]["start"]) / span if span else 0
            for k, (a, b) in ramp.items():
                u[k] = a + (b - a) * t
        if randomize:
            for k, amt in randomize.items():
                base = u.get(k, n.get(k, EXPR_DEFAULTS.get(k, 0)))
                u[k] = base + rng.uniform(-amt, amt)
        if "velocity" in u:
            u["velocity"] = max(1, min(127, round(u["velocity"])))
        for k in ("pan", "timbre"):
            if k in u:
                u[k] = max(-1, min(1, u[k]))
        for k in ("gain", "pressure", "chance", "velocity_spread"):
            if k in u:
                u[k] = max(0, min(1, u[k]))
        updates.append(u)
    return updates


# --- Transforms (return a new full note list) --------------------------------------------------

def _replace(notes, chosen, changed):
    keep = [n for n in notes if not any(same(n, c) for c in chosen)]
    return keep + changed


def harmonize(notes, chosen, intervals, key, scale):
    """Add diatonic voices: intervals are scale steps (2 = a third, 4 = a fifth, 7 = octave,
    -7 = octave down)."""
    sc = music.SCALES[scale]
    root = music.parse_key(key)
    added = []
    for n in chosen:
        pc = (n["pitch"] - root) % 12
        deg = min(range(len(sc)), key=lambda i: abs(sc[i] - pc))  # nearest degree for chromatic notes
        octv = (n["pitch"] - root - sc[deg]) // 12
        for iv in intervals:
            d = deg + iv
            o, i = divmod(d, len(sc))
            p = root + 12 * (octv + o) + sc[i]
            if 0 <= p <= 127 and not any(m["pitch"] == p and abs(m["start"] - n["start"]) < 1e-6 for m in notes + added):
                added.append({**n, "pitch": p, "velocity": max(1, n["velocity"] - 10)})
    return notes + added


def invert(notes, chosen, axis=None):
    axis = axis if axis is not None else (min(n["pitch"] for n in chosen) + max(n["pitch"] for n in chosen)) / 2
    return _replace(notes, chosen, [{**n, "pitch": int(round(2 * axis - n["pitch"]))} for n in chosen
                                    if 0 <= round(2 * axis - n["pitch"]) <= 127])


def arpeggiate(notes, chosen, rate=0.25, pattern="up", gate=0.9, seed=None):
    """Turn chords (notes sharing a start) into arpeggios across each chord's duration."""
    rng = random.Random(seed)
    groups = {}
    for n in chosen:
        groups.setdefault(round(n["start"], 3), []).append(n)
    out = []
    for start, g in groups.items():
        g.sort(key=lambda n: n["pitch"])
        seq = {"up": g, "down": g[::-1], "updown": g + g[-2:0:-1] if len(g) > 2 else g,
               "random": g}[pattern]
        length = max(n["duration"] for n in g)
        steps = max(1, int(round(length / rate)))
        for i in range(steps):
            src = rng.choice(g) if pattern == "random" else seq[i % len(seq)]
            out.append({**src, "start": start + i * rate, "duration": rate * gate})
    return _replace(notes, chosen, out)


def strum(notes, chosen, amount=0.03, direction="down"):
    """Offset chord notes in time like a strum (down = low to high)."""
    groups = {}
    for n in chosen:
        groups.setdefault(round(n["start"], 3), []).append(n)
    out = []
    for g in groups.values():
        g.sort(key=lambda n: n["pitch"], reverse=(direction == "up"))
        for i, n in enumerate(g):
            out.append({**n, "start": n["start"] + i * amount, "duration": max(0.05, n["duration"] - i * amount)})
    return _replace(notes, chosen, out)


def flam(notes, chosen, offset=0.03, velocity_drop=40):
    """Add a quiet grace note just before each selected note."""
    grace = [{**n, "start": max(0, n["start"] - offset), "duration": offset,
              "velocity": max(1, n["velocity"] - velocity_drop)} for n in chosen if n["start"] >= offset]
    return notes + grace


def chop(notes, chosen, division=0.25, gate=0.9):
    out = []
    for n in chosen:
        k = max(1, int(round(n["duration"] / division)))
        out += [{**n, "start": n["start"] + i * division, "duration": division * gate} for i in range(k)]
    return _replace(notes, chosen, out)


def set_length(notes, chosen, length=None, factor=None):
    return _replace(notes, chosen, [{**n, "duration": max(0.03, length if length else n["duration"] * factor)}
                                    for n in chosen])


def randomize_pitch(notes, chosen, spread=2, key=None, scale="major", seed=None):
    """Move notes by up to +/- spread scale steps (or semitones without a key)."""
    rng = random.Random(seed)
    out = []
    for n in chosen:
        if key:
            pool = [p for p in range(n["pitch"] - 12, n["pitch"] + 13)
                    if (p - music.parse_key(key)) % 12 in music.SCALES[scale]]
            pool.sort(key=lambda p: abs(p - n["pitch"]))
            idx = min(len(pool) - 1, rng.randint(0, spread * 2))
            p = pool[idx]
        else:
            p = n["pitch"] + rng.randint(-spread, spread)
        out.append({**n, "pitch": max(0, min(127, p))})
    return _replace(notes, chosen, out)


def voicing(notes, chosen, mode="drop2", inversion=1):
    """Re-voice chords: close, open (spread), drop2, drop3, inversion (n), spread_octaves."""
    groups = {}
    for n in chosen:
        groups.setdefault(round(n["start"], 3), []).append(n)
    out = []
    for g in groups.values():
        g = sorted(g, key=lambda n: n["pitch"])
        ps = [n["pitch"] for n in g]
        if len(ps) < 3:
            out += g
            continue
        if mode == "close":
            base = ps[0]
            ps = sorted(base + ((p - base) % 12) for p in ps)
        elif mode == "inversion":
            for _ in range(inversion % len(ps)):
                ps = ps[1:] + [ps[0] + 12]
        elif mode in ("drop2", "drop3"):
            k = 2 if mode == "drop2" else 3
            ps[-k] -= 12
        elif mode == "open":
            ps = [p - 12 if i % 2 == 1 and i < len(ps) - 1 else p for i, p in enumerate(ps)]
        elif mode == "spread_octaves":
            ps = [p + 12 * (i // 2) for i, p in enumerate(ps)]
        else:
            raise ValueError("voicing mode: close, open, drop2, drop3, inversion, spread_octaves")
        out += [{**n, "pitch": max(0, min(127, p))} for n, p in zip(g, sorted(ps))]
    return _replace(notes, chosen, out)


def accent(notes, chosen, pattern="x...", step=0.25, boost=25, cut=15):
    """Apply an accent pattern: x = accent (+boost), . = soften (-cut), - = unchanged."""
    out = []
    for n in chosen:
        ch = pattern[int(round(n["start"] / step)) % len(pattern)]
        v = n["velocity"] + (boost if ch == "x" else -cut if ch == "." else 0)
        out.append({**n, "velocity": max(1, min(127, v))})
    return _replace(notes, chosen, out)


def thin(notes, chosen, keep=0.5, seed=None):
    rng = random.Random(seed)
    drop = [n for n in chosen if rng.random() > keep]
    return [n for n in notes if not any(same(n, d) for d in drop)]


def euclid(pulses, steps, rotation=0):
    """Bjorklund/Euclidean rhythm as a list of booleans."""
    if steps <= 0 or pulses <= 0:
        return [False] * max(steps, 0)
    pattern = [((i * pulses) // steps) != (((i - 1) * pulses) // steps) for i in range(steps)]
    r = rotation % steps
    return pattern[-r:] + pattern[:-r] if r else pattern
