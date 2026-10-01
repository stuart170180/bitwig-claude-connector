"""Pitch and tuning analysis: monophonic note tracking (YIN) for vocals/leads/basses, and a
tuning-offset + key estimate for polyphonic material (chords, full mixes)."""
import io

import numpy as np
from scipy import signal

import music

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def hz_to_note(hz, ref=440.0):
    """(note name with octave, cents off the nearest equal-tempered note) for a frequency."""
    m = 69 + 12 * np.log2(hz / ref)
    n = int(round(m))
    return f"{NAMES[n % 12]}{n // 12 - 1}", float((m - n) * 100)


def yin(frame, sr, fmin=60.0, fmax=1100.0, thresh=0.15):
    """YIN fundamental estimate for one frame. Returns (hz, clarity 0..1) or (None, 0)."""
    n = len(frame)
    w = n // 2
    tau_max, tau_min = min(int(sr / fmin), w - 1), max(2, int(sr / fmax))
    spec = np.fft.rfft(frame, 2 * n)
    head = np.fft.rfft(frame[:w], 2 * n)
    c = np.fft.irfft(spec * np.conj(head))[:w]                      # c[tau] = sum_j x[j] * x[j + tau]
    cs = np.concatenate([[0.0], np.cumsum(frame ** 2)])
    d = cs[w] + (cs[w:2 * w] - cs[:w]) - 2 * c                      # difference function
    d[0] = 0.0
    cm = np.ones(w)
    cm[1:] = d[1:] * np.arange(1, w) / np.maximum(np.cumsum(d[1:]), 1e-12)  # cumulative mean normalised
    below = np.where(cm[tau_min:tau_max] < thresh)[0]
    if len(below):
        tau = tau_min + below[0]
        while tau + 1 < tau_max and cm[tau + 1] < cm[tau]:
            tau += 1
    else:
        tau = tau_min + int(np.argmin(cm[tau_min:tau_max]))
        if cm[tau] > 0.5:
            return None, 0.0
    if 1 < tau < w - 1:                                             # parabolic refinement
        a, b, cc = cm[tau - 1], cm[tau], cm[tau + 1]
        denom = a - 2 * b + cc
        tau_f = tau + (0.5 * (a - cc) / denom if denom else 0.0)
    else:
        tau_f = float(tau)
    return float(sr / tau_f), float(max(0.0, 1 - cm[tau]))


def track(x, sr, hop_s=0.01, frame=2048, gate_db=-55.0):
    """Frame-by-frame f0 track of the mono mix. Returns times, f0 (nan where unvoiced), clarity."""
    mono = x.mean(axis=1) if x.ndim == 2 else x
    hop = int(hop_s * sr)
    starts = range(0, max(1, len(mono) - frame), hop)
    t = np.array([(s + frame / 2) / sr for s in starts])
    f0, cl = np.full(len(t), np.nan), np.zeros(len(t))
    for i, s in enumerate(starts):
        fr = mono[s:s + frame]
        if len(fr) < frame or 20 * np.log10(np.sqrt(np.mean(fr ** 2)) + 1e-12) < gate_db:
            continue
        hz, c = yin(fr - fr.mean(), sr)
        if hz is not None:
            f0[i], cl[i] = hz, c
    return t, f0, cl


def segments(t, f0, clarity, min_dur=0.08, min_clarity=0.85, ref=440.0):
    """Group the f0 track into notes: one entry per sustained pitch with its cents deviation."""
    voiced = np.isfinite(f0) & (clarity >= min_clarity)
    m = np.full(len(f0), np.nan)
    m[voiced] = 69 + 12 * np.log2(f0[voiced] / ref)
    nn = np.where(voiced, np.round(m), -999)
    if len(nn) >= 5:                                                # median filter removes one-frame glitches
        nn = signal.medfilt(nn, 5)
    out, i = [], 0
    while i < len(nn):
        if nn[i] < 0:
            i += 1
            continue
        j = i
        while j + 1 < len(nn) and nn[j + 1] == nn[i]:
            j += 1
        if t[j] - t[i] + (t[1] - t[0] if len(t) > 1 else 0) >= min_dur:
            seg = m[i:j + 1][np.isfinite(m[i:j + 1])]
            if len(seg):
                n = int(nn[i])
                cents = (seg - n) * 100
                out.append({"note": f"{NAMES[n % 12]}{n // 12 - 1}", "midi": n, "start_s": round(float(t[i]), 2),
                            "duration_s": round(float(t[j] - t[i]), 2), "cents": round(float(np.median(cents)), 1),
                            "vibrato_cents": round(float(np.std(cents)), 1),
                            "hz": round(float(ref * 2 ** ((n - 69) / 12)), 2)})
        i = j + 1
    return out


def poly_tuning(x, sr, max_seconds=40.0, ref=440.0):
    """Global tuning offset (cents vs A=440) from spectral peaks of the whole signal, plus its confidence and a
    pitch-class energy profile (tuning-corrected). Works on chords and mixes."""
    mono = x.mean(axis=1) if x.ndim == 2 else x
    mono = mono[:int(max_seconds * sr)]
    win, hop = 8192, 4096
    w = np.hanning(win)
    f = np.fft.rfftfreq(win, 1 / sr)
    band = (f >= 80) & (f <= 4000)
    peaks_hz, peaks_w = [], []
    for s in range(0, len(mono) - win, hop):
        seg = mono[s:s + win]
        if np.sqrt(np.mean(seg ** 2)) < 10 ** (-55 / 20):
            continue
        mag = np.abs(np.fft.rfft(seg * w))
        idx, _ = signal.find_peaks(np.where(band, mag, 0), height=mag[band].max() * 0.04, distance=3)
        for k in idx:
            a, b, c = np.log(mag[k - 1] + 1e-12), np.log(mag[k] + 1e-12), np.log(mag[k + 1] + 1e-12)
            denom = a - 2 * b + c
            delta = 0.5 * (a - c) / denom if denom else 0.0
            hz = (k + delta) * sr / win
            peaks_hz.append(hz)
            peaks_w.append(mag[k])
    if not peaks_hz:
        return None
    hz, wt = np.array(peaks_hz), np.array(peaks_w)
    m = 12 * np.log2(hz / ref)
    dev = m - np.round(m)
    z = np.sum(wt * np.exp(2j * np.pi * dev))
    offset = float(np.angle(z) / (2 * np.pi) * 100)
    confidence = float(np.abs(z) / wt.sum())                        # 0 = peaks scattered, 1 = perfectly on one grid
    pc = np.zeros(12)
    for mi, wi in zip(m - offset / 100, wt):
        pc[(int(round(mi)) + 9) % 12] += wi
    return {"offset_cents": round(offset, 1), "confidence": round(confidence, 2),
            "a4_hz": round(ref * 2 ** (offset / 1200), 2), "pitch_classes": pc}


def key_from_profile(pc):
    fake = [{"pitch": i, "duration": float(v)} for i, v in enumerate(pc) if v > 0]
    return music.detect_key(fake)[:3] if fake else []


def analyze(x, sr, mode="auto", threshold_cents=25.0):
    if float(np.abs(x).max()) < 1e-4:
        raise ValueError("audio is silent (live: press play in Bitwig; file: try another start time)")
    t, f0, cl = track(x, sr)
    active = np.isfinite(f0)
    clear = float(np.mean(cl[active] >= 0.85)) if active.any() else 0.0
    if mode == "auto":
        mode = "mono" if active.mean() > 0.2 and clear > 0.75 else "poly"
    res = {"mode": mode, "duration_s": round(len(x) / sr, 1)}
    pt = poly_tuning(x, sr)
    if pt:
        res["tuning"] = {k: v for k, v in pt.items() if k != "pitch_classes"}
        res["tuning"]["verdict"] = (
            "in tune with A=440" if abs(pt["offset_cents"]) <= 8 else
            f"{abs(pt['offset_cents']):.0f} cents {'sharp' if pt['offset_cents'] > 0 else 'flat'} of A=440 (A4 ≈ {pt['a4_hz']} Hz)")
        if pt["confidence"] < 0.35:
            res["tuning"]["note"] = "low confidence: little tonal content, or the material is deliberately detuned/atonal"
        res["key_estimate"] = key_from_profile(pt["pitch_classes"])
    if mode == "mono":
        notes = segments(t, f0, cl)
        res["notes"] = notes
        if notes:
            dur = sum(n["duration_s"] for n in notes)
            off = [n for n in notes if abs(n["cents"]) > threshold_cents]
            wmean = sum(n["cents"] * n["duration_s"] for n in notes) / dur
            res["summary"] = {
                "notes_found": len(notes), f"notes_over_{int(threshold_cents)}_cents": len(off),
                "average_cents_off": round(float(sum(abs(n["cents"]) * n["duration_s"] for n in notes) / dur), 1),
                "average_bias_cents": round(float(wmean), 1),
                "range": f"{min(notes, key=lambda n: n['midi'])['note']} - {max(notes, key=lambda n: n['midi'])['note']}",
                "worst": sorted(notes, key=lambda n: -abs(n["cents"]))[:3],
                "advice": _advice(notes, off, wmean, threshold_cents)}
        else:
            res["summary"] = {"notes_found": 0, "advice": "no steady pitched notes found - try mode='poly' for chords or mixes"}
    res["_track"] = (t, f0, cl)
    return res


def _advice(notes, off, bias, thr):
    tips = []
    if len(off) / len(notes) > 0.4:
        tips.append(f"{len(off)} of {len(notes)} notes are more than {thr:.0f} cents off - consider pitch correction.")
    if abs(bias) > 12:
        tips.append(f"The part sits consistently {abs(bias):.0f} cents {'sharp' if bias > 0 else 'flat'} - "
                    "retune the whole part (Sampler/Polymer transpose fine-tune, or the source) instead of note by note.")
    if not tips:
        tips.append("Pitch is tight - nothing needs correcting.")
    return tips


def render(res, title="Pitch & tuning"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    bg, fg, grid = "#15171c", "#e6e6e6", "#30343c"
    plt.rcParams.update({"text.color": fg, "axes.labelcolor": fg, "xtick.color": fg, "ytick.color": fg,
                         "axes.edgecolor": grid, "font.size": 9})
    t, f0, cl = res["_track"]
    fig, axes = plt.subplots(2, 1, figsize=(12, 6.5), facecolor=bg, gridspec_kw={"height_ratios": [2, 1]})
    for ax in axes:
        ax.set_facecolor(bg)
        ax.grid(True, color=grid, lw=0.5)
    ax = axes[0]
    ok = np.isfinite(f0) & (cl > 0.8)
    if ok.any():
        midi = 69 + 12 * np.log2(f0 / 440)
        cents = np.abs((midi - np.round(midi)) * 100)
        sc = ax.scatter(t[ok], midi[ok], c=np.clip(cents[ok], 0, 50), cmap="RdYlGn_r", s=6, vmin=0, vmax=50)
        lo, hi = int(np.nanmin(midi[ok])) - 1, int(np.nanmax(midi[ok])) + 2
        ax.set_yticks(range(lo, hi))
        ax.set_yticklabels([f"{NAMES[n % 12]}{n // 12 - 1}" for n in range(lo, hi)])
        ax.set_ylim(lo, hi)
        fig.colorbar(sc, ax=ax, label="cents off")
    ax.set_title(title, color=fg)
    ax.set_xlabel("s")
    ax = axes[1]
    notes = res.get("notes") or []
    if notes:
        xs = [n["start_s"] + n["duration_s"] / 2 for n in notes]
        ax.bar(xs, [n["cents"] for n in notes], width=[max(n["duration_s"], 0.05) for n in notes],
               color=["#ff6b6b" if abs(n["cents"]) > 25 else "#51cf66" for n in notes])
        ax.axhline(25, color="#fcc419", ls="--", lw=0.8)
        ax.axhline(-25, color="#fcc419", ls="--", lw=0.8)
        ax.set_ylabel("cents")
        ax.set_ylim(-50, 50)
    else:
        tu = res.get("tuning") or {}
        ax.axis("off")
        ax.text(0.02, 0.6, f"Tuning: {tu.get('verdict', 'n/a')}   (confidence {tu.get('confidence', '-')})", transform=ax.transAxes, fontsize=12)
        ks = res.get("key_estimate") or []
        if ks:
            ax.text(0.02, 0.25, "Key: " + ", ".join(f"{k['key']} {k['scale']} ({k['confidence']})" for k in ks), transform=ax.transAxes, fontsize=12)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=90, facecolor=bg)
    plt.close(fig)
    return buf.getvalue()
