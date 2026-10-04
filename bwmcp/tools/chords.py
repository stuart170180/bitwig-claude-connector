"""Chords and voicings: a big chord library, 20 voicing styles, genre suggestions, voice-led progressions written straight into clips."""
from bwmcp.core.bridge import tool
from bwmcp.core.util import _chords_arg, _write
from bwmcp.music import music, voicings


@tool()
def chord_library() -> dict:
    """Every chord quality chord_voicings / write_voiced_chords understands (with its intervals in semitones from the root), the voicing
    styles with a one-line description, and the genre -> suggested voicing styles table."""
    return {"qualities": {(k or "major"): v for k, v in voicings.CHORD_TYPES.items()}, "styles": voicings.STYLES,
            "genre_styles": voicings.GENRE_STYLES}


@tool()
def suggest_voicing(genre: str) -> dict:
    """Voicing styles that suit a genre (jazz, neo_soul, lofi, pop, rock, house, deep_house, techno, trance, progressive, big_room, dubstep,
    dnb, hiphop, trap, ambient, cinematic, funk, reggaeton ...), each with what it sounds like."""
    g = genre.lower().replace(" ", "_").replace("-", "_")
    if g not in voicings.GENRE_STYLES:
        raise ValueError(f"unknown genre '{genre}'; use one of {sorted(voicings.GENRE_STYLES)}")
    return {"genre": g, "styles": {s: voicings.STYLES[s] for s in voicings.GENRE_STYLES[g]}}


@tool()
def chord_voicings(chord: str, styles: list[str] | None = None, center: int = 60) -> dict:
    """Show one chord (e.g. 'Dm9', 'G13', 'Bb7#9', 'Cmaj7/E') in several voicing styles: note names and MIDI pitches for each. styles
    default = all. center = the MIDI note the voicing is placed around (60 = middle C)."""
    out = {}
    for st in (styles or list(voicings.STYLES)):
        v = voicings.voice_progression([chord], st, center=center)[0]
        out[st] = {"notes": voicings.describe(v), "pitches": v, "about": voicings.STYLES[st]}
    return {"chord": chord, "voicings": out}


@tool()
def write_voiced_chords(track_index: int, slot: int, chords: list[str] | None = None, progression: str | None = None, key: str = "C",
                        scale: str = "major", style: str = "drop2", rhythm: str = "sustained", bars_per_chord: float = 1,
                        center: int = 60, low: int = 36, high: int = 96, voice_lead: bool = True, add_bass: bool = False) -> dict:
    """Write a chord progression into a clip using a voicing style, voice-led for the smallest movement between chords.
    chords: symbols ('Dm7','G7','Cmaj7') or roman numerals (ii7, V7, I) resolved in key/scale; or progression = a preset name.
    style: see chord_library (close, open, drop2, drop3, drop2and4, shell, rootless_a, rootless_b, quartal, so_what, ust, cluster, power, pad,
    spread, neo_soul, edm_stab, supersaw, gospel, triad_stack). rhythm: sustained, stabs, pulse, arp_up, arp_updown, strum.
    low/high keep every voicing inside a register; add_bass puts the root two octaves down as a bass note."""
    ch = _chords_arg(chords, progression)
    symbols = voicings.resolve(ch, key, scale)
    voiced = voicings.voice_progression(symbols, style, center=center, low=low, high=high, voice_lead=voice_lead, add_bass=add_bass)
    notes = music.chord_progression(symbols, key, scale, rhythm, bars_per_chord, voicings=voiced)
    res = _write(track_index, slot, notes, len(symbols) * 4 * bars_per_chord, f"{style} {rhythm}")
    res["chords"] = symbols
    res["voicings"] = [voicings.describe(v) for v in voiced]
    return res
