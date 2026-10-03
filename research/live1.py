import server,time,json
bw=server.bw
L=r"C:\Program Files\Bitwig Studio\Library"
bw.call("create_instrument_track",position=-1); time.sleep(0.8)
s=bw.call("get_session"); idx=len(s["tracks"])-1; print("scratch idx",idx,[t["name"] for t in s["tracks"]])
bw.call("set_track_name",track_index=idx,name="ZZ research") if False else None
import json
print([c for c in dir(bw)][:5])
