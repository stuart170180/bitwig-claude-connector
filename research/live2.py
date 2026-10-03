import server,time,json
bw=server.bw
L=r"C:\Program Files\Bitwig Studio\Library"
T=2
bw.call("select_track",track_index=T); time.sleep(.7)
bw.call("set_track_name",track_index=T,name="ZZ research") 
for name in ["Poly Grid","Polymer","FX Grid"]:
    bw.call("insert_file",path=L+"\devices\\"+name+".bwdevice"); time.sleep(1.5)
print(bw.call("list_devices"))
for i in range(3):
    bw.call("select_device",device_index=i); time.sleep(.8)
    info=bw.call("deep_info",limit=300)
    print(info["device"],"slots",info["slots"],"layers",info["layers"],"nparams",info["param_count"])
    for p in info["params"]: print("   ",p["id"],"|",p["name"],"|",round(p["value"],3) if p["value"] is not None else None,"|",p["display"])
