"""Lab for the Grid / modulator experiments: build edited presets, load them on a fresh scratch track, watch the audio engine,
recover if it dies, clean up. Run from anywhere. Needs Bitwig open; a crash stops the audio engine until this recovers it."""
import glob
import os
import sys
import time
from pathlib import Path

_R = Path(__file__).resolve()
while not (_R / "server.py").exists():
    _R = _R.parent
sys.path[:0] = [str(_R), str(_R / "research")]

import bwformat as bw  # noqa: E402
import server  # noqa: E402

bwc = server.bw
OUT = _R / "research" / "grid" / "out"
OUT.mkdir(parents=True, exist_ok=True)
DS = "C:/Program Files/Bitwig Studio/Library/device-settings/"
LOG = os.path.expandvars(r"%LOCALAPPDATA%\Bitwig Studio\BitwigStudio.log")
BAD = ("Communications with engine lost", "Error launching or running engine", "fatal", "access violation", "0xC0000005")


def ds(prefix):
    return glob.glob(DS + prefix + "*/Default.bwpreset")[0]


def log_size():
    return os.path.getsize(LOG)


def log_since(pos):
    with open(LOG, "rb") as fh:
        fh.seek(pos)
        t = fh.read().decode("utf8", "replace")
    return [ln for ln in t.splitlines() if "isEngineReadyChanged" not in ln]


def engine_active():
    try:
        return bool(bwc.call("engine", action="state")["active"])
    except Exception:
        return None          # script not reachable


def track_names():
    return [t["name"] for t in bwc.call("get_session")["tracks"]]


def new_track(name="ZZ grid", kind="instrument"):
    n = len(track_names())
    bwc.call("create_instrument_track" if kind == "instrument" else "create_audio_track", position=-1)
    time.sleep(0.6)
    bwc.call("set_track_name", track_index=n, name=name)
    time.sleep(0.3)
    bwc.call("select_track", track_index=n)
    time.sleep(0.6)
    return n


def delete_scratch():
    """Delete every track whose name starts with ZZ (highest first)."""
    for _ in range(10):
        z = [i for i, n in enumerate(track_names()) if n.startswith("ZZ")]
        if not z:
            return
        bwc.call("delete_track", track_index=z[-1])
        time.sleep(0.8)


def recover(timeout=90):
    """Re-activate the audio engine after a crash (script command if reachable, else click Bitwig's button); returns seconds, or None."""
    from bwmcp.control import uiclick
    t0 = time.time()
    while time.time() - t0 < timeout:
        if engine_active():
            return round(time.time() - t0, 1)
        if engine_active() is None:
            uiclick.reactivate_engine()            # script is disconnected while the engine is down
        else:
            try:
                bwc.call("engine", action="activate")
            except Exception:
                pass
        time.sleep(2.5)
    return None


def load_and_watch(path, idx, watch=10.0):
    """Load a preset file on track idx, watch the engine for `watch` seconds. Returns a result dict."""
    pos = log_size()
    bwc.call("select_track", track_index=idx)
    time.sleep(0.5)
    before = len(bwc.call("list_devices")["devices"])
    bwc.call("insert_file", path=str(path))
    t0, died_at = time.time(), None
    while time.time() - t0 < watch:
        time.sleep(0.4)
        if engine_active() is not True:
            died_at = round(time.time() - t0, 1)
            break
    lines = log_since(pos)
    bad = [ln for ln in lines if any(b.lower() in ln.lower() for b in BAD)]
    loaded = None
    try:
        loaded = len(bwc.call("list_devices")["devices"]) - before
    except Exception:
        pass
    return {"file": Path(path).name, "devices_added": loaded, "engine_died_after_s": died_at, "log_problems": bad[:3],
            "load_errors": [ln for ln in lines if "Error loading" in ln][:2]}


def case(name, path, watch=10.0):
    """One fresh track, one load, recover and clean up. Prints and returns the result."""
    idx = new_track()
    try:
        r = load_and_watch(path, idx, watch)
    except Exception as e:                       # the script vanished mid-call: the engine died
        r = {"file": Path(path).name, "devices_added": None, "engine_died_after_s": 0.0, "log_problems": [str(e)[:80]], "load_errors": []}
    r["case"] = name
    if r["engine_died_after_s"] is not None or engine_active() is not True:
        r["engine_died_after_s"] = r["engine_died_after_s"] if r["engine_died_after_s"] is not None else 0.0
        r["recovered_in_s"] = recover()
    time.sleep(1.0)
    delete_scratch()
    time.sleep(1.0)
    r["tracks_after"] = track_names()
    print(r, flush=True)
    return r
