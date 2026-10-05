"""Build the 140 bpm F# minor trance test template in the clip launcher (one scene per section) from the tracks that already exist in the open project.

Tracks (by name): Kick Clap Snare Hat 'Open Hat' Crash 'Perc Top' Strings 'Strings Stacc' 'Synth Strings' Bass Sub Chords Pluck Lead Pad Atmos Risers Impacts.
Sections (bars): Intro 16, Strings Build 16, Subtle Mid 16, Big Build 16, Massive Drop 32, Outro 8.   usage: python research/build_trance_template.py [section ...]
All music is original: a four-chord loop F#m - D - A - E, a rolling 16th bass, supersaw stabs, plucks and a short hook written here."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bwmcp.core.bridge import bw  # noqa: E402
from bwmcp.tools import clips, library  # noqa: E402

SECTIONS = [("Intro", 16), ("Strings Build", 16), ("Subtle Mid", 16), ("Big Build", 16), ("Massive Drop", 32), ("Outro", 8)]
CHORDS = [(6, "m"), (2, ""), (9, ""), (4, "")]                 # F#m D A E as (pitch class, quality)
TRIAD = {"m": (0, 3, 7), "": (0, 4, 7)}
ROOT_BASS = [42, 38, 45, 40]                                   # F#2 D2 A2 E2
KICK, CLAP, SNARE, HAT, OPEN, CRASH = 60, 60, 60, 60, 60, 60  # every drum is a Sampler: C3 plays the sample at its original pitch
SAMPLES = json.loads((Path(__file__).resolve().parent.parent / "data" / "trance_samples.json").read_text())
TRACKS = {}


def refresh_tracks():
    TRACKS.clear()
    for t in bw.call("get_session")["tracks"]:
        TRACKS[t["name"]] = t["index"]


def N(pitch, start, dur, vel=100):
    return {"pitch": int(pitch), "start": round(float(start), 4), "duration": round(float(dur), 4), "velocity": int(max(1, min(127, vel)))}


def put(track, slot, notes, bars, name):
    ti = TRACKS[track]
    for attempt in range(3):
        try:
            r = clips.write_notes(ti, slot, notes, bars * 4, name)
            if r.get("verified", True):
                return r
        except Exception as e:  # noqa: BLE001
            print("   retry", track, slot, str(e)[:80])
        time.sleep(1.5)
    print("   !! not verified:", track, slot, name)


def voicing(prev, pc, quality, lo=57, hi=76):
    """Triad inversion around the middle register that is closest to the previous voicing (smooth voice leading)."""
    best = None
    for inv in range(3):
        tones = [(pc + i) % 12 for i in TRIAD[quality]]
        tones = tones[inv:] + tones[:inv]
        notes, cur = [], lo
        for t in tones:
            while cur % 12 != t:
                cur += 1
            notes.append(cur)
            cur += 1
        shift = 0
        while sum(notes) / 3 + shift < (lo + hi) / 2 - 6:
            shift += 12
        notes = [n + shift for n in notes]
        cost = 0 if prev is None else sum(abs(a - b) for a, b in zip(sorted(notes), sorted(prev)))
        if best is None or cost < best[0]:
            best = (cost, sorted(notes))
    return best[1]


def chord_bars(bars, start_bar=0):
    prev, out = None, []
    for b in range(bars):
        pc, q = CHORDS[(b + start_bar) % 4]
        prev = voicing(prev, pc, q)
        out.append(prev)
    return out


# ---------------------------------------------------------------- pattern makers
def four_floor(bars, first=0, last=None, vel=118):
    last = bars if last is None else last
    return [N(KICK, b * 4 + k, 0.4, vel) for b in range(first, last) for k in range(4)]


def clap_24(bars, first=0, last=None):
    last = bars if last is None else last
    return [N(CLAP, b * 4 + k, 0.3, 105) for b in range(first, last) for k in (1, 3)]


def hats_16(bars, first=0, last=None, vel=70):
    last = bars if last is None else last
    out = []
    for b in range(first, last):
        for i in range(16):
            if i % 4 == 2:
                continue                                       # leave the off-beat 8ths to the open hat
            out.append(N(HAT, b * 4 + i * 0.25, 0.12, vel + (12 if i % 4 == 0 else 0) + (-8 if i % 2 else 0)))
    return out


def open_off(bars, first=0, last=None, vel=96):
    last = bars if last is None else last
    return [N(OPEN, b * 4 + k + 0.5, 0.4, vel) for b in range(first, last) for k in range(4)]


def rolling_bass(bars, first=0, last=None, vel=108):
    last = bars if last is None else last
    out = []
    for b in range(first, last):
        r = ROOT_BASS[b % 4]
        for k in range(4):
            for i, off in enumerate((0.25, 0.5, 0.75)):
                out.append(N(r + (12 if (k == 3 and i == 2) else 0), b * 4 + k + off, 0.2, vel - (6 if i == 1 else 0)))
    return out


def sub_roots(bars, first=0, last=None, vel=100):
    last = bars if last is None else last
    return [N(ROOT_BASS[b % 4], b * 4, 3.9, vel) for b in range(first, last)]


def pad_chords(bars, first=0, last=None, vel=80, vel_to=None, octave=0):
    last = bars if last is None else last
    ch = chord_bars(bars)
    out = []
    for b in range(first, last):
        v = vel if vel_to is None else vel + (vel_to - vel) * (b - first) / max(1, last - first - 1)
        out += [N(n + octave, b * 4, 3.95, v) for n in ch[b]]
    return out


def stabs(bars, first=0, last=None, vel=100, pattern=(0.5, 1.5, 2.5, 3.5), dur=0.4):
    last = bars if last is None else last
    ch = chord_bars(bars)
    return [N(n, b * 4 + p, dur, vel) for b in range(first, last) for p in pattern for n in ch[b]]


def pluck_arp(bars, first=0, last=None, vel=84, octave=12):
    last = bars if last is None else last
    ch = chord_bars(bars)
    out = []
    for b in range(first, last):
        t = ch[b] + [ch[b][0] + 12]
        order = [0, 1, 2, 3, 2, 1, 2, 3, 0, 1, 2, 3, 2, 1, 3, 2]
        for i, o in enumerate(order):
            out.append(N(t[o] + octave, b * 4 + i * 0.25, 0.22, vel + (10 if i % 4 == 0 else 0) - (6 if i % 2 else 0)))
    return out


def stacc_8ths(bars, first=0, last=None, vel=80, vel_to=None, rise=False):
    last = bars if last is None else last
    ch = chord_bars(bars)
    out = []
    for b in range(first, last):
        v = vel if vel_to is None else vel + (vel_to - vel) * (b - first) / max(1, last - first - 1)
        for i in range(8):
            for n in ch[b]:
                out.append(N(n + (12 if (rise and b >= last - 4) else 0), b * 4 + i * 0.5, 0.45, v + (8 if i % 2 == 0 else 0)))
    return out


HOOK = [  # (bar-in-4, beat, length, pitch): the eight-bar lead hook over F#m D A E F#m D A E
    (0, 0, 0.75, 73), (0, 0.75, 0.75, 78), (0, 1.5, 0.5, 76), (0, 2, 1, 73), (0, 3, 1, 69),
    (1, 0, 0.75, 74), (1, 0.75, 0.75, 78), (1, 1.5, 0.5, 74), (1, 2, 1, 69), (1, 3, 1, 74),
    (2, 0, 0.75, 73), (2, 0.75, 0.75, 76), (2, 1.5, 0.5, 81), (2, 2, 1, 78), (2, 3, 1, 76),
    (3, 0, 1.5, 76), (3, 1.5, 0.5, 71), (3, 2, 1, 80), (3, 3, 1, 76),
]
HOOK_B = [
    (0, 0, 0.75, 78), (0, 0.75, 0.75, 81), (0, 1.5, 0.5, 78), (0, 2, 1, 73), (0, 3, 1, 76),
    (1, 0, 1.5, 78), (1, 1.5, 0.5, 74), (1, 2, 1, 81), (1, 3, 1, 78),
    (2, 0, 0.75, 76), (2, 0.75, 0.75, 81), (2, 1.5, 0.5, 85), (2, 2, 1, 81), (2, 3, 1, 78),
    (3, 0, 2, 80), (3, 2, 0.5, 76), (3, 2.5, 0.5, 78), (3, 3, 1, 80),
]


def lead_notes(first_bar, bars, vel=100, octave=0, b_phrase=False):
    out = []
    for b in range(bars):
        out_phrase = HOOK_B if (b_phrase or (b // 4) % 2 == 1) else HOOK
        for (bb, beat, ln, p) in out_phrase:
            if bb == b % 4:
                out.append(N(p + octave, (first_bar + b) * 4 + beat, ln * 0.95, vel))
    return out


def snare_roll(first_bar, bars, vel_from=50, vel_to=120):
    """Accelerating roll: 1/4 -> 1/8 -> 1/16 -> 1/32 across `bars`."""
    out, t, total = [], first_bar * 4, bars * 4
    end = (first_bar + bars) * 4
    while t < end - 0.01:
        frac = (t - first_bar * 4) / total
        step = 1.0 if frac < 0.25 else 0.5 if frac < 0.5 else 0.25 if frac < 0.75 else 0.125
        out.append(N(SNARE, t, min(step * 0.9, 0.4), vel_from + (vel_to - vel_from) * frac))
        t += step
    return out


# ---------------------------------------------------------------- audio clips
def sample(name, track, slot):
    try:
        r = library.load_sample(name, TRACKS[track], slot, "clip", None)
        return r
    except Exception as e:  # noqa: BLE001
        print("   sample failed", name, str(e)[:100])


def build(sections):
    refresh_tracks()
    sc = {n: i for i, (n, _b) in enumerate(SECTIONS)}
    for n in sections:
        i, bars = sc[n], dict(SECTIONS)[n]
        print(f"== {n} (scene {i}, {bars} bars)")
        session_scene = i
        bw.call("set_scene_name", scene=session_scene, name=f"{i + 1} {n}")
        if n == "Intro":
            put("Kick", i, four_floor(bars, 0, 16, 112), bars, "kick")
            put("Open Hat", i, open_off(bars, 4, 16, 88), bars, "open hat")
            put("Hat", i, hats_16(bars, 8, 16, 62), bars, "hats")
            put("Pluck", i, pluck_arp(bars, 8, 16, 76), bars, "pluck arp")
            put("Pad", i, pad_chords(bars, 0, 16, 70), bars, "pad")
            put("Sub", i, sub_roots(bars, 8, 16, 90), bars, "sub")
            sample("PLX_ATE_140_top_loop_hithere", "Perc Top", i)
            sample("FSS_DPTE_140_fx_atmosphere_fund_E", "Atmos", i)
            sample("FSS_DPTE2_140_fx_upsweep_team", "Risers", i)
        elif n == "Strings Build":
            put("Kick", i, four_floor(bars, 0, 16, 114), bars, "kick")
            put("Open Hat", i, open_off(bars, 0, 16, 92), bars, "open hat")
            put("Hat", i, hats_16(bars, 0, 16, 66), bars, "hats")
            put("Clap", i, clap_24(bars, 8, 16), bars, "clap")
            put("Snare", i, snare_roll(12, 4, 55, 118), bars, "snare roll")
            put("Strings", i, pad_chords(bars, 0, 16, 62, 112, 0), bars, "strings swell")
            put("Strings Stacc", i, stacc_8ths(bars, 8, 16, 70, 108), bars, "strings 8ths")
            put("Synth Strings", i, pad_chords(bars, 4, 16, 60, 100, -12), bars, "synth strings")
            put("Pluck", i, pluck_arp(bars, 0, 16, 80), bars, "pluck arp")
            put("Pad", i, pad_chords(bars, 0, 8, 72), bars, "pad")
            put("Bass", i, rolling_bass(bars, 8, 16, 96), bars, "bass")
            put("Sub", i, sub_roots(bars, 8, 16, 96), bars, "sub")
            put("Crash", i, [N(CRASH, 0, 2, 110)], bars, "crash")
            sample("PLX_ATE_140_top_loop_hithere", "Perc Top", i)
            sample("PLX_ATE_140_fx_loop_riser_breathe", "Risers", i)
            sample("FSS_DPTE_cymbal_crash_reverse_comet", "Impacts", i)
        elif n == "Subtle Mid":
            put("Synth Strings", i, pad_chords(bars, 0, 16, 78, 92, 0), bars, "synth strings")
            put("Strings", i, pad_chords(bars, 0, 16, 66, 84, -12), bars, "strings low")
            put("Pad", i, pad_chords(bars, 0, 16, 76), bars, "pad")
            put("Pluck", i, pluck_arp(bars, 0, 16, 62), bars, "pluck arp")
            put("Lead", i, lead_notes(0, 16, 74, -12), bars, "lead (soft)")
            put("Hat", i, [N(HAT, b * 4 + k, 0.1, 54) for b in range(8, 16) for k in range(4)], bars, "hats tick")
            sample("FSS_DPTE_140_fx_atmosphere_dog_E", "Atmos", i)
            sample("FSS_DPTE_fx_downlifter_above", "Impacts", i)
        elif n == "Big Build":
            put("Kick", i, four_floor(bars, 4, 15, 112) + [N(KICK, 15 * 4 + k, 0.4, 112) for k in (0, 1)], bars, "kick")
            put("Clap", i, clap_24(bars, 8, 15), bars, "clap")
            put("Snare", i, snare_roll(0, 16, 50, 126), bars, "snare roll")
            put("Hat", i, hats_16(bars, 8, 15, 70), bars, "hats")
            put("Strings Stacc", i, stacc_8ths(bars, 0, 15, 66, 120, rise=True), bars, "strings 8ths rising")
            put("Strings", i, pad_chords(bars, 0, 15, 76, 120), bars, "strings swell")
            put("Synth Strings", i, pad_chords(bars, 0, 15, 74, 118, -12), bars, "synth strings")
            put("Pluck", i, pluck_arp(bars, 4, 15, 82), bars, "pluck arp")
            put("Lead", i, lead_notes(0, 8, 92, 0), bars, "lead tease")
            put("Bass", i, rolling_bass(bars, 8, 15, 100), bars, "bass")
            put("Sub", i, sub_roots(bars, 8, 15, 98), bars, "sub")
            put("Crash", i, [N(CRASH, 0, 2, 100), N(CRASH, 8 * 4, 2, 104)], bars, "crash")
            sample("PLX_ATE_140_fx_loop_riser_racetrack", "Risers", i)
            sample("FSS_DPTE_cymbal_crash_reverse_sputnik", "Impacts", i)
            sample("FSS_DPTE2_140_drum_fill_top", "Perc Top", i)
        elif n == "Massive Drop":
            put("Kick", i, four_floor(bars, 0, 32, 124), bars, "kick")
            put("Clap", i, clap_24(bars, 0, 32), bars, "clap")
            put("Hat", i, hats_16(bars, 0, 32, 72), bars, "hats")
            put("Open Hat", i, open_off(bars, 0, 32, 100), bars, "open hat")
            put("Bass", i, rolling_bass(bars, 0, 32, 112), bars, "bass")
            put("Sub", i, sub_roots(bars, 0, 32, 104), bars, "sub")
            put("Chords", i, stabs(bars, 0, 32, 100), bars, "supersaw stabs")
            put("Pad", i, pad_chords(bars, 0, 32, 84), bars, "pad")
            put("Strings", i, pad_chords(bars, 0, 32, 84, None, 0), bars, "strings")
            put("Pluck", i, pluck_arp(bars, 0, 32, 86), bars, "pluck arp")
            put("Lead", i, lead_notes(8, 24, 108, 0), bars, "lead hook")
            put("Crash", i, [N(CRASH, b * 4, 2, 112) for b in (0, 8, 16, 24)], bars, "crash")
            sample("PLX_ATE_140_drum_loop_silver_percussion", "Perc Top", i)
            sample("FSS_DPTE_fx_impact_survive", "Impacts", i)
        elif n == "Outro":
            put("Kick", i, four_floor(bars, 0, 8, 108), bars, "kick")
            put("Hat", i, hats_16(bars, 0, 4, 60), bars, "hats")
            put("Open Hat", i, open_off(bars, 0, 8, 84), bars, "open hat")
            put("Pad", i, pad_chords(bars, 0, 8, 70), bars, "pad")
            put("Pluck", i, pluck_arp(bars, 0, 8, 70), bars, "pluck arp")
            sample("FSS_DPTE_fx_downlifter_claim", "Impacts", i)
            sample("FSS_DPTE_140_fx_atmosphere_fund_E", "Atmos", i)


if __name__ == "__main__":
    which = sys.argv[1:] or [n for n, _b in SECTIONS]
    build(which)
    print("done")
