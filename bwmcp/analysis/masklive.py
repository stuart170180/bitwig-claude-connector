"""Masking between tracks measured at the same time: every track carries a BW Remote probe, the song plays once, and the 24-band spectra are compared.
Unlike masking_report (which solos each track in turn and so only works for looping launcher clips) this is right for arranger songs too."""
import numpy as np

EDGES = 25.0 * (20000.0 / 25.0) ** (np.arange(25) / 24)           # the plug-in's 24 log-spaced bands, 25 Hz .. 20 kHz
CENTRES = np.sqrt(EDGES[:-1] * EDGES[1:])
FLOOR_DB = -75.0           # bands quieter than this are not audible content
CLOSE_DB = 6.0             # two tracks within this many dB in a band compete for it


def band_label(i):
    lo, hi = EDGES[i], EDGES[i + 1]
    f = lambda v: f"{v / 1000:.1f}k" if v >= 1000 else f"{v:.0f}"
    return f"{f(lo)}-{f(hi)} Hz"


def analyse(spectra: dict, top: int = 12) -> dict:
    """spectra: {track name: 24 dB values}. Returns per-band conflicts (who is loudest, who is within CLOSE_DB), a pair ranking and plain advice."""
    names = [n for n, v in spectra.items() if v is not None and len(v) == 24]
    if len(names) < 2:
        return {"tracks": names, "conflicts": [], "pairs": [], "advice": ["Need at least two tracks with signal."]}
    m = np.array([spectra[n] for n in names], float)                # tracks x bands
    conflicts, pair_score = [], {}
    for b in range(24):
        col = m[:, b]
        order = np.argsort(-col)
        lead = order[0]
        if col[lead] < FLOOR_DB:
            continue
        rivals = [int(i) for i in order[1:] if col[i] >= FLOOR_DB and col[lead] - col[i] <= CLOSE_DB]
        if not rivals:
            continue
        group = [int(lead)] + rivals
        conflicts.append({"band": band_label(b), "centre_hz": round(float(CENTRES[b])), "tracks": [names[i] for i in group],
                          "levels_db": [round(float(col[i]), 1) for i in group], "spread_db": round(float(col[lead] - col[group[-1]]), 1)})
        for x in range(len(group)):
            for y in range(x + 1, len(group)):
                key = tuple(sorted((names[group[x]], names[group[y]])))
                pair_score[key] = pair_score.get(key, 0.0) + (CLOSE_DB - abs(col[group[x]] - col[group[y]])) / CLOSE_DB * (1.0 if CENTRES[b] > 40 else 0.6)
    pairs = sorted(({"tracks": list(k), "score": round(float(v), 2), "shared_bands": sum(1 for c in conflicts if set(k) <= set(c["tracks"]))} for k, v in pair_score.items()),
                   key=lambda r: -r["score"])[:top]
    advice = []
    for p in pairs[:5]:
        bands = [c for c in conflicts if set(p["tracks"]) <= set(c["tracks"])]
        lows = [c["band"] for c in bands][:3]
        advice.append(f"{p['tracks'][0]} and {p['tracks'][1]} fight in {len(bands)} band(s) ({', '.join(lows)}): cut one with EQ there or pan / sidechain them apart.")
    return {"tracks": names, "conflicts": sorted(conflicts, key=lambda c: -len(c["tracks"]))[:top * 2], "pairs": pairs, "advice": advice}
