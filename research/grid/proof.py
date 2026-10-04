"""Audio proof: load a Polymer variant on a fresh track, play one sustained note, record the master, measure it."""
import time

import numpy as np

import lab
from bwmcp.analysis import capture


def metrics(x, sr):
    m = x.mean(axis=1) if x.ndim == 2 else x
    m = m[int(0.3 * sr):]                                # skip the attack / start-up
    rms = float(np.sqrt(np.mean(m ** 2)) + 1e-12)
    spec = np.abs(np.fft.rfft(m * np.hanning(len(m)))) ** 2
    f = np.fft.rfftfreq(len(m), 1 / sr)
    tot = float(spec.sum() + 1e-18)
    return {"rms_db": round(20 * np.log10(rms), 1), "peak_db": round(20 * np.log10(np.abs(m).max() + 1e-12), 1),
            "centroid_hz": round(float((f * spec).sum() / tot)),
            "energy_above_1k_pct": round(100 * float(spec[f > 1000].sum()) / tot, 2)}


def render(name, path, note=60, seconds=3.0):
    idx = lab.new_track("ZZ proof")
    r = lab.load_and_watch(path, idx, watch=8.0)
    out = {"case": name, **r}
    if r["engine_died_after_s"] is None and r["devices_added"]:
        server = lab.server
        server.write_notes(idx, 0, [{"pitch": note, "start": 0, "duration": 8, "velocity": 110}], length_beats=8)
        time.sleep(1.0)
        server.launch(idx, 0)
        time.sleep(0.8)
        try:
            x, sr, _ = capture.capture_recorder(seconds)
            out["audio"] = metrics(x, sr)
        finally:
            server.stop_clips()
            time.sleep(0.5)
    elif r["engine_died_after_s"] is not None:
        out["recovered_in_s"] = lab.recover()
    lab.delete_scratch()
    time.sleep(1.0)
    out["tracks_after"] = lab.track_names()
    print(out, flush=True)
    return out
