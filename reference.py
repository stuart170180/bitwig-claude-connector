"""Compare a mix against a reference track: metric differences, matching suggestions, overlay chart."""
import io

import numpy as np
from scipy import signal


def _spectrum(x, sr, normalize=True):
    """Welch spectrum smoothed onto 240 log-spaced bins (~1/24 octave); optionally normalized to equal total
    power so two tracks compare on tonal balance rather than loudness."""
    f, p = signal.welch(x, sr, nperseg=8192)
    edges = np.geomspace(20, min(20000, sr / 2), 241)
    centers, vals = [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (f >= lo) & (f < hi)
        if sel.any():
            centers.append(np.sqrt(lo * hi))
            vals.append(p[sel].mean())
    vals = np.array(vals)
    if normalize:
        vals = vals / vals.sum()
    return np.array(centers), 10 * np.log10(vals + 1e-30)


def _sub(x, y):
    return None if x is None or y is None else round(x - y, 1)


def compare(a, b):
    """Differences (mix minus reference) and matching suggestions from two mastering.analyze() results."""
    d = {
        "loudness_lu": _sub(a["loudness"]["integrated_lufs"], b["loudness"]["integrated_lufs"]),
        "true_peak_db": _sub(a["peaks"]["true_peak_dbtp"], b["peaks"]["true_peak_dbtp"]),
        "plr_db": _sub(a["dynamics"]["plr_db"], b["dynamics"]["plr_db"]),
        "lra_lu": _sub(a["loudness"]["lra_lu"], b["loudness"]["lra_lu"]),
        "width_pct": _sub(a["stereo"]["width_pct"], b["stereo"]["width_pct"]),
        "correlation": _sub(a["stereo"]["correlation"], b["stereo"]["correlation"]),
        "band_share_pct": {k: _sub(a["bands"][k]["share_pct"], b["bands"][k]["share_pct"]) for k in a["bands"]},
        "band_side_vs_mid_db": {k: _sub(a["bands"][k]["side_vs_mid_db"], b["bands"][k]["side_vs_mid_db"])
                                for k in a["bands"]},
    }
    tips = []
    if d["loudness_lu"] is not None and abs(d["loudness_lu"]) > 1:
        tips.append(f"{'Louder' if d['loudness_lu'] > 0 else 'Quieter'} than the reference by {abs(d['loudness_lu'])} LU"
                    f" - change limiter gain by {-d['loudness_lu']:+.1f} dB to match.")
    if d["plr_db"] is not None and abs(d["plr_db"]) > 2:
        tips.append(f"{'More dynamic' if d['plr_db'] > 0 else 'More compressed'} than the reference "
                    f"(PLR {d['plr_db']:+} dB).")
    if d["width_pct"] is not None and abs(d["width_pct"]) > 10:
        tips.append(f"{'Wider' if d['width_pct'] > 0 else 'Narrower'} than the reference ({d['width_pct']:+} width "
                    f"points) - try Tool St. Width around {max(0, round(100 - d['width_pct']))}%.")
    for band, diff in d["band_share_pct"].items():
        if diff is not None and abs(diff) > 6:
            tips.append(f"{band}: {'more' if diff > 0 else 'less'} energy than the reference ({diff:+} pts)"
                        f" - {'cut' if diff > 0 else 'boost'} that region a little.")
    return {"difference_mix_minus_reference": d, "suggestions": tips or ["Very close to the reference."]}


def render(xa, sr_a, ma, xb, sr_b, mb, name_a="Mix", name_b="Reference"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    bg, fg, grid, ca, cb = "#15171c", "#e6e6e6", "#30343c", "#4dabf7", "#ffa94d"
    plt.rcParams.update({"text.color": fg, "axes.labelcolor": fg, "xtick.color": fg, "ytick.color": fg,
                         "axes.edgecolor": grid, "font.size": 9})
    fig, axes = plt.subplots(2, 2, figsize=(13, 7.5), facecolor=bg)
    for ax in axes.flat:
        ax.set_facecolor(bg)
        ax.grid(True, color=grid, lw=0.5, which="both")
    # Level-matched spectra, so tonal balance rather than loudness is compared.
    ax = axes[0, 0]
    for x, sr, col, nm in ((xa, sr_a, ca, name_a), (xb, sr_b, cb, name_b)):
        f, p = _spectrum(x.mean(axis=1), sr)
        ax.semilogx(f, p, color=col, lw=1.4, label=nm)
    ax.set_ylabel("dB (equal total power)")
    ax.set_xlim(20, 20000)
    ax.set_title("Tonal balance (level-matched)", color=fg)
    ax.legend(facecolor=bg, edgecolor=grid)
    ax = axes[0, 1]
    for x, sr, col, nm in ((xa, sr_a, ca, name_a), (xb, sr_b, cb, name_b)):
        # side relative to each track's own mid, so a quieter track isn't simply "less wide"
        f, side = _spectrum((x[:, 0] - x[:, 1]) / 2, sr, normalize=False)
        _, mid = _spectrum((x[:, 0] + x[:, 1]) / 2, sr, normalize=False)
        ax.semilogx(f, side - mid, color=col, lw=1.4, label=nm)
    ax.set_ylabel("side minus mid (dB)")
    ax.set_xlim(20, 20000)
    ax.set_title("Stereo width by frequency (side vs mid)", color=fg)
    ax.legend(facecolor=bg, edgecolor=grid)
    ax = axes[1, 0]
    names = list(ma["bands"])
    xi = np.arange(len(names))
    ax.bar(xi - 0.2, [ma["bands"][n]["share_pct"] for n in names], 0.4, color=ca, label=name_a)
    ax.bar(xi + 0.2, [mb["bands"][n]["share_pct"] for n in names], 0.4, color=cb, label=name_b)
    ax.set_xticks(xi, names)
    ax.set_title("Energy share per band (%)", color=fg)
    ax.legend(facecolor=bg, edgecolor=grid)
    ax = axes[1, 1]
    ax.axis("off")
    rows = [("Integrated LUFS", "loudness", "integrated_lufs"), ("True peak dBTP", "peaks", "true_peak_dbtp"),
            ("PLR dB", "dynamics", "plr_db"), ("LRA LU", "loudness", "lra_lu"), ("Width %", "stereo", "width_pct"),
            ("Correlation", "stereo", "correlation"), ("Mono loss LU", "stereo", "mono_loudness_drop_lu")]
    ax.text(0.0, 0.95, f"{'':18s}{name_a[:12]:>14s}{name_b[:12]:>14s}", family="monospace", transform=ax.transAxes)
    for i, (label, g, k) in enumerate(rows):
        ax.text(0.0, 0.85 - i * 0.1, f"{label:18s}{str(ma[g][k]):>14s}{str(mb[g][k]):>14s}", family="monospace",
                transform=ax.transAxes)
    fig.suptitle(f"{name_a} vs {name_b}", color=fg, fontsize=13, fontweight="bold")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=90, facecolor=bg)
    plt.close(fig)
    return buf.getvalue()
