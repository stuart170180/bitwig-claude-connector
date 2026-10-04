"""Masking finder: measure tracks one at a time (solo + loopback capture), find frequency clashes, propose and
apply EQ cuts. The scoring/analysis half is pure numpy (offline-testable); the capture/apply half talks to Bitwig.

    from bwmcp.analysis import masking
    rep = masking.report([3, 4, 5, 6], seconds=3)     # live: needs playback running and Bitwig on WASAPI
    print(masking.format_report(rep))
    masking.apply(rep, max_fixes=2)                   # inserts EQ+ and cuts, re-measures
"""
import time

import numpy as np
from scipy import signal

# 1/3-octave centres, 25 Hz .. 16 kHz
CENTRES = np.array([25 * 2 ** (i / 3) for i in range(30) if 25 * 2 ** (i / 3) <= 16000])
EDGES_LO = CENTRES / 2 ** (1 / 6)
EDGES_HI = CENTRES * 2 ** (1 / 6)
FLOOR_DB = -90.0          # silence floor for band energies
SILENT_DB = -70.0         # track whose total power is below this (dBFS) counts as silent
AUDIBLE_RANGE = 30.0      # bands more than this far below the loudest band of any measured track are ignored
PRIORITY = [("kick", 10), ("vocal", 9), ("vox", 9), ("lead", 8), ("snare", 7), ("bass", 8), ("sub", 8),
            ("pad", 3), ("string", 3), ("chord", 4), ("keys", 5), ("hat", 2), ("fx", 1), ("atmos", 1)]


# ------------------------------------------------------------------ analysis (offline)
def band_spectrum(x, sr):
    """x: samples (n,) or (n,ch). Returns (band_db[len(CENTRES)], total_db). Welch PSD summed into 1/3-oct bands,
    dB relative to full scale power (a full-scale sine reads about -3 dB)."""
    x = np.asarray(x, dtype=float)
    if x.ndim == 2:
        x = x.mean(axis=1)
    if len(x) < 1024:
        raise ValueError("capture too short for analysis")
    nper = int(min(len(x), 16384))
    f, p = signal.welch(x, sr, nperseg=nper, window="hann")
    df = f[1] - f[0]
    out = np.full(len(CENTRES), FLOOR_DB)
    for i, (lo, hi) in enumerate(zip(EDGES_LO, EDGES_HI)):
        m = (f >= lo) & (f < hi)
        if m.any():
            e = p[m].sum() * df
        else:  # band narrower than a bin: interpolate
            e = np.interp(CENTRES[i], f, p) * (hi - lo)
        out[i] = max(FLOOR_DB, 10 * np.log10(max(e, 1e-12)))
    total = 10 * np.log10(max(float(np.mean(x ** 2)), 1e-12))
    return out, float(total)


def pair_masking(a_db, b_db, floor_db=None):
    """Per-band masking score (0..1) for two band spectra. High only when both carry real energy in a band
    (relative to the louder of the two tracks' own peak band) AND their levels are close.
    score = presence * closeness; presence = how far the weaker one is above its audibility floor (0..1 over 20 dB),
    closeness = 1 at equal level, 0 when 12 dB apart or more."""
    a = np.asarray(a_db); b = np.asarray(b_db)
    ref = max(a.max(), b.max())
    fa = fb = (ref - AUDIBLE_RANGE) if floor_db is None else floor_db
    presence = np.clip(np.minimum((a - fa) / 20.0, (b - fb) / 20.0), 0, 1)
    closeness = np.clip(1 - np.abs(a - b) / 12.0, 0, 1)
    return presence * closeness


def total_score(per_band):
    """Single number: summed band scores (a perfect full overlap of 5 bands ~ 5)."""
    return float(np.sum(per_band))


def find_clashes(names, spectra, min_band_score=0.25, min_width=2):
    """spectra: {name: band_db}. Returns clashes ranked worst first. Each clash = a contiguous run of bands
    (>= min_width) where the pair's score exceeds min_band_score."""
    out = []
    ks = list(names)
    gfloor = max(float(np.max(spectra[k])) for k in ks) - AUDIBLE_RANGE if ks else 0.0
    for i in range(len(ks)):
        for j in range(i + 1, len(ks)):
            a, b = ks[i], ks[j]
            s = pair_masking(spectra[a], spectra[b], gfloor)
            hot = s >= min_band_score
            k = 0
            while k < len(s):
                if not hot[k]:
                    k += 1
                    continue
                e = k
                while e + 1 < len(s) and hot[e + 1]:
                    e += 1
                if e - k + 1 >= min_width:
                    sl = slice(k, e + 1)
                    lo, hi = EDGES_LO[k], EDGES_HI[e]
                    out.append({
                        "a": a, "b": b, "lo_hz": round(float(lo), 1), "hi_hz": round(float(hi), 1),
                        "centre_hz": round(float(np.sqrt(lo * hi)), 1), "bands": (k, e),
                        "score": round(float(s[sl].sum()), 3), "peak_score": round(float(s[sl].max()), 2),
                        "a_db": round(float(np.mean(np.asarray(spectra[a])[sl])), 1),
                        "b_db": round(float(np.mean(np.asarray(spectra[b])[sl])), 1),
                    })
                k = e + 1
    out.sort(key=lambda c: -c["score"])
    return out


def _priority(name):
    n = name.lower()
    return max([p for k, p in PRIORITY if k in n], default=5)


def choose_cut(clash, spectra):
    """Decide which track yields. Name priority first (kick/vocal/lead beat pad/fx); otherwise the track whose
    energy is LESS concentrated in the clash region (the other one 'owns' that range)."""
    a, b = clash["a"], clash["b"]
    pa, pb = _priority(a), _priority(b)
    if pa != pb:
        return (b, a) if pa > pb else (a, b)        # (cut, keep)
    k, e = clash["bands"]

    def share(n):
        lin = 10 ** (np.asarray(spectra[n]) / 10)
        return lin[k:e + 1].sum() / lin.sum()
    return (b, a) if share(a) >= share(b) else (a, b)


def describe(c):
    diff = abs(c["a_db"] - c["b_db"])
    return (f"{c['a']} and {c['b']} fight at {c['lo_hz']:.0f}-{c['hi_hz']:.0f} Hz: "
            f"both within {diff:.1f} dB (about {c['a_db']:.0f}/{c['b_db']:.0f} dB band level)")


def propose_eq(clash, spectra):
    """Concrete EQ+ move for the track that should yield. Gain scales with severity (2..4 dB), Q with width."""
    cut, keep = choose_cut(clash, spectra)
    width_oct = np.log2(clash["hi_hz"] / clash["lo_hz"])
    gain = -float(np.clip(1.5 + clash["peak_score"] * 2.5, 2.0, 4.0))
    q = float(np.clip(1.4 / max(width_oct, 0.33), 0.7, 4.0))
    return {"track": cut, "keep": keep,
            "band": {"type": "Bell", "freq_hz": clash["centre_hz"], "gain_db": round(gain, 1),
                     "q": round(q, 2), "enabled": True},
            "why": f"cut {cut} {abs(gain):.1f} dB at {clash['centre_hz']:.0f} Hz (Q {q:.1f}) so {keep} owns the range"}


def analyse(captures, min_band_score=0.25):
    """captures: {name: (x, sr)}. Pure function: spectra, clashes, proposals, total score."""
    spectra, totals, skipped = {}, {}, {}
    for n, (x, sr) in captures.items():
        try:
            db, tot = band_spectrum(x, sr)
        except ValueError as e:
            skipped[n] = str(e)
            continue
        if tot < SILENT_DB:
            skipped[n] = f"silent ({tot:.0f} dBFS)"
            continue
        spectra[n], totals[n] = db, tot
    clashes = find_clashes(list(spectra), spectra, min_band_score)
    for c in clashes:
        c["finding"] = describe(c)
        c["fix"] = propose_eq(c, spectra)
    return {"spectra": {k: [round(float(v), 1) for v in s] for k, s in spectra.items()}, "totals": totals,
            "skipped": skipped, "clashes": clashes, "score": round(sum(c["score"] for c in clashes), 3),
            "_spectra": spectra}


# ------------------------------------------------------------------ live capture
def _bw():
    import server
    return server


def measure_tracks(track_indices=None, seconds=3.0, settle=0.35):
    """Solo each track in turn, capture `seconds` of loopback, restore solo state. Returns
    {"captures": {name: (x, sr)}, "skipped": {name: reason}, "timing": {name: sec}}.
    Skips group tracks (their children are measured individually) and effect/master tracks."""
    server = _bw()
    seconds = max(1.0, float(seconds))
    sess = server.bw.call("get_session")
    if not sess.get("playing"):
        raise RuntimeError("transport is not playing; launch clips/scene first so there is audio to measure")
    tracks = sess["tracks"]
    orig_solo = {t["index"]: bool(t["solo"]) for t in tracks}
    wanted = [t for t in tracks if track_indices is None or t["index"] in track_indices]
    cur = dict(orig_solo)
    caps, skipped, timing = {}, {}, {}
    try:
        for t in wanted:
            name = f"{t['name']}"
            if name in caps:
                name = f"{name}#{t['index']}"
            if t.get("type", "").lower() in ("group", "master", "effect"):
                skipped[name] = f"{t['type']} track (measure its children instead)"
                continue
            if t["mute"]:
                skipped[name] = "muted"
                continue
            t0 = time.time()
            for o in tracks:  # exclusive solo: set every track explicitly, only call when the state changes
                want = o["index"] == t["index"]
                if cur[o["index"]] != want:
                    server.bw.call("set_track_solo", track_index=o["index"], value=want)
                    cur[o["index"]] = want
            time.sleep(settle)
            try:
                from bwmcp.analysis import capture

                x, sr, _ = capture.capture_live(seconds)
            except Exception as e:
                skipped[name] = f"capture failed: {e}"
                continue
            if not server.bw.call("get_session").get("playing"):
                skipped[name] = "transport stopped during capture (someone else stopped playback?)"
                continue
            caps[name] = (x, sr)
            timing[name] = round(time.time() - t0, 2)
    finally:
        for o in tracks:
            try:
                if cur[o["index"]] != orig_solo[o["index"]]:
                    server.bw.call("set_track_solo", track_index=o["index"], value=orig_solo[o["index"]])
            except Exception:
                pass
    return {"captures": caps, "skipped": skipped, "timing": timing, "indices": {t["name"]: t["index"] for t in tracks}}


def report(track_indices=None, seconds=3.0):
    m = measure_tracks(track_indices, seconds)
    r = analyse(m["captures"])
    r["skipped"].update(m["skipped"])
    r["timing_s"] = m["timing"]
    r["indices"] = m["indices"]
    r["seconds"] = seconds
    return r


def format_report(r):
    lines = [f"Masking score {r['score']} ({len(r['clashes'])} clash(es)); measured {list(r['spectra'])}"]
    for n, why in r["skipped"].items():
        lines.append(f"  skipped {n}: {why}")
    for i, c in enumerate(r["clashes"], 1):
        lines.append(f" {i}. [{c['score']}] {c['finding']}")
        lines.append(f"      fix: {c['fix']['why']}")
    return "\n".join(lines)


# ------------------------------------------------------------------ apply
def apply(rep, max_fixes=2, min_score=0.5):
    """Apply the proposed cuts for the worst clashes (one EQ+ per track, reused if already present; bands 1-8
    used in order, existing band types left alone if non-Off), then re-measure the same tracks.
    Returns {"applied": [...], "before": score, "after": score, "after_report": ...}."""
    server = _bw()
    applied, used = [], {}
    fixes = [c for c in rep["clashes"] if c["score"] >= min_score][:max_fixes]
    for c in fixes:
        f = c["fix"]
        ti = rep["indices"][f["track"].split("#")[0]] if f["track"].split("#")[0] in rep["indices"] else rep["indices"][f["track"]]

        server.bw.call("select_track", track_index=ti)
        time.sleep(0.3)
        dl = server.bw.call("list_devices")["devices"]
        di = next((d["index"] for d in dl if d["name"] == "EQ+"), None)
        if di is None:
            server.load_preset("EQ+", track_index=ti)
            dl = server.bw.call("list_devices")["devices"]
            di = next(d["index"] for d in dl if d["name"] == "EQ+")
        state = server.eq_set(ti, di)
        free = [b for b in state if str(b.get("type", "Off")) == "Off"]
        key = (ti, di)
        slot = used.get(key)
        if slot is None:
            if not free:
                continue
            slot = free[0]["band"] if "band" in free[0] else state.index(free[0]) + 1
        used[key] = slot + 1
        band = dict(f["band"]); band["band"] = slot
        server.eq_set(ti, di, [band])
        applied.append({"track": f["track"], "track_index": ti, "device_index": di, **band, "why": f["why"],
                        "clash_bands": c["bands"]})
    after = None
    if applied:
        after = report(list(set(a["track_index"] for a in applied)) + [rep["indices"][n.split("#")[0]]
                       for n in rep["spectra"] if n.split("#")[0] in rep["indices"]], rep.get("seconds", 3.0))
    if after:  # direct, less noisy evidence: level of the cut track inside the clash bands, before vs after
        for a in applied:
            k, e = a["clash_bands"]
            n = a["track"]
            if n in rep["_spectra"] and n in after["_spectra"]:
                a["measured_change_db"] = round(float(np.mean(after["_spectra"][n][k:e + 1])
                                                      - np.mean(rep["_spectra"][n][k:e + 1])), 1)
    return {"applied": applied, "before": rep["score"], "after": after["score"] if after else rep["score"],
            "after_report": after}
