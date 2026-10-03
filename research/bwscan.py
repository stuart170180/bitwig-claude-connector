"""Scan Bitwig preset files (version 0002 = plain). Prints device name/id and referenced modulators/modules."""
import glob,re,sys,struct
def meta(b):
    n=int(b[0x10:0x18],16)  # meta length hex
    return b[0x2a:0x2a+n]
def strings(m):
    return [s.decode('utf8','replace') for s in re.findall(rb'\x08\x00\x00\x00.([\x20-\x7e]*)',m)]
if __name__=="__main__":
    roots=[r"C:\Program Files\Bitwig Studio\Library",r"C:\Users\stuar\AppData\Local\Bitwig Studio\installed-packages",r"C:\Users\stuar\Documents\Bitwig Studio"]
    for r in roots:
        for f in glob.glob(r+r"\**\*.bw*",recursive=True):
            if f.endswith(('.bwproject','.bwclip')):continue
            b=open(f,'rb').read()
            if b[:12]!=b'BtWg00030002': continue
            m=meta(b)
            mm=re.search(rb'referenced_module_ids\x19\x00\x00\x00(....)',m); mo=re.search(rb'referenced_modulator_ids\x19\x00\x00\x00(....)',m)
            nm=struct.unpack('>I',mm.group(1))[0] if mm else 0; no=struct.unpack('>I',mo.group(1))[0] if mo else 0
            if nm or no:
                dn=re.search(rb'device_name\x08\x00\x00\x00.([^\x00]*)',m)
                print(nm,no,dn.group(1).decode() if dn else '?',f)
