"""Device preset library: named starting points for Bitwig's stock Reverb, Compressor+, Saturator, De-Esser, Gate, Peak Limiter and Tool, in
real units (time in ms, frequency in Hz, dB, %). Time values can follow the project tempo: {"note": "1/64"} or {"beats": 2}.

Starting points, not laws: tempo-locked reverb sizes follow the common rule that pre-delay is about a 1/64 note and the total reverb time a
note value (hall = 2 bars, large room = 1 bar, small room = 1/2 note, tight ambience = 1/4 note); vocal plates sit around 40-60 ms pre-delay and
1.0-1.5 s decay. Your own presets are stored in data/device_presets.json."""
import json

from bwmcp.core import paths

NOTE_BEATS = {"1/1": 4.0, "1/2": 2.0, "1/4": 1.0, "1/8": 0.5, "1/16": 0.25, "1/32": 0.125, "1/64": 0.0625, "1/128": 0.03125}
USER_FILE = paths.DATA / "device_presets.json"


def note_ms(note: str, bpm: float) -> float:
    """'1/8', '1/8.' (dotted), '1/8t' (triplet) -> milliseconds at bpm."""
    t = note.strip().lower()
    mult = 1.5 if t.endswith(".") else 2 / 3 if t.endswith("t") else 1.0
    base = NOTE_BEATS[t.rstrip(".t")]
    return base * mult * 60000.0 / bpm


def evaluate(value, bpm: float):
    """A number stays; {"note": "1/64"} or {"beats": 2} become milliseconds at the tempo."""
    if isinstance(value, dict):
        if "note" in value:
            return round(note_ms(value["note"], bpm), 2)
        if "beats" in value:
            return round(float(value["beats"]) * 60000.0 / bpm, 2)
        raise ValueError(f"unknown value spec {value}")
    return value


PRESETS = {
    "Reverb": {
        "vocal_plate": {"about": "bright smooth plate for lead vocals: 45 ms pre-delay, about 1.3 s",
                        "values": {"PRE-DELAY": 45, "REVERB_TIME": 1300, "ROOM_SIZE": 90, "DIFFUSION": 95, "BUILDUP": 55, "WIDTH": 100, "HIFREQ": 7000, "LOFREQ": 300},
                        "send_mix": 100, "insert_mix": 18},
        "snare_room": {"about": "tight room sized to a quarter note so the tail dies before the next hit",
                       "values": {"PRE-DELAY": {"note": "1/128"}, "REVERB_TIME": {"note": "1/4"}, "ROOM_SIZE": 60, "DIFFUSION": 80, "WIDTH": 90},
                       "send_mix": 100, "insert_mix": 15},
        "small_room": {"about": "half-note room: the glue that makes a mix sound like one space",
                       "values": {"PRE-DELAY": {"note": "1/64"}, "REVERB_TIME": {"note": "1/2"}, "ROOM_SIZE": 70, "DIFFUSION": 85, "WIDTH": 100},
                       "send_mix": 100, "insert_mix": 14},
        "large_room": {"about": "one-bar room for pads and keys",
                       "values": {"PRE-DELAY": {"note": "1/64"}, "REVERB_TIME": {"note": "1/1"}, "ROOM_SIZE": 110, "DIFFUSION": 85, "WIDTH": 100},
                       "send_mix": 100, "insert_mix": 20},
        "hall": {"about": "two-bar hall: strings, choirs, cinematic builds",
                 "values": {"PRE-DELAY": {"note": "1/32"}, "REVERB_TIME": {"beats": 8}, "ROOM_SIZE": 150, "DIFFUSION": 90, "BUILDUP": 60, "HIFREQ": 6000},
                 "send_mix": 100, "insert_mix": 22},
        "ambient_wash": {"about": "very long dark tail for ambient and intros",
                         "values": {"PRE-DELAY": 80, "REVERB_TIME": 6000, "ROOM_SIZE": 200, "DIFFUSION": 100, "BUILDUP": 80, "HIFREQ": 4500, "LOFREQ": 250},
                         "send_mix": 100, "insert_mix": 35},
        "dark_hall": {"about": "hall with the highs rolled off: sits behind a bright mix",
                      "values": {"PRE-DELAY": 30, "REVERB_TIME": 2800, "ROOM_SIZE": 140, "DIFFUSION": 90, "HIFREQ": 3500, "LOFREQ": 250},
                      "send_mix": 100, "insert_mix": 20},
        "tight_ambience": {"about": "barely-there ambience to add life to drums and percussion",
                           "values": {"PRE-DELAY": 5, "REVERB_TIME": 450, "ROOM_SIZE": 55, "DIFFUSION": 70},
                           "send_mix": 100, "insert_mix": 10},
    },
    "Compressor+": {
        "vocal": {"about": "level a lead vocal: 3.5:1, medium attack to keep the consonants, release near 100 ms",
                  "values": {"ratio": 3.5, "attack_ms": 12, "release_ms": 110, "threshold_db": -20, "knee_pct": 40, "makeup_db": 3}},
        "drum_bus": {"about": "glue a drum bus: 4:1, slow-ish attack lets the transients through",
                     "values": {"ratio": 4, "attack_ms": 30, "release_ms": 120, "threshold_db": -16, "knee_pct": 20, "makeup_db": 2}},
        "bass": {"about": "even out a bass: 4:1, quick but not instant attack, release about 120 ms",
                 "values": {"ratio": 4, "attack_ms": 15, "release_ms": 120, "threshold_db": -18, "knee_pct": 30, "makeup_db": 2}},
        "mix_glue": {"about": "gentle 2:1 bus glue for the master or a group",
                     "values": {"ratio": 2, "attack_ms": 30, "release_ms": 150, "threshold_db": -14, "knee_pct": 50, "makeup_db": 1}},
        "parallel_smash": {"about": "hard 10:1 squash, blend it in with mix about 40 % (parallel compression)",
                           "values": {"ratio": 10, "attack_ms": 2, "release_ms": 90, "threshold_db": -30, "knee_pct": 0, "makeup_db": 6, "mix_pct": 40}},
        "leveler": {"about": "slow leveler for pads and strings",
                    "values": {"ratio": 2.5, "attack_ms": 40, "release_ms": 250, "threshold_db": -22, "knee_pct": 60}},
    },
    "Saturator": {
        "warm": {"about": "light tape-ish warmth (drive is in dB)", "values": {"DRIVE": 6, "OUTPUT": -2}},
        "drive": {"about": "obvious harmonic grit for bass and synths", "values": {"DRIVE": 14, "OUTPUT": -5}},
        "hot": {"about": "heavy saturation for leads and drums bus, filtered at the top", "values": {"DRIVE": 22, "OUTPUT": -9, "CUTOFF": 12000}},
    },
    "De-Esser": {
        "vocal": {"about": "tame sibilance on a vocal around 6 kHz", "values": {"FREQ": 6200, "AMOUNT": 60}},
        "bright_vocal": {"about": "for very bright vocals: lower frequency, stronger", "values": {"FREQ": 5200, "AMOUNT": 80}},
    },
    "Gate": {
        "drum_gate": {"about": "tighten a drum: fast attack, short release", "values": {"THRESHOLD_LEVEL": -35, "ATTACK": 0.5, "RELEASE": 80}},
        "noise_gate": {"about": "remove noise between phrases without chopping tails", "values": {"THRESHOLD_LEVEL": -50, "ATTACK": 2, "RELEASE": 200}},
    },
    "Peak Limiter": {
        "streaming_master": {"about": "ceiling -1 dB for streaming with a medium release", "values": {"CEILING": -1.0, "RELEASE": 150}},
        "club_master": {"about": "louder club master: ceiling -0.3 dB, fast release", "values": {"CEILING": -0.3, "RELEASE": 80}},
        "safety": {"about": "a safety limiter that rarely works: ceiling -0.5 dB, slow release", "values": {"CEILING": -0.5, "RELEASE": 400}},
    },
    "Delay+": {
        "slapback": {"about": "short single echo for vocals and guitars", "values": {"TIME": 90, "FEEDBACK": 12, "MIX": 20, "HICUT": 5000, "LOCUT": 200}},
        "quarter": {"about": "plain quarter-note echo, tempo locked", "values": {"TIME": {"note": "1/4"}, "FEEDBACK": 30, "MIX": 25, "HICUT": 6000, "LOCUT": 150}},
        "dotted_eighth": {"about": "the classic dotted-eighth echo (rhythmic leads and guitars)", "values": {"TIME": {"note": "1/8."}, "FEEDBACK": 35, "MIX": 25, "HICUT": 5500, "LOCUT": 200}},
        "triplet": {"about": "triplet-eighth echo for a rolling feel", "values": {"TIME": {"note": "1/8t"}, "FEEDBACK": 38, "MIX": 22, "HICUT": 6500, "LOCUT": 180}},
        "tape_echo": {"about": "dark, softly repeating tape-style echo", "values": {"TIME": {"note": "1/8."}, "FEEDBACK": 45, "MIX": 25, "HICUT": 3500, "LOCUT": 120}},
        "dub": {"about": "long dubby repeats with a dark tail", "values": {"TIME": {"note": "1/4."}, "FEEDBACK": 65, "MIX": 30, "HICUT": 3000, "LOCUT": 250}},
        "ambient_swirl": {"about": "half-note wash with blur and ducking so it stays out of the way", "values": {"TIME": {"note": "1/2"}, "FEEDBACK": 55, "MIX": 35, "HICUT": 4000, "LOCUT": 200, "BLUR": 40, "DUCKING": 30}},
    },
    "Pitch Shifter": {
        "octave_up": {"about": "an octave up, blended in for sparkle", "values": {"PITCH": 12, "MIX": 40, "GRAIN_RATE": 10}},
        "octave_down": {"about": "an octave down, blended in for weight", "values": {"PITCH": -12, "MIX": 50, "GRAIN_RATE": 10}},
        "fifth_up": {"about": "a fifth up for a quick harmony pad", "values": {"PITCH": 7, "MIX": 35, "GRAIN_RATE": 8}},
        "fine_tune_up": {"about": "+10 cents, accurate (1 Hz grains)", "values": {"PITCH": 0.1, "MIX": 100, "GRAIN_RATE": 1}},
    },
    "Tool": {
        "mono_bass": {"about": "make a bass or sub mono", "values": {"WIDTH": 0}},
        "wide": {"about": "widen a pad by 40 %", "values": {"WIDTH": 140}},
    },
}


def user_presets() -> dict:
    return json.loads(USER_FILE.read_text(encoding="utf-8")) if USER_FILE.exists() else {}


def all_presets() -> dict:
    out = {d: dict(p) for d, p in PRESETS.items()}
    for d, p in user_presets().items():
        out.setdefault(d, {}).update(p)
    return out


def save_user_preset(device: str, name: str, values: dict, about: str = ""):
    data = user_presets()
    data.setdefault(device, {})[name] = {"about": about or "saved by you", "values": values}
    USER_FILE.parent.mkdir(parents=True, exist_ok=True)
    USER_FILE.write_text(json.dumps(data, indent=1), encoding="utf-8")


def resolve(device: str, preset: str, bpm: float, as_send: bool = False) -> dict:
    lib = all_presets()
    if device not in lib or preset not in lib[device]:
        raise ValueError(f"no preset '{preset}' for {device}; known: {{ {', '.join(f'{d}: {sorted(p)}' for d, p in lib.items())} }}")
    spec = lib[device][preset]
    values = {k: evaluate(v, bpm) for k, v in spec["values"].items()}
    mix = spec.get("send_mix" if as_send else "insert_mix")
    if mix is not None:
        values["MIX"] = mix
    return values
