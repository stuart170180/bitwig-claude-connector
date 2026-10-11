"""Decode a sample to float32 stereo (soundfile reads wav / aiff / flac / ogg / mp3) and make waveform peaks."""
from pathlib import Path

import numpy as np
import soundfile as sf

EXTS = {".wav", ".aif", ".aiff", ".flac", ".ogg", ".mp3"}


def load(path):
    data, sr = sf.read(str(path), always_2d=True, dtype="float32")
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    return data[:, :2], int(sr)


def peaks(mono, columns):
    """(columns, 2) min / max per column for drawing."""
    n = len(mono)
    if n == 0 or columns <= 0:
        return np.zeros((0, 2), np.float32)
    edges = np.linspace(0, n, columns + 1).astype(int)
    out = np.zeros((columns, 2), np.float32)
    for i in range(columns):
        seg = mono[edges[i]:max(edges[i + 1], edges[i] + 1)]
        out[i] = (seg.min(), seg.max())
    return out


def scan_folder(folder, limit=5000):
    """Audio files under a folder (recursive), capped so a huge library does not freeze the list."""
    found = []
    for p in Path(folder).rglob("*"):
        if p.suffix.lower() in EXTS and p.is_file():
            found.append(p)
            if len(found) >= limit:
                break
    return sorted(found, key=lambda p: p.name.lower())
