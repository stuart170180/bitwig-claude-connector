"""Master-bus analysis: loudness, peaks, dynamics, mid/side, stereo image, spectrum; PNG dashboard."""
import io
import os
import time

import numpy as np
import pyloudnorm as pyln
from scipy import signal
from scipy.io import wavfile

TARGETS = {  # integrated LUFS, true-peak ceiling dBTP
    "streaming": (-14.0, -1.0), "spotify": (-14.0, -1.0), "youtube": (-14.0, -1.0), "apple": (-16.0, -1.0),
    "soundcloud": (-11.0, -1.0), "club": (-8.0, -0.3), "cd": (-9.0, -0.3), "broadcast": (-23.0, -1.0),
}
BANDS = [("sub", 20, 60), ("bass", 60, 250), ("low-mid", 250, 2000), ("high-mid", 2000, 6000), ("air", 6000, 20000)]
# Rough "balanced modern mix" share of energy per band (percent), used only for gentle tonal hints.
REFERENCE_SHARE = {"sub": 18, "bass": 32, "low-mid": 30, "high-mid": 13, "air": 7}


def db(x):
    return float(20 * np.log10(max(float(x), 1e-12)))


# --- Sources ---------------------------------------------------------------------------------------

def capture_loopback(seconds: float):
    """Record the default Windows output (WASAPI loopback). Fails if the device is held exclusively
    (e.g. Bitwig on ASIO4ALL) - switch Bitwig's audio system to WASAPI to allow live capture."""
    import pyaudiowpatch as pa
    p = pa.PyAudio()
    try:
        wasapi = p.get_host_api_info_by_type(pa.paWASAPI)
        spk = p.get_device_info_by_index(wasapi["defaultOutputDevice"])
        lb = next((d for d in p.get_loopback_device_info_generator() if spk["name"] in d["name"]), None)
        if not lb:
            raise RuntimeError(f"no loopback device for {spk['name']}")
        ch, sr = lb["maxInputChannels"], int(lb["defaultSampleRate"])
        try:
            st = p.open(format=pa.paFloat32, channels=ch, rate=sr, frames_per_buffer=2048, input=True,
                        input_device_index=lb["index"])
        except OSError as e:
            raise RuntimeError(
                f"can't capture '{spk['name']}' ({e}). Bitwig is probably using it exclusively via ASIO/ASIO4ALL. "
                "For live analysis set Bitwig > Settings > Audio > Driver model to 'Windows Audio' (WASAPI shared) "
                "on the same output, or analyze an exported/recorded WAV with source=<file path>.") from None
        frames, t0 = [], time.time()
        while time.time() - t0 < seconds:
            frames.append(np.frombuffer(st.read(2048, exception_on_overflow=False), dtype=np.float32))
        st.close()
        x = np.concatenate(frames).reshape(-1, ch)[:, :2]
        if x.shape[1] == 1:
            x = np.repeat(x, 2, axis=1)
        return x.astype(np.float64), sr, f"live: {spk['name']}"
    finally:
        p.terminate()


def load_file(path: str, start: float = 0.0, seconds: float | None = None):
    if os.path.splitext(path)[1].lower() in (".mp3", ".flac", ".ogg"):      # libsndfile decodes these; WAV/AIFF keep the scipy path
        import soundfile as sf

        with sf.SoundFile(path) as f:
            f.seek(int(start * f.samplerate))
            x = f.read(-1 if seconds is None else int(seconds * f.samplerate), dtype="float64", always_2d=True)
            sr = f.samplerate
        x = np.repeat(x, 2, axis=1) if x.shape[1] == 1 else x[:, :2]
        return x, sr, f"file: {os.path.basename(path)}"
    sr, x = wavfile.read(path)
    if x.dtype.kind == "i":
        x = x / float(np.iinfo(x.dtype).max)
    elif x.dtype.kind == "u":
        x = (x - 128) / 128.0
    x = x.astype(np.float64)
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    x = x[:, :2]
    a = int(start * sr)
    b = len(x) if seconds is None else a + int(seconds * sr)
    return x[a:b], sr, f"file: {os.path.basename(path)}"


# --- Analysis -------------------------------------------------------------------------------------

def _band(x, sr, lo, hi):
    hi = min(hi, sr / 2 * 0.95)
    sos = signal.butter(4, [lo, hi], btype="band", fs=sr, output="sos")
    return signal.sosfilt(sos, x, axis=0)


def k_weight(x, sr):
    """BS.1770 K-weighting, applied to each channel separately (pyloudnorm's filter works on 1-D data)."""
    meter = pyln.Meter(sr)
    y = np.empty_like(x)
    for ch in range(x.shape[1]):
        c = x[:, ch]
        for f in meter._filters.values():
            c = f.apply_filter(c)
        y[:, ch] = c
    return y


def integrated_lufs(x, sr):
    """BS.1770-4 integrated loudness: 400 ms blocks, 75% overlap, -70 LUFS absolute and -10 LU relative gates."""
    _, blocks = loudness_curve(x, sr, 0.4)
    blocks = blocks[np.isfinite(blocks) & (blocks > -70)]
    if not len(blocks):
        return float("-inf")
    rel = 10 * np.log10(np.mean(10 ** (blocks / 10))) - 10
    blocks = blocks[blocks > rel]
    return float(10 * np.log10(np.mean(10 ** (blocks / 10))))


def loudness_curve(x, sr, win, hop=0.1):
    """Ungated sliding loudness (EBU momentary = 0.4 s, short-term = 3 s windows). K-weights once and
    sums 100 ms block energies, so a full song takes milliseconds instead of re-measuring every window."""
    y = k_weight(x, sr)
    blk = int(hop * sr)
    nb = len(y) // blk
    if nb == 0:
        return np.array([]), np.array([])
    energy = (y[:nb * blk] ** 2).reshape(nb, blk, y.shape[1]).mean(axis=1).sum(axis=1)  # per-block, summed channels
    k = max(1, int(round(win / hop)))
    if nb < k:
        return np.array([]), np.array([])
    c = np.concatenate([[0.0], np.cumsum(energy)])
    z = (c[k:] - c[:-k]) / k
    with np.errstate(divide="ignore"):
        lufs = -0.691 + 10 * np.log10(z)
    times = (np.arange(len(z)) + k) * hop
    return times, lufs


def analyze(x, sr, target="streaming"):
    if len(x) < sr * 0.05:
        raise ValueError("need at least 50 ms of audio")
    if float(np.abs(x).max()) < 1e-5:
        raise ValueError("audio is silent (live: is Bitwig playing? file: try another start/section)")
    L, R = x[:, 0], x[:, 1]
    M, S = (L + R) / 2, (L - R) / 2
    # LUFS needs 400 ms blocks; for short one-shots report peaks/stereo only.
    has_lufs = len(x) >= sr * 0.4
    integrated = integrated_lufs(x, sr) if has_lufs else float("nan")

    _, st = loudness_curve(x, sr, 3.0) if len(x) >= 3 * sr else (None, np.array([integrated]))
    _, mo = loudness_curve(x, sr, 0.4) if has_lufs else (None, np.array([]))
    st, mo = st[np.isfinite(st)], mo[np.isfinite(mo)]
    if not len(st):
        st = np.array([integrated])
    # EBU R128 loudness range: short-term values gated at -70 LUFS absolute and -20 LU relative
    gated = st[st > -70]
    if len(gated) > 2:
        rel = 10 * np.log10(np.mean(10 ** (gated / 10))) - 20
        gated = gated[gated > rel]
    lra = float(np.percentile(gated, 95) - np.percentile(gated, 10)) if len(gated) > 2 else 0.0

    peak = float(np.abs(x).max())
    tp = float(np.abs(signal.resample_poly(x, 4, 1, axis=0)).max())
    rms_l, rms_r = np.sqrt(np.mean(L ** 2)), np.sqrt(np.mean(R ** 2))
    rms = np.sqrt(np.mean(x ** 2))
    clipped = int(np.sum(np.abs(x) >= 0.999))

    rms_m, rms_s = np.sqrt(np.mean(M ** 2)), np.sqrt(np.mean(S ** 2))
    corr = float(np.corrcoef(L, R)[0, 1]) if rms_l > 0 and rms_r > 0 else 1.0
    n = int(0.4 * sr)
    win_corr = [np.corrcoef(L[i:i + n], R[i:i + n])[0, 1] for i in range(0, len(L) - n, n)
                if np.std(L[i:i + n]) > 1e-6 and np.std(R[i:i + n]) > 1e-6]
    mono = np.stack([M, M], axis=1)
    mono_lufs = integrated_lufs(mono, sr) if has_lufs else float("nan")

    bands = {}
    total_m = sum(np.mean(_band(M, sr, lo, hi) ** 2) for _, lo, hi in BANDS) or 1e-12
    for name, lo, hi in BANDS:
        bm, bs = _band(M, sr, lo, hi), _band(S, sr, lo, hi)
        em, es = np.mean(bm ** 2), np.mean(bs ** 2)
        bands[name] = {"mid_db": round(db(np.sqrt(em)), 1), "side_db": round(db(np.sqrt(es)), 1),
                       "side_vs_mid_db": round(db(np.sqrt(es)) - db(np.sqrt(em)), 1),
                       "share_pct": round(100 * em / total_m, 1)}

    t_lufs, t_tp = TARGETS.get(target, TARGETS["streaming"])
    m = {
        "loudness": {"integrated_lufs": round(float(integrated), 1), "short_term_max_lufs": round(float(st.max()), 1),
                     "momentary_max_lufs": round(float(mo.max()), 1) if len(mo) else None, "lra_lu": round(lra, 1)},
        "peaks": {"sample_peak_dbfs": round(db(peak), 2), "true_peak_dbtp": round(db(tp), 2),
                  "clipped_samples": clipped},
        "dynamics": {"rms_dbfs": round(db(rms), 1), "crest_factor_db": round(db(peak) - db(rms), 1),
                     "plr_db": round(db(tp) - integrated, 1)},
        "stereo": {"balance_lr_db": round(db(rms_l) - db(rms_r), 2), "correlation": round(corr, 2),
                   "min_correlation_400ms": round(float(min(win_corr)), 2) if win_corr else None,
                   "mid_rms_dbfs": round(db(rms_m), 1), "side_rms_dbfs": round(db(rms_s), 1),
                   "side_vs_mid_db": round(db(rms_s) - db(rms_m), 1),
                   "width_pct": round(100 * rms_s / max(rms_m, 1e-12), 1),
                   "mono_loudness_drop_lu": round(integrated - mono_lufs, 1)},
        "bands": bands,
        "dc_offset": {"left": round(float(L.mean()), 5), "right": round(float(R.mean()), 5)},
        "target": {"name": target, "lufs": t_lufs, "true_peak": t_tp,
                   "gain_to_target_db": round(t_lufs - integrated, 1)},
        "duration_s": round(len(x) / sr, 1), "sample_rate": sr,
    }
    m = _finite(m)
    m["advice"] = advise(m) if has_lufs else ["Clip is under 400 ms: loudness (LUFS) needs a longer section; "
                                              "peaks and stereo/mid-side figures are still valid."]
    return m


def _finite(o):
    """JSON-safe: non-finite numbers become None, and -0.0 becomes 0.0."""
    if isinstance(o, float) and o == 0:
        return 0.0
    if isinstance(o, dict):
        return {k: _finite(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_finite(v) for v in o]
    if isinstance(o, float) and not np.isfinite(o):
        return None
    return o


def advise(m):
    a = []
    L, P, D, S, B, T = m["loudness"], m["peaks"], m["dynamics"], m["stereo"], m["bands"], m["target"]
    g = T["gain_to_target_db"]
    if abs(g) > 1:
        a.append(f"Loudness {L['integrated_lufs']} LUFS vs {T['lufs']} target: {'raise' if g > 0 else 'lower'} "
                 f"by ~{abs(g)} dB (limiter input gain).")
    if P["true_peak_dbtp"] > T["true_peak"]:
        a.append(f"True peak {P['true_peak_dbtp']} dBTP exceeds {T['true_peak']}: lower the limiter ceiling.")
    if P["clipped_samples"]:
        a.append(f"{P['clipped_samples']} clipped samples - reduce gain before the limiter.")
    if D["plr_db"] < 6:
        a.append(f"PLR {D['plr_db']} dB: heavily limited; transients may sound squashed.")
    elif D["plr_db"] > 14 and T["name"] in ("club", "cd", "soundcloud"):
        a.append(f"PLR {D['plr_db']} dB: very dynamic for {T['name']}; more compression/limiting may suit.")
    if S["correlation"] < 0.2:
        a.append(f"Correlation {S['correlation']}: phase-y/wide; check mono compatibility.")
    if S["mono_loudness_drop_lu"] > 3:
        a.append(f"Loses {S['mono_loudness_drop_lu']} LU in mono - narrow wide elements or check phase.")
    if abs(S["balance_lr_db"]) > 1:
        a.append(f"L/R imbalance {S['balance_lr_db']} dB (positive = left louder).")
    low_side = max(B["sub"]["side_vs_mid_db"], B["bass"]["side_vs_mid_db"])
    if low_side > -15:
        a.append(f"Low end has side energy ({low_side} dB vs mid below 250 Hz) - mono the bass "
                 "(Mid-Side Split or a low-cut on the side).")
    if S["width_pct"] < 10:
        a.append(f"Very narrow image (width {S['width_pct']}%) - consider widening highs/mids.")
    elif S["width_pct"] > 80:
        a.append(f"Very wide image (width {S['width_pct']}%) - may collapse in mono.")
    for name, ref in REFERENCE_SHARE.items():
        share = B[name]["share_pct"]
        if share > ref * 2 and share > 10:
            a.append(f"{name} heavy ({share}% of energy vs ~{ref}% in a typical full mix).")
        elif share < ref / 3:
            a.append(f"{name} light ({share}% of energy vs ~{ref}% in a typical full mix).")
    if max(abs(m["dc_offset"]["left"]), abs(m["dc_offset"]["right"])) > 0.005:
        a.append("DC offset present - add a high-pass around 20 Hz.")
    return a or ["Nothing alarming - within normal ranges for the target."]


# --- Dashboard image -------------------------------------------------------------------------------

def render(x, sr, m, title="Master analysis"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    L, R = x[:, 0], x[:, 1]
    M, S = (L + R) / 2, (L - R) / 2
    bg, fg, grid = "#15171c", "#e6e6e6", "#30343c"
    cm, cs, cl, cr = "#4dabf7", "#f783ac", "#63e6be", "#ffd43b"
    plt.rcParams.update({"text.color": fg, "axes.labelcolor": fg, "xtick.color": fg, "ytick.color": fg,
                         "axes.edgecolor": grid, "font.size": 9})
    fig = plt.figure(figsize=(13, 8), facecolor=bg)
    gs = fig.add_gridspec(3, 4, height_ratios=[1.1, 1, 0.9], hspace=0.45, wspace=0.35)

    # Spectrum (mid vs side)
    ax = fig.add_subplot(gs[0, :3], facecolor=bg)
    for sig_, col, lab in ((M, cm, "Mid"), (S, cs, "Side")):
        f, pxx = signal.welch(sig_, sr, nperseg=8192)
        ax.semilogx(f[1:], 10 * np.log10(pxx[1:] + 1e-20), color=col, lw=1.2, label=lab)
    ax.set_xlim(20, sr / 2)
    ax.set_title("Spectrum - mid vs side", color=fg)
    ax.set_xlabel("Hz")
    ax.set_ylabel("dB")
    ax.grid(True, color=grid, which="both", lw=0.5)
    ax.legend(facecolor=bg, edgecolor=grid)

    # Vectorscope / goniometer
    ax = fig.add_subplot(gs[0, 3], facecolor=bg)
    idx = np.linspace(0, len(L) - 1, min(len(L), 20000)).astype(int)
    peak = max(np.abs(x).max(), 1e-9)
    ax.scatter(S[idx] / peak, M[idx] / peak, s=0.5, color=cl, alpha=0.35)
    ax.set_xlim(-1, 1)
    ax.set_ylim(-1, 1)
    ax.set_aspect("equal")
    ax.axhline(0, color=grid, lw=0.5)
    ax.axvline(0, color=grid, lw=0.5)
    ax.set_title(f"Vectorscope  (corr {m['stereo']['correlation']})", color=fg)
    ax.set_xticks([])
    ax.set_yticks([])

    # Short-term loudness over time
    ax = fig.add_subplot(gs[1, :2], facecolor=bg)
    ts, vals = loudness_curve(x, sr, max(0.4, min(3.0, len(x) / sr / 2)))
    keep = np.isfinite(vals)
    ts, vals = ts[keep], vals[keep]
    ax.plot(ts, vals, color=cl, lw=1.4, label="short-term")
    ax.axhline(m["target"]["lufs"], color=cr, ls="--", lw=1, label=f"target {m['target']['lufs']}")
    if m["loudness"]["integrated_lufs"] is not None:
        ax.axhline(m["loudness"]["integrated_lufs"], color=cm, ls=":", lw=1, label="integrated")
    else:
        ax.text(0.5, 0.5, "too short for LUFS", color=fg, ha="center", transform=ax.transAxes)
    ax.set_title("Loudness (LUFS)", color=fg)
    ax.set_xlabel("s")
    ax.grid(True, color=grid, lw=0.5)
    ax.legend(facecolor=bg, edgecolor=grid, fontsize=8)

    # Band mid/side bars
    ax = fig.add_subplot(gs[1, 2:], facecolor=bg)
    names = list(m["bands"])
    xi = np.arange(len(names))
    floor = -90  # bars rise from a floor so taller = louder (silent side content shows as no bar)
    ax.bar(xi - 0.2, [max(0, m["bands"][n]["mid_db"] - floor) for n in names], 0.4, bottom=floor, color=cm, label="Mid")
    ax.bar(xi + 0.2, [max(0, m["bands"][n]["side_db"] - floor) for n in names], 0.4, bottom=floor, color=cs, label="Side")
    ax.set_xticks(xi, names)
    ax.set_title("Mid / side level per band (dBFS RMS)", color=fg)
    ax.grid(True, axis="y", color=grid, lw=0.5)
    ax.legend(facecolor=bg, edgecolor=grid, fontsize=8)
    ax.set_ylim(floor, 0)

    # Numbers panel
    ax = fig.add_subplot(gs[2, :], facecolor=bg)
    ax.axis("off")
    Lo, P, D, St, T = m["loudness"], m["peaks"], m["dynamics"], m["stereo"], m["target"]
    cols = [
        ("LOUDNESS", [f"Integrated  {Lo['integrated_lufs']} LUFS", f"Short-term max  {Lo['short_term_max_lufs']}",
                      f"LRA  {Lo['lra_lu']} LU", f"Target {T['name']}: {T['lufs']} / {T['true_peak']} dBTP"]),
        ("PEAKS & DYNAMICS", [f"True peak  {P['true_peak_dbtp']} dBTP", f"Sample peak  {P['sample_peak_dbfs']} dBFS",
                              f"PLR  {D['plr_db']} dB   Crest  {D['crest_factor_db']} dB",
                              f"Clipped samples  {P['clipped_samples']}"]),
        ("STEREO / M-S", [f"Correlation  {St['correlation']} (min {St['min_correlation_400ms']})",
                          f"Width (S/M)  {St['width_pct']}%   S-M  {St['side_vs_mid_db']} dB",
                          f"Mono loss  {St['mono_loudness_drop_lu']} LU", f"L/R balance  {St['balance_lr_db']} dB"]),
    ]
    for ci, (head, lines) in enumerate(cols):
        ax.text(0.01 + ci * 0.25, 0.95, head, fontsize=10, fontweight="bold", color=cr, va="top", transform=ax.transAxes)
        for li, line in enumerate(lines):
            ax.text(0.01 + ci * 0.25, 0.75 - li * 0.2, line, fontsize=9, va="top", transform=ax.transAxes)
    ax.text(0.76, 0.95, "ADVICE", fontsize=10, fontweight="bold", color=cr, va="top", transform=ax.transAxes)
    for li, line in enumerate(m["advice"][:4]):
        ax.text(0.76, 0.75 - li * 0.2, (line[:58] + "...") if len(line) > 60 else line, fontsize=8, va="top",
                transform=ax.transAxes, wrap=True)
    fig.suptitle(title, color=fg, fontsize=13, fontweight="bold")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=90, facecolor=bg)
    plt.close(fig)
    return buf.getvalue()
