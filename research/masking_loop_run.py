"""Masking report over a looped arranger section: each track is soloed for one whole loop. Writes data/reports/masking_loop.json and restores transport/solo state."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from bwmcp.core.bridge import bw  # noqa: E402
from bwmcp.tools import mixing  # noqa: E402

LOOP_START = 272.0
tracks = [int(a) for a in sys.argv[2:]] or None
seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 83.0
before = bw.call("get_session")
solo0 = [t["index"] for t in before["tracks"] if t["solo"]]
arm0 = [t["index"] for t in before["tracks"] if t["arm"]]
bw.call("set_position", beats=LOOP_START)
time.sleep(0.5)
bw.call("play")
time.sleep(1.5)
try:
    rep = mixing.masking_report(tracks, seconds)
finally:
    bw.call("stop")
    time.sleep(0.5)
    bw.call("set_position", beats=LOOP_START)
out = ROOT / "data" / "reports"
out.mkdir(parents=True, exist_ok=True)
(out / "masking_loop.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
after = bw.call("get_session")
print("solo before", solo0, "after", [t["index"] for t in after["tracks"] if t["solo"]], "arm before", arm0, "after", [t["index"] for t in after["tracks"] if t["arm"]])
print("score", rep.get("score"), "clashes", len(rep.get("clashes", [])))
