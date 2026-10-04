import sys
from pathlib import Path

_R = Path(__file__).resolve()
while not (_R / "server.py").exists():
    _R = _R.parent
sys.path[:0] = [str(_R), str(_R / "research")]   # repo root (server, bwmcp) and research/ (bwlock, bwformat)
import server,time
bw=server.bw
bw.call("select_track",track_index=2); time.sleep(.7)
bw.call("select_device",device_index=6); time.sleep(.8)  # EQ+ index 6
n=lambda:[x["name"] for x in bw.call("list_devices")["devices"]]
print(len(n()))
for u in ["a9ffacb5-33e9-4fc7-8621-b1af31e410ef","ca8cc421-bcbc-44d9-8ef3-6e570e528d2b","dcacb71b-0f1a-4493-8916-bd460eee71d5"]:
    print(u,bw.call("probe_insert_uuid",uuid=u)); time.sleep(1.5); print(len(n()), n()[-8:])
