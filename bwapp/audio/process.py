"""Sample processing: key detection, and time-stretch / pitch-shift (Rubber Band inside pedalboard) rendered offline."""
from pathlib import Path

import numpy as np
import soundfile as sf
from pedalboard import time_stretch
from scipy import signal

from bwmcp.core import paths
from bwmcp.music import music

OUT = paths.DATA / "samples_processed"


def detect_key(mono, sr):
    """(key name like 'F minor', confidence) from a chroma profile, or (None, 0) for unpitched material."""
    if len(mono) < sr // 2:
        return None, 0.0
    _, _, Z = signal.stft(mono, sr, nperseg=8192, noverlap=4096)
    f = np.linspace(0, sr / 2, Z.shape[0])
    band = (f >= 80) & (f <= 5000)
    power = (np.abs(Z[band]) ** 2).mean(axis=1)
    midi = np.round(69 + 12 * np.log2(np.maximum(f[band], 1) / 440)).astype(int)
    chroma = np.zeros(12)
    for pc, p in zip(midi % 12, power):
        chroma[pc] += p
    if chroma.sum() <= 0:
        return None, 0.0
    best = music.detect_key([{"pitch": pc, "duration": float(w)} for pc, w in enumerate(chroma)])[0]
    return f"{best['key']} {best['scale']}", float(best["confidence"])


def stretch(data, sr, factor=1.0, semitones=0.0):
    """data (n, 2) float32. factor > 1 = faster / shorter (project_bpm / sample_bpm). Pitch shifts independently of speed."""
    if abs(factor - 1) < 1e-4 and abs(semitones) < 1e-4:
        return data
    y = time_stretch(np.ascontiguousarray(data.T), sr, stretch_factor=float(factor), pitch_shift_in_semitones=float(semitones))
    return np.ascontiguousarray(y.T, dtype=np.float32)


def save_copy(data, sr, source, tag):
    """Write the processed audio next to the library data and return its path (what Send to Bitwig loads)."""
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{Path(source).stem}_{tag}.wav"
    sf.write(str(p), data, sr, subtype="PCM_24")
    return p
