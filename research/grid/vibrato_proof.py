"""Factory Polymer's vibrato LFO is mapped to PITCH_TRANSPOSE. Change that mapping's amount (a same-length edit) and measure the pitch wobble."""
import glob
import sys
import time
from pathlib import Path

import numpy as np

_R = Path(__file__).resolve()
while not (_R / "server.py").exists():
    _R = _R.parent
sys.path[:0] = [str(_R), str(_R / "research" / "grid")]
import server as s  # noqa: E402
from bwmcp.analysis import capture  # noqa: E402
from bwmcp.devices import gridedit as ge  # noqa: E402
from bwmcp.music import pitch  # noqa: E402

D = "C:/Program Files/Bitwig Studio/Library/device-settings/"
OUT = _R / "data" / "patched_presets"


def variant(amount):
    f = ge.load(glob.glob(D + "8f58138b*/Default.bwpreset")[0])
    if amount is not None:
        ge.set_mapping_amount(f, "0", "CONTENTS/PITCH_TRANSPOSE", amount)
    p = OUT / f"vib_{'factory' if amount is None else amount}.bwpreset"
    ge.save(f, p)
    return p


def measure(preset, label):
    n0 = len(s.bw.call("get_session")["tracks"])
    i = s.create_track("instrument", name="ZZ vib")["index"]
    s.bw.call("select_track", track_index=i)
    time.sleep(0.6)
    s.bw.call("insert_file", path=str(preset))
    time.sleep(3)
    s.write_notes(i, 0, [{"pitch": 57, "start": 0, "duration": 16, "velocity": 100}], length_beats=16)
    time.sleep(1)
    s.launch(i, 0)
    time.sleep(0.5)
    x, sr, _ = capture.capture_recorder(8.0)
    s.stop_clips()
    time.sleep(0.8)
    s.transport("stop")
    t, f0, cl = pitch.track(x[int(3 * sr):], sr)                         # skip the vibrato's delay and fade-in
    ok = np.isfinite(f0)
    cents = 1200 * np.log2(f0[ok] / np.nanmedian(f0[ok]))
    print(label, "pitch wobble std %.1f cents, range %.0f cents, voiced %d%%" % (cents.std(), np.ptp(cents), 100 * ok.mean()), flush=True)
    s.delete_track(i)
    time.sleep(1.2)
    assert len(s.bw.call("get_session")["tracks"]) == n0


if __name__ == "__main__":
    for amount in (0.0, None, 3.0):
        measure(variant(amount), "mapping amount " + ("factory 0.5" if amount is None else str(amount)))
