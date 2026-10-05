"""Audition Spire presets by measurement: load each preset into a Spire track, play a held note, capture the master through the BW Remote VST3 and print level/spectrum.
usage: python research/spire_audition.py <track_index> <pitch> "<preset query>" [more queries...]   (project must have BW Remote on the master and Spire-1.5 on the track)"""
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bwmcp.analysis import vstfeed  # noqa: E402
from bwmcp.core.bridge import bw  # noqa: E402
from bwmcp.devices import spire  # noqa: E402
from bwmcp.core.bridge import deep  # noqa: E402
from bwmcp.tools import clips, tracks  # noqa: E402

SLOT = 7


def audition(ti, pitch, hit, seconds=2.2):
    spire.apply(bw, deep, ti, 0, hit["path"])
    time.sleep(0.4)
    clips.write_notes(ti, SLOT, [{"pitch": pitch, "start": 0, "duration": 6, "velocity": 100}], 8, "audition")
    time.sleep(0.8)
    tracks.launch(ti, SLOT)
    time.sleep(1.0)
    x, sr = vstfeed.read_audio(seconds, wait=True)
    bw.call("stop")
    tracks.stop_clips()
    m = x.mean(axis=1)
    rms = 20 * np.log10(np.sqrt((m ** 2).mean()) + 1e-9)
    s = np.abs(np.fft.rfft(m * np.hanning(len(m))))
    f = np.fft.rfftfreq(len(m), 1 / sr)
    cen = float((s * f).sum() / (s.sum() + 1e-9))
    low = float(s[f < 150].sum() / (s.sum() + 1e-9) * 100)
    return round(float(rms), 1), round(float(np.abs(m).max()), 2), round(cen), round(low)


if __name__ == "__main__":
    ti, pitch = int(sys.argv[1]), int(sys.argv[2])
    vstfeed.feed()
    time.sleep(1.5)
    for q in sys.argv[3:]:
        hits = spire.search(q, None, 1)
        if not hits:
            print(q, "-> no preset")
            continue
        h = hits[0]
        try:
            print(f"{h['bank'][:22]:22} | {h['name'][:30]:30} rms/peak/centroid/low%:", audition(ti, pitch, h))
        except Exception as e:  # noqa: BLE001
            print(h["name"], "ERR", str(e)[:100])
    try:
        clips.delete_clip(ti, SLOT)
    except Exception:
        pass
