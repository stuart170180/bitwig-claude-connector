"""Capture what Bitwig is playing. Preferred route: Bitwig's own master recorder (exact, any audio driver, no speakers needed).
Fallback: Windows loopback (WASAPI). Both return (samples, sample_rate, label) like mastering.capture_loopback."""
import glob
import os
import time

from bwmcp.analysis import mastering
from bwmcp.core import paths
from bwmcp.core.bridge import bw


def _recording_dirs():
    local = os.environ.get("LOCALAPPDATA", "")
    return [os.path.join(local, "Bitwig Studio", "temp-projects", "*", "master-recordings"),
            str(paths.documents_dir() / "Bitwig Studio" / "Projects" / "*" / "master-recordings")]


def find_recording(since: float):
    """Newest master-recording WAV written after `since` (epoch seconds), or None."""
    found = [f for pat in _recording_dirs() for f in glob.glob(os.path.join(pat, "*.wav")) if os.path.getmtime(f) >= since - 1]
    return max(found, key=os.path.getmtime) if found else None


def capture_recorder(seconds: float, keep_file: bool = False):
    t0 = time.time()
    bw.call("rec_start")
    try:
        time.sleep(seconds)
    finally:
        bw.call("rec_stop")
    path = None
    for _ in range(30):                     # the file appears a moment after stop
        time.sleep(0.2)
        path = find_recording(t0)
        if path and os.path.getsize(path) > 1000:
            time.sleep(0.3)
            break
    if not path:
        raise RuntimeError("the master recorder did not produce a file")
    x, sr, _ = mastering.load_file(path)
    if not keep_file:
        try:
            os.remove(path)                 # these pile up (gigabytes); ours is only a capture buffer
        except OSError:
            pass
    return x, sr, f"master recorder ({seconds:g} s)"


def capture_live(seconds: float, prefer: str = "auto"):
    """prefer: auto (recorder, then loopback), recorder, loopback."""
    if prefer not in ("auto", "recorder", "loopback"):
        raise ValueError("prefer must be auto, recorder or loopback")
    if prefer in ("auto", "recorder"):
        try:
            return capture_recorder(seconds)
        except Exception as e:
            if prefer == "recorder":
                raise
            err = e
    try:
        return mastering.capture_loopback(seconds)
    except Exception as e2:
        raise RuntimeError(f"master recorder failed ({err if prefer == 'auto' else ''}); loopback failed ({e2})") from None
