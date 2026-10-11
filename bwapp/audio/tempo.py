"""BPM and length-in-bars for a sample: onset-envelope autocorrelation (scipy only), then a whole-bars sanity check for loops."""
import numpy as np
from scipy import signal

HOP = 512


def onset_envelope(mono, sr):
    f, t, Z = signal.stft(mono, sr, nperseg=1024, noverlap=1024 - HOP)
    mag = np.log1p(np.abs(Z) * 10)
    flux = np.maximum(np.diff(mag, axis=1), 0).sum(axis=0)
    flux -= np.convolve(flux, np.ones(21) / 21, mode="same")
    return np.maximum(flux, 0), sr / HOP


def estimate_bpm(mono, sr, lo=70.0, hi=180.0):
    """(bpm, confidence 0..1) or (None, 0) for one-shots / too little rhythm."""
    if len(mono) < sr * 1.0:
        return None, 0.0
    env, fps = onset_envelope(mono, sr)
    if env.max() <= 1e-6:
        return None, 0.0
    ac = signal.correlate(env, env, mode="full")[len(env) - 1:]
    ac /= ac[0] + 1e-12
    lags = np.arange(len(ac))
    bpm = 60.0 * fps / np.maximum(lags, 1)
    ok = (bpm >= lo) & (bpm <= hi)
    if not ok.any():
        return None, 0.0
    cand = np.where(ok)[0]
    score = ac[cand] * (1 + 0.15 * np.exp(-0.5 * ((bpm[cand] - 124) / 40) ** 2))   # mild preference for common dance tempos
    best = cand[int(np.argmax(score))]
    half = best // 2                                           # twice the tempo = half the lag: take it when it is nearly as strong
    if half > 2:
        near = half - 1 + int(np.argmax(ac[half - 1:half + 2]))
        if bpm[near] <= hi and ac[near] > 0.7 * ac[best]:
            best = near
    lag = float(best)
    if 1 < best < len(ac) - 1:                                 # parabolic peak interpolation: finer than one onset-frame lag
        a, b, c = ac[best - 1], ac[best], ac[best + 1]
        d = a - 2 * b + c
        if d != 0:
            lag += 0.5 * (a - c) / d
    return float(60.0 * fps / lag), float(max(0.0, min(1.0, ac[best])))


def analyse(mono, sr, beats_per_bar=4):
    """dict: seconds, bpm, bars, confidence, method. Loops that are a whole number of bars use the length to fix the tempo."""
    dur = len(mono) / sr
    est, conf = estimate_bpm(mono, sr)
    out = {"seconds": dur, "bpm": est, "bars": None, "confidence": conf, "method": "onsets"}
    if est is None:
        return out
    best = None
    for bars in (0.5, 1, 2, 4, 8, 16, 32, 64):
        bpm = 60.0 * beats_per_bar * bars / dur
        if 70 <= bpm <= 180 and (best is None or abs(bpm - est) < abs(best[0] - est)):
            best = (bpm, bars)
    if best and abs(best[0] - est) / est < 0.08:
        out.update(bpm=best[0], bars=best[1], method="whole bars", confidence=max(conf, 0.8))
    else:
        out["bars"] = dur * est / (60.0 * beats_per_bar)
    return out
