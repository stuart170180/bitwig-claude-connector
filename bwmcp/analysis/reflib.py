"""Reference library: analyse reference tracks once, store in library.json, compare a mix against them.
Built on mastering.analyze (LUFS/TP/crest/LRA/width/mid-side per band) plus a 1/3-octave tonal balance.
Supported input: WAV (8/16/24/32-bit int, 32-bit float via scipy) and AIFF (own PCM parser). MP3/FLAC/AAC/OGG are NOT
supported (no decoder installed, no new dependencies allowed): convert to WAV first."""
import json
import os
import struct
import time

import numpy as np
from scipy import signal

from bwmcp.analysis import mastering  # noqa: E402
from bwmcp.core import paths

LIB = paths.DATA / "references.json"
# 1/3-octave centres, 25 Hz .. 16 kHz (ISO preferred)
CENTERS = [25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000,
           2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000]
GROUPS = [("sub", 20, 60), ("bass", 60, 250), ("low-mid", 250, 500), ("mid", 500, 2000),
          ("presence", 2000, 6000), ("air", 6000, 20000)]
UNSUPPORTED = (".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wma")


# ---------------------------------------------------------------- loading
def _ieee80(b):
    e = ((b[0] & 0x7F) << 8) | b[1]
    m = int.from_bytes(b[2:10], "big")
    return 0.0 if e == 0 and m == 0 else (m / 2 ** 63) * 2 ** (e - 16383)


def _load_aiff(path):
    d = open(path, "rb").read()
    if d[:4] != b"FORM" or d[8:12] not in (b"AIFF", b"AIFC"):
        raise ValueError("not an AIFF file")
    i, fmt, pcm = 12, None, None
    while i + 8 <= len(d):
        cid, ln = d[i:i + 4], struct.unpack(">I", d[i + 4:i + 8])[0]
        body = d[i + 8:i + 8 + ln]
        if cid == b"COMM":
            ch, frames, bits = struct.unpack(">hIh", body[:8])
            fmt = (ch, frames, bits, _ieee80(body[8:18]), body[18:22] if len(body) >= 22 else b"NONE")
        elif cid == b"SSND":
            off = struct.unpack(">I", body[:4])[0]
            pcm = body[8 + off:]
        i += 8 + ln + (ln & 1)
    if not fmt or pcm is None:
        raise ValueError("AIFF missing COMM/SSND")
    ch, frames, bits, sr, comp = fmt
    if comp not in (b"NONE", b"twos", b"sowt"):
        raise ValueError(f"compressed AIFC ({comp!r}) not supported")
    w = bits // 8
    raw = np.frombuffer(pcm[:frames * ch * w], dtype=np.uint8).reshape(-1, w).astype(np.int64)
    if comp == b"sowt":
        raw = raw[:, ::-1]
    v = np.zeros(len(raw), dtype=np.int64)
    for k in range(w):
        v = (v << 8) | raw[:, k]
    v = np.where(v >= 1 << (bits - 1), v - (1 << bits), v)
    return int(round(sr)), (v / float(1 << (bits - 1))).reshape(-1, ch)


def load_audio(path, start=0.0, seconds=None):
    """-> (stereo float64 array, sr). Raises a clear error for unsupported formats."""
    ext = os.path.splitext(path)[1].lower()
    if ext in UNSUPPORTED:
        raise ValueError(f"{ext} is not supported (no decoder installed); convert to WAV or AIFF first")
    if ext in (".aif", ".aiff", ".aifc"):
        sr, x = _load_aiff(path)
        x = x.astype(np.float64)
        x = np.repeat(x, 2, axis=1) if x.shape[1] == 1 else x[:, :2]
        a = int(start * sr)
        return x[a:(len(x) if seconds is None else a + int(seconds * sr))], sr
    x, sr, _ = mastering.load_file(path, start, seconds)
    return x, sr


# ---------------------------------------------------------------- analysis
def third_octave(x, sr):
    """1/3-octave band levels in dB, relative to the mean band level of 100 Hz-10 kHz (tonal balance, level independent; pink noise PSD -3 dB/oct = flat).
    x: stereo array; uses L+R power spectrum. Returns list aligned with CENTERS (None above Nyquist)."""
    f, p = signal.welch(x, sr, nperseg=16384, axis=0)
    p = p.sum(axis=1)
    out = []
    for c in CENTERS:
        lo, hi = c / 2 ** (1 / 6), c * 2 ** (1 / 6)
        if hi > sr / 2:
            out.append(None)
            continue
        sel = (f >= lo) & (f < hi)
        out.append(float(p[sel].sum()) if sel.any() else 1e-30)
    ref = [10 * np.log10(max(v, 1e-30)) for c, v in zip(CENTERS, out) if v is not None and 100 <= c <= 10000]
    ref = float(np.mean(ref))  # normalise to the mean level of 100 Hz-10 kHz (robust: total power is dominated by bass)
    return [None if v is None else round(10 * np.log10(max(v, 1e-30)) - ref, 2) for v in out]


def analyse(x, sr):
    m = mastering.analyze(x, sr)
    return {"loudness": m["loudness"], "peaks": m["peaks"], "dynamics": m["dynamics"], "stereo": m["stereo"],
            "bands": m["bands"], "third_octave_db": third_octave(x, sr), "duration_s": m["duration_s"],
            "sample_rate": sr}


# ---------------------------------------------------------------- library
def _load_lib():
    try:
        return json.loads(LIB.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"references": {}}


def _save_lib(lib):
    LIB.write_text(json.dumps(lib, indent=1), encoding="utf-8")


def add_reference(path, label, start=0.0, seconds=120.0, note=""):
    """Analyse `path` (first `seconds` from `start`) and store it under `label` (replaces an existing label)."""
    x, sr = load_audio(path, start, seconds)
    a = analyse(x, sr)
    lib = _load_lib()
    lib["references"][label] = {"path": path, "added": time.strftime("%Y-%m-%d %H:%M"), "note": note,
                                "section": [start, seconds], **a}
    _save_lib(lib)
    return {"label": label, "lufs": a["loudness"]["integrated_lufs"], "true_peak": a["peaks"]["true_peak_dbtp"],
            "crest_db": a["dynamics"]["crest_factor_db"], "lra": a["loudness"]["lra_lu"],
            "width_pct": a["stereo"]["width_pct"]}


def remove_reference(label):
    lib = _load_lib()
    ok = lib["references"].pop(label, None) is not None
    _save_lib(lib)
    return ok


def list_references():
    return [{"label": k, "path": v["path"], "lufs": v["loudness"]["integrated_lufs"],
             "true_peak": v["peaks"]["true_peak_dbtp"], "crest_db": v["dynamics"]["crest_factor_db"],
             "lra": v["loudness"]["lra_lu"], "width_pct": v["stereo"]["width_pct"], "note": v.get("note", "")}
            for k, v in _load_lib()["references"].items()]


def _get(label):
    refs = _load_lib()["references"]
    if label not in refs:
        raise KeyError(f"no reference '{label}'; have: {', '.join(refs) or 'none'}")
    return refs[label]


def _avg_db(rows):
    """Average a list of dB lists elementwise (power-mean would over-weight loud bands; tonal-balance curves are
    already level-normalised so a dB mean is the usual 'average curve')."""
    out = []
    for vals in zip(*rows):
        v = [a for a in vals if a is not None]
        out.append(round(float(np.mean(v)), 2) if v else None)
    return out


def target_curve(labels=None):
    """Averaged balance (1/3-octave dB, level-normalised) and average numbers of several references (default all)."""
    refs = _load_lib()["references"]
    labels = labels or list(refs)
    rs = [_get(l) for l in labels]
    if not rs:
        raise ValueError("library is empty")
    mean = lambda f: round(float(np.mean([f(r) for r in rs])), 2)
    return {"labels": labels, "centers_hz": CENTERS, "third_octave_db": _avg_db([r["third_octave_db"] for r in rs]),
            "lufs": mean(lambda r: r["loudness"]["integrated_lufs"]), "crest_db": mean(lambda r: r["dynamics"]["crest_factor_db"]),
            "lra": mean(lambda r: r["loudness"]["lra_lu"]), "width_pct": mean(lambda r: r["stereo"]["width_pct"]),
            "true_peak": mean(lambda r: r["peaks"]["true_peak_dbtp"])}


def _group_diff(diff):
    out = {}
    for name, lo, hi in GROUPS:
        v = [d for c, d in zip(CENTERS, diff) if d is not None and lo <= c < hi]
        if v:
            out[name] = round(float(np.mean(v)), 1)
    return out


def compare_to_reference(label, source="live", seconds=20.0, start=0.0, threshold_db=1.5):
    """label: a stored label, or a list/comma string of labels (averaged target). source: 'live' (WASAPI loopback),
    a WAV/AIFF path, or an analysis dict from analyse(). Returns per-band dB differences (mix minus reference)
    and plain advice."""
    if isinstance(label, str) and "," in label:
        label = [s.strip() for s in label.split(",")]
    ref = target_curve(label) if isinstance(label, (list, tuple)) else None
    if ref is None:
        r = _get(label)
        ref = {"third_octave_db": r["third_octave_db"], "lufs": r["loudness"]["integrated_lufs"],
               "crest_db": r["dynamics"]["crest_factor_db"], "lra": r["loudness"]["lra_lu"],
               "width_pct": r["stereo"]["width_pct"], "true_peak": r["peaks"]["true_peak_dbtp"]}
    if isinstance(source, dict):
        a = source
    else:
        if source == "live":
            x, sr, _ = mastering.capture_loopback(seconds)
        else:
            x, sr = load_audio(source, start, seconds)
        a = analyse(x, sr)
    diff = [None if m is None or r is None else round(m - r, 2) for m, r in zip(a["third_octave_db"], ref["third_octave_db"])]
    groups = _group_diff(diff)
    d = {"loudness_lu": round(a["loudness"]["integrated_lufs"] - ref["lufs"], 1),
         "crest_db": round(a["dynamics"]["crest_factor_db"] - ref["crest_db"], 1),
         "lra_lu": round(a["loudness"]["lra_lu"] - ref["lra"], 1),
         "width_pct": round(a["stereo"]["width_pct"] - ref["width_pct"], 1),
         "true_peak_db": round(a["peaks"]["true_peak_dbtp"] - ref["true_peak"], 1)}
    tips = []
    for g, v in groups.items():
        if abs(v) >= threshold_db:
            tips.append(f"{g}: {abs(v)} dB {'louder' if v > 0 else 'quieter'} than the reference - "
                        f"{'cut' if v > 0 else 'boost'} that region by about {round(abs(v) * 0.6, 1)}-{abs(v)} dB (broad EQ).")
    if abs(d["loudness_lu"]) >= 1:
        tips.append(f"Loudness {d['loudness_lu']:+} LU vs reference: adjust the final limiter/gain by {-d['loudness_lu']:+.1f} dB "
                    "(compare tonal balance at matched level, this table is already level independent).")
    if abs(d["crest_db"]) >= 2:
        tips.append(f"Crest factor {d['crest_db']:+} dB: your mix is {'more dynamic/peaky' if d['crest_db'] > 0 else 'more squashed'}"
                    f" - {'more compression/limiting' if d['crest_db'] > 0 else 'ease the compression'}.")
    if abs(d["width_pct"]) >= 10:
        tips.append(f"Stereo width {d['width_pct']:+} points: {'narrow it' if d['width_pct'] > 0 else 'widen it'} (side level vs mid).")
    return {"difference_mix_minus_reference": d, "third_octave_diff_db": dict(zip(CENTERS, diff)),
            "group_diff_db": groups, "advice": tips or ["Very close to the reference."]}
