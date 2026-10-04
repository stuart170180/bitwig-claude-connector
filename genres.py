"""Genre presets for sidechain ducking. Tempo-independent: release is a fraction of one beat, so the same preset works at
any bpm (release_ms = 60000 / bpm * release_beats). Starting points, to be tuned by ear."""

GENRES = {
    # name: attack_ms, release_beats, ratio, threshold_db, knee_pct, note
    "house":        (1, 0.35, 6, -26, 10, "Classic four-on-the-floor pump; bass, chords and pads duck under the kick."),
    "deep_house":   (2, 0.40, 4, -22, 20, "Softer, rounder duck; keep it musical rather than obvious."),
    "techno":       (1, 0.30, 6, -24, 5, "Tight and fast so the kick stays punchy and the rumble stays out of its way."),
    "trance":       (1, 0.40, 8, -28, 5, "Deep, even pump that breathes with the kick; pads and bass duck hardest."),
    "progressive":  (2, 0.40, 6, -24, 10, "Medium pump; leave leads mostly un-ducked."),
    "big_room":     (0.5, 0.45, 10, -32, 0, "Heavy, very audible pump, the genre signature."),
    "dubstep":      (1, 0.30, 8, -28, 5, "Half-time feel: duck the sub and the mid bass to keep the kick and snare clear."),
    "dnb":          (1, 0.22, 4, -22, 10, "Fast recovery for the high tempo; duck the sub on kick and snare hits."),
    "hiphop":       (2, 0.25, 4, -20, 20, "Mainly keeps the 808 / sub out of the kick."),
    "trap":         (2, 0.25, 4, -20, 20, "Same idea as hip-hop; tune the 808 first, then duck lightly."),
    "pop":          (5, 0.30, 3, -18, 30, "Subtle; the bass and pads duck a little, the listener should not notice."),
    "edm_pop":      (3, 0.35, 5, -22, 15, "Audible but polished pump on the chords and the bass."),
    "disco_funk":   (3, 0.35, 3.5, -20, 20, "Light duck to keep the bass and kick locked together."),
    "reggaeton":    (2, 0.30, 4, -20, 15, "Duck the bass under the kick of the dembow pattern."),
    "rock":         (10, 0.25, 2.5, -16, 30, "Rarely needed; use gently on bass against the kick."),
    "lofi":         (5, 0.40, 3, -18, 30, "Lazy, soft pump on the keys and pads."),
    "ambient":      (20, 0.50, 2, -16, 40, "Very light; only for slow breathing movement."),
}
DEPTH = {"light": 6.0, "medium": 0.0, "heavy": -6.0}   # dB added to the threshold (lower = more ducking)
ALIASES = {"edm": "big_room", "drum_and_bass": "dnb", "dnb_liquid": "dnb", "hip_hop": "hiphop", "uk_garage": "house",
           "tech_house": "house", "melodic_techno": "techno", "psytrance": "trance", "future_bass": "edm_pop"}


def settings(genre: str, depth: str, bpm: float) -> dict:
    g = ALIASES.get(genre.lower().replace(" ", "_").replace("-", "_"), genre.lower().replace(" ", "_").replace("-", "_"))
    if g not in GENRES:
        raise ValueError(f"unknown genre '{genre}'; use one of {sorted(GENRES)}")
    if depth not in DEPTH:
        raise ValueError(f"depth must be one of {list(DEPTH)}")
    attack, beats, ratio, thr, knee, _ = GENRES[g]
    release = max(20.0, min(1200.0, 60000.0 / float(bpm) * beats))
    return {"attack_ms": attack, "release_ms": round(release, 1), "ratio": ratio, "threshold_db": thr + DEPTH[depth], "knee_pct": knee}


def describe() -> list:
    return [{"genre": k, "attack_ms": v[0], "release_beats": v[1], "ratio": v[2], "threshold_db": v[3], "knee_pct": v[4], "note": v[5]}
            for k, v in GENRES.items()]
