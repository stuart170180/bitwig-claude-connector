import sys
from pathlib import Path

_R = Path(__file__).resolve()
while not (_R / "server.py").exists():
    _R = _R.parent
sys.path[:0] = [str(_R), str(_R / "research")]   # repo root (server, bwmcp) and research/ (bwlock, bwformat)
import server,time,json
bw=server.bw
L="C:\Program Files\Bitwig Studio\Library\\"
T=2
bw.call("select_track",track_index=T); time.sleep(.7)
for name in ["Polysynth","Sampler","Filter+","EQ+","FX Layer"]:
    bw.call("insert_file",path=L+"devices\\"+name+".bwdevice"); time.sleep(1.5)
d=bw.call("list_devices")["devices"]; print([x["name"] for x in d])
for x in d[3:]:
    bw.call("select_device",device_index=x["index"]); time.sleep(.8)
    i=bw.call("deep_info",limit=0); print(x["name"],"slots",i["slots"],"layers",i["layers"],"n",i["param_count"])
# try modulator file insertion on Polysynth (index 3)
bw.call("select_device",device_index=3); time.sleep(.8)
for where in ["after","slot_end"]:
    try:
        r=bw.call("deep_insert_file",where=where,path=L+"modulators\LFO.bwmodulator"); print(where,r)
    except Exception as e: print(where,"ERR",e)
    time.sleep(1.5)
print([x["name"] for x in bw.call("list_devices")["devices"]])
i=bw.call("deep_info",limit=300); print(i["device"],i["param_count"],[p["id"] for p in i["params"]][:60])
