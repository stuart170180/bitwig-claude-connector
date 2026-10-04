"""Work out a sensible name (and colour) for a track from its devices, presets, clips and notes."""
import re

# Role -> (keywords, colour). Order matters: more specific roles first.
ROLES = [
    ("Kick", ["kick", "kck"], "#e03131"),
    ("Snare", ["snare", "snr"], "#f76707"),
    ("Clap", ["clap"], "#f59f00"),
    ("Hats", ["hihat", "hi-hat", "hi hat", "hat"], "#fab005"),
    ("Perc", ["perc", "shaker", "conga", "bongo", "tamb", "cowbell", "rim"], "#e8590c"),
    ("Drums", ["drum", "kit", "break", "beat", "groove", "top loop"], "#e4572e"),
    ("808", ["808"], "#c2255c"),
    ("Bass", ["bass", "sub"], "#4c6ef5"),
    ("Vocal", ["vocal", "vox", "voice", "acapella", "choir", "chant"], "#ae3ec9"),
    ("Keys", ["piano", "rhodes", "wurli", "keys", "clav", "organ", "e-piano"], "#2fb380"),
    ("Pad", ["pad", "atmos", "drone", "texture", "strings", "string", "choir"], "#20c997"),
    ("Pluck", ["pluck"], "#94d82d"),
    ("Arp", ["arp"], "#66a80f"),
    ("Lead", ["lead", "solo", "melody", "hook"], "#f2b134"),
    ("Chords", ["chord", "stab", "poly"], "#38d9a9"),
    ("Guitar", ["guitar", "gtr"], "#a9e34b"),
    ("Brass", ["brass", "horn", "trumpet", "sax"], "#fcc419"),
    ("FX", ["fx", "riser", "impact", "sweep", "noise", "whoosh", "downlifter", "uplifter"], "#868e96"),
    ("Synth", ["synth", "saw", "pwm", "polysynth", "phase-4", "fm-4", "polymer", "spire", "serum", "vital"], "#fd7e14"),
]
GENERIC_DEVICES = {"sampler", "drum machine", "instrument layer", "instrument selector", "poly grid", "note grid",
                   "chain", "fx layer", "fx selector", "hw instrument"}
DEFAULT_NAME = re.compile(r"^(inst(rument)?|audio|hybrid|fx|effect|group|track|midi)\s*\d*$", re.I)


def classify(text: str):
    # Match keywords at the start of words only, so "offbeat" isn't "beat" and "that" isn't "hat".
    low = " " + re.sub(r"[_\-.()]+", " ", text.lower()) + " "
    for role, words, color in ROLES:
        if any(re.search(r"(?<![a-z])" + re.escape(w.strip()), low) for w in words):
            return role, color
    return None, None


def classify_notes(notes):
    """Guess a role from MIDI content when there's no telling device/preset name."""
    if not notes:
        return None
    pitches = [n["pitch"] for n in notes]
    drum_hits = sum(1 for n in notes if 35 <= n["pitch"] <= 51 and n["duration"] <= 0.26)
    if drum_hits / len(notes) > 0.7:
        return "Drums"
    starts = {}
    for n in notes:
        starts.setdefault(round(n["start"], 2), []).append(n["pitch"])
    poly = sum(1 for v in starts.values() if len(v) >= 3) / max(1, len(starts))
    avg = sum(pitches) / len(pitches)
    if avg < 50:
        return "Bass"
    if poly > 0.5:
        return "Chords"
    return "Lead"


def is_default(name: str) -> bool:
    return bool(DEFAULT_NAME.match(name.strip()))


def clean(text: str) -> str:
    """Tidy sample/preset names: drop pack prefixes, BPM/key tags, underscores, numbering."""
    t = re.sub(r"\.(wav|aif|aiff|flac|mp3)$", "", text, flags=re.I)
    t = re.sub(r"^\d{1,3}[_.\-]+", "", t)                       # leading numbering like '009_'
    t = t.replace("_", " ")
    t = re.sub(r"\b\d{2,3}\s?bpm\b", "", t, flags=re.I)
    t = re.sub(r"\b(?!(?:808|909|707|606|303|101|505)\b)\d{2,3}\b", "", t)  # stray BPMs; keep drum-machine names
    t = re.sub(r"\s{2,}", " ", t).strip()
    t = re.sub(r"^(?:[A-Z]{2,5}\s){1,2}(?=\w)", "", t)          # pack prefixes like 'AU BTH ', 'RKU HHL '
    t = t.split(" - ")[0]                                        # drop ' - Pack Name' suffixes
    t = re.sub(r"\s{2,}", " ", t).strip(" -")
    return _fit(t, 28).strip(" -") or text[:28]


def _fit(t: str, n: int) -> str:
    """Shorten to n chars at a word boundary."""
    if len(t) <= n:
        return t
    cut = t[:n].rsplit(" ", 1)[0]
    return cut if len(cut) >= n // 2 else t[:n]


def suggest(track: dict, devices: list, clips: list, notes=None, style: str = "smart"):
    """Return (name, colour, reason). style: smart ('Bass - Rippin' Bass' when informative),
    role ('Bass'), source (preset/sample name only)."""
    source, reason = None, None
    instr = next((d for d in devices if d["name"].lower() not in ("eq+", "eq-5", "compressor", "reverb",
                                                                  "delay+", "limiter", "peak limiter")), None)
    if instr:
        if instr.get("preset"):
            source, reason = instr["preset"], f"preset '{instr['preset']}'"
        elif instr["name"].lower() not in GENERIC_DEVICES:
            source, reason = instr["name"], f"device '{instr['name']}'"
        else:
            reason = f"device '{instr['name']}'"
    if not source and clips:
        source, reason = clips[0]["name"], f"clip '{clips[0]['name']}'"
    role, color = classify(source or "") if source else (None, None)
    if not role and instr and instr["name"].lower() == "drum machine":
        role, color = "Drums", "#e4572e"
    if not role and notes:
        role = classify_notes(notes)
        if role:
            color = next(c for r, _, c in ROLES if r == role)
            reason = (reason + ", " if reason else "") + "MIDI note analysis"
    if not role and not source:
        return None, None, "nothing to go on (no devices, presets or clips)"
    pretty = clean(source) if source else None
    if style == "role" or not pretty:
        name = role or pretty
    elif style == "source":
        name = pretty
    else:
        name = pretty if not role or role.lower() in pretty.lower() else f"{role} - {pretty}"
    if name[:1].islower():
        name = name.title()
    return _fit(name, 32), color, reason


def dedupe(names: list):
    """Append 2, 3... to repeated names, keeping the first one plain."""
    seen, out = {}, []
    for n in names:
        if n is None:
            out.append(None)
            continue
        seen[n] = seen.get(n, 0) + 1
        out.append(n if seen[n] == 1 else f"{n} {seen[n]}")
    return out
