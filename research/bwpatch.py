"""Prototype: read/patch parameter values inside a Bitwig version-0002 .bwpreset (plain container) WITHOUT changing
any length, and list what a preset contains. Always writes a COPY.
  python bwpatch.py info  <file.bwpreset>
  python bwpatch.py set   <in.bwpreset> <out.bwpreset> <PARAM_NAME> <value> [occurrence=-1]
Param values are stored as: [string 08 len name][00 00 01 36][07 + 8-byte big-endian double]  (field 0x136 = value).
This only works for doubles stored that way (verified for device-level params, e.g. PITCH_TRANSPOSE, in real units)."""
import re, struct, sys

def split(b):
    assert b[:12] == b"BtWg00030002", "not a plain (v2) preset; v4 files in Library/devices|modulators|modules are scrambled"
    return b[:0x2a], b[0x2a:]

def info(path):
    b = open(path, "rb").read()
    meta = b[0x2a:0x2a + int(b[0x10:0x18], 16)]
    strs = re.findall(rb"\x08\x00\x00\x00.([\x20-\x7e]*)", b)
    out = {"size": len(b), "device_name": None}
    m = re.search(rb"device_name\x08\x00\x00\x00.([^\x00]*)", meta)
    if m: out["device_name"] = m.group(1).decode()
    out["strings"] = [s.decode() for s in strs]
    out["params"] = []
    for m in re.finditer(rb"\x08\x00\x00\x00([\x01-\x7f])([A-Za-z0-9_/ >+.-]+)\x00\x00\x01\x36\x07(.{8})", b, re.S):
        n = m.group(2)[: m.group(1)[0] - 0]
        out["params"].append((m.group(2).decode()[: m.group(1)[0]], struct.unpack(">d", m.group(3))[0], m.start(3)))
    return out

def set_param(src, dst, name, value, occurrence=-1):
    b = bytearray(open(src, "rb").read()); split(b)
    pat = b"\x08\x00\x00\x00" + bytes([len(name)]) + name.encode() + b"\x00\x00\x01\x36\x07"
    hits = [m.end() for m in re.finditer(re.escape(pat), b)]
    if not hits: raise SystemExit(f"{name!r} not found as a plain double param")
    off = hits[occurrence]
    old = struct.unpack(">d", b[off:off + 8])[0]
    b[off:off + 8] = struct.pack(">d", float(value))
    open(dst, "wb").write(b)
    return {"occurrences": len(hits), "offset": off, "old": old, "new": float(value)}

if __name__ == "__main__":
    if sys.argv[1] == "info":
        i = info(sys.argv[2]); print(i["device_name"], i["size"]); print("strings:", i["strings"][:80]); print("params:", i["params"][:40])
    elif sys.argv[1] == "set":
        print(set_param(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], int(sys.argv[6]) if len(sys.argv) > 6 else -1))
