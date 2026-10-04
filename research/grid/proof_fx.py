"""Audio proof for an added module in an effects Grid: Polysynth note -> [Grid variant] -> master recorder -> metrics."""
import time

import lab
from bwmcp.analysis import capture
from proof import metrics

server = lab.server


def render_fx(name, path, note=72, seconds=3.0):
    idx = lab.new_track("ZZ fxproof")
    server.bw.call("select_track", track_index=idx)
    time.sleep(0.5)
    # a sound source on the track: Polysynth (bright, saw-based), then the Grid variant after it
    server.load_preset("Polysynth", idx)
    time.sleep(1.5)
    r = lab.load_and_watch(path, idx, watch=8.0)
    out = {"case": name, **r}
    if r["engine_died_after_s"] is None and r["devices_added"]:
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
