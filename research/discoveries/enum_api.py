import zipfile,re,struct,json,glob,sys
jar=r"C:\Program Files\Bitwig Studio\bin\bitwig.jar"
z=zipfile.ZipFile(jar)
names=[n for n in z.namelist() if n.startswith("com/bitwig/extension/controller/api/") and n.endswith(".class")]
def parse(b):
    p=8;n=struct.unpack(">H",b[p:p+2])[0];p+=2;cp=[None]*n;i=1
    while i<n:
        t=b[p];p+=1
        if t==1:
            l=struct.unpack(">H",b[p:p+2])[0];cp[i]=b[p+2:p+2+l].decode("utf8","replace");p+=2+l
        elif t in(3,4):p+=4
        elif t in(5,6):p+=8;i+=1
        elif t in(7,8,16,19,20):cp[i]=("r",struct.unpack(">H",b[p:p+2])[0]);p+=2
        elif t in(9,10,11,12,17,18):p+=4
        elif t==15:p+=3
        i+=1
    acc,this,sup=struct.unpack(">HHH",b[p:p+6]);p+=6
    ic=struct.unpack(">H",b[p:p+2])[0];p+=2+2*ic
    def s(i):
        v=cp[i];return cp[v[1]] if isinstance(v,tuple) else v
    def members():
        nonlocal p
        c=struct.unpack(">H",b[p:p+2])[0];p+=2;out=[]
        for _ in range(c):
            a,ni,di,ac=struct.unpack(">HHHH",b[p:p+8]);p+=8
            out.append((cp[ni],cp[di]))
            for _ in range(ac):
                an,al=struct.unpack(">HI",b[p:p+6]);p+=6+al
        return out
    f=members();m=members()
    return s(this),acc,f,m
api={}
for n in names:
    try:
        c,acc,f,m=parse(z.read(n))
        api[c.split("/")[-1]]={"iface":bool(acc&0x200),"methods":sorted(set(x[0] for x in m if x[0] not in("<init>","<clinit>")))}
    except Exception as e: print("err",n,e)
json.dump(api,open("api_surface.json","w"),indent=0)
print(len(api),"classes",sum(len(v["methods"]) for v in api.values()),"methods")
# used names in scripts
src="".join(open(f,encoding="utf8",errors="ignore").read() for f in glob.glob("../../bitwig_script/*.js"))
used=set(re.findall(r"\b([A-Za-z_]\w*)\(",src))
unused={}
for c,v in api.items():
    u=[m for m in v["methods"] if m not in used]
    if u: unused[c]=u
json.dump(unused,open("api_unused.json","w"),indent=0)
print(len(unused),"classes with unused;",sum(len(v) for v in unused.values()))
