import glob,re,json,os
m={}
for f in glob.glob(r"C:\Program Files\Bitwig Studio\Library\device-settings\*\Default.bwpreset"):
    b=open(f,'rb').read(); n=int(b[0x10:0x18],16); meta=b[0x2a:0x2a+n]
    d=re.search(rb'device_name\x08\x00\x00\x00.([^\x00]*)',meta); m[os.path.basename(os.path.dirname(f))]=d.group(1).decode() if d else '?'
json.dump(m,open("device_uuids.json","w"),indent=0); print(len(m))
