import sys
from pathlib import Path

_R = Path(__file__).resolve()
while not (_R / "server.py").exists():
    _R = _R.parent
sys.path[:0] = [str(_R), str(_R / "research")]   # repo root (server, bwmcp) and research/ (bwlock, bwformat)
import server,time,struct,os
bw=server.bw
src=r"C:\Program Files\Bitwig Studio\Library\device-settings\a33bba66-8cd4-4f89-aee5-68bf67f70a54\Default.bwpreset"
S=os.path.abspath("research/scratch")
b=bytearray(open(src,'rb').read())
open(S+r"\pg_copy.bwpreset","wb").write(b)
i=b.rfind(b'\x08\x00\x00\x00\x0fPITCH_TRANSPOSE')+len(b'\x08\x00\x00\x00\x0fPITCH_TRANSPOSE')+5
assert b[i-1]==7
print(b[i-1:i+8].hex())
b[i:i+8]=struct.pack(">d",7.0)
open(S+r"\pg_patched.bwpreset","wb").write(b)
T=2; bw.call("select_track",track_index=T); time.sleep(.7)
n0=len(bw.call("list_devices")["devices"])
for f in ["pg_patched"]:
    bw.call("insert_file",path=S+"\\"+f+".bwpreset"); time.sleep(2)
d=bw.call("list_devices")["devices"]; print([x["name"] for x in d])
for x in d[n0:]:
    bw.call("select_device",device_index=x["index"]); time.sleep(.8)
    i=bw.call("deep_info",limit=3); print(x["name"],x["preset"],[(p["id"],p["value"],p["display"]) for p in i["params"]])
