import server,time,json
bw=server.bw
a=bw.call("probe_actions"); print(len(a))
open("research/actions.txt","w",encoding="utf8").write("\n".join(a))
for x in a:
    if any(k in x.lower() for k in ("modulat","grid","macro")): print(x)
bw.call("select_track",track_index=2); time.sleep(.7)
bw.call("select_device",device_index=3); time.sleep(.8)
print(bw.call("probe_modsrc"))
