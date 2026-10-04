import sys
from pathlib import Path

_R = Path(__file__).resolve()
while not (_R / "server.py").exists():
    _R = _R.parent
sys.path[:0] = [str(_R), str(_R / "research")]   # repo root (server, bwmcp) and research/ (bwlock, bwformat)
"""bwformat: parse / serialize / inspect / edit Bitwig Studio plain presets (container "BtWg00030002").

Applies to .bwpreset and .bwremotecontrols files of container version 0002 (version 0004 files are scrambled and
NOT supported).  See docs/PRESET_FORMAT.md for the grammar and the evidence.

Quick use:
    import bwformat as bw
    f = bw.load(path)                 # -> BwFile(header, meta, padding, root)
    assert bw.dump(f) == open(path,'rb').read()
    print(bw.grid_inspect(f))         # readable view of a device / modulators / grid modules
    bw.save(f, out_path)

Grammar (all integers big-endian):
  file     := header(42) meta padding '\\n' payload
  header   := 'BtWg' '0003' '0002' <4 hex: opaque, kept verbatim> <8 hex: absolute offset of payload>
              '0000000000000000' '00'
  meta     := u32(4) str('meta') { u32(1) str(key) typed-value }  u32(0)
  padding  := N spaces (normally 5000, 0 for 'Containers' presets), then one '\\n'
  payload  := u32(root class) fields
  fields   := { u32(field id != 0) u8(type) value }  u32(0)             (an object body; id 0 ends it)
  value by type byte:
     01 u8 | 05 u8 | 02 i16 | 03 i32 | 0b i32 (enum) | 07 f64 | 08 string | 0a null (no bytes)
     15, 16 : 16 raw bytes (15 = UUID) | 0d : u32 n + n bytes | 17 : u32 n + n*f32
     09 object : u32(class) fields              -> body ends with u32(0)
     12 list   : { u32(code) ... } code 3 = end of list (no further bytes), code 1 = u32 integer element,
                 any other code = object class id of an element followed by fields (ends with u32(0))
     19 (meta only) string array : u32 n + n strings
  string := u32 len + bytes (utf-8) ; if len has bit 31 set: (len&0x7fffffff) UTF-16BE code units.
"""
import struct, re, io, os

HEADER_LEN = 0x2A
PAD_DEFAULT = 5000


# ----------------------------------------------------------------------------- data model
class Node:
    """A typed value.  t = type byte; v = python value (int/float/str/bytes/list/Obj/None)."""
    __slots__ = ("t", "v", "u16")

    def __init__(self, t, v=None, u16=False):
        self.t, self.v, self.u16 = t, v, u16

    def __repr__(self):
        return "Node(%02x,%r)" % (self.t, self.v if not isinstance(self.v, Obj) else "obj")


class Field:
    __slots__ = ("id", "node")

    def __init__(self, id, node):
        self.id, self.node = id, node

    def __repr__(self):
        return "Field(%#x,%r)" % (self.id, self.node)


class Obj:
    """Object body: class id + ordered fields.  Also used for the payload root."""
    __slots__ = ("cls", "fields")

    def __init__(self, cls, fields=None):
        self.cls, self.fields = cls, fields if fields is not None else []

    def get(self, fid, default=None):
        """First field with this id -> python value (Node.v) or default."""
        for f in self.fields:
            if f.id == fid:
                return f.node.v
        return default

    def node(self, fid):
        for f in self.fields:
            if f.id == fid:
                return f.node
        return None

    def getall(self, fid):
        return [f.node.v for f in self.fields if f.id == fid]

    def set(self, fid, value, t=None):
        """Replace the value of an existing field (keeps its type unless t given)."""
        for f in self.fields:
            if f.id == fid:
                f.node.v = value
                if t is not None:
                    f.node.t = t
                return f.node
        raise KeyError(hex(fid))

    def __repr__(self):
        return "Obj(%#x, %d fields)" % (self.cls, len(self.fields))


class ListItemInt:
    """List element encoded as code 1 + int32."""
    __slots__ = ("v",)

    def __init__(self, v):
        self.v = v

    def __repr__(self):
        return "ListItemInt(%d)" % self.v


class BwFile:
    def __init__(self):
        self.magic = b"BtWg00030002"
        self.hdr_opaque = b"00c4"          # 4 hex digits, meaning unknown, kept verbatim
        self.hdr_tail = b"000000000000000000"  # 16 hex zeros + '00'
        self.meta_first = 4                # first u32 of meta (always 4)
        self.meta = []                     # [(key, type, value)] type 8 str, 3 int, 0x19 list[str], 0x0d bytes
        self.padding = b" " * PAD_DEFAULT
        self.root = Obj(0)                 # root.cls = first u32 of payload


# ----------------------------------------------------------------------------- reading
class _R:
    def __init__(self, b, p=0):
        self.b, self.p = b, p

    def u32(self):
        v = struct.unpack_from(">I", self.b, self.p)[0]
        self.p += 4
        return v

    def u8(self):
        v = self.b[self.p]
        self.p += 1
        return v

    def take(self, n):
        if self.p + n > len(self.b):
            raise ValueError("truncated at %d" % self.p)
        v = self.b[self.p:self.p + n]
        self.p += n
        return v

    def string(self):
        n = self.u32()
        if n & 0x80000000:
            return Node(8, self.take((n & 0x7FFFFFFF) * 2).decode("utf-16-be", "surrogatepass"), True)
        return Node(8, self.take(n).decode("utf-8", "surrogateescape"), False)


def _read_value(r, t):
    if t in (1, 5):
        return Node(t, r.u8())
    if t == 2:
        return Node(t, struct.unpack(">H", r.take(2))[0])
    if t in (3, 0xB):
        return Node(t, r.u32())
    if t == 7:
        return Node(t, r.take(8))          # kept as raw 8 bytes; use Node.f64 helpers to decode
    if t == 8:
        return r.string()
    if t == 0xA:
        return Node(t, None)
    if t in (0x15, 0x16):
        return Node(t, bytes(r.take(16)))
    if t == 0xD:
        return Node(t, bytes(r.take(r.u32())))
    if t == 0x17:
        n = r.u32()
        return Node(t, bytes(r.take(4 * n)))
    if t == 9:
        cls = r.u32()
        return Node(t, Obj(cls, _read_fields(r)))
    if t == 0x12:
        items = []
        while True:
            code = r.u32()
            if code == 3:
                break
            if code == 1:
                items.append(ListItemInt(r.u32()))
            else:
                items.append(Obj(code, _read_fields(r)))
        return Node(t, items)
    raise ValueError("unknown type %#x at %d" % (t, r.p - 1))


def _read_fields(r):
    out = []
    while True:
        fid = r.u32()
        if fid == 0:
            return out
        t = r.u8()
        out.append(Field(fid, _read_value(r, t)))


def parse(b):
    b = bytes(b)
    if b[:12] != b"BtWg00030002":
        raise ValueError("not a plain (version 0002) Bitwig file: %r" % b[:12])
    f = BwFile()
    f.magic = b[:12]
    f.hdr_opaque = b[12:16]
    off = int(b[16:24], 16)
    f.hdr_tail = b[24:HEADER_LEN]
    r = _R(b, HEADER_LEN)
    f.meta_first = r.u32()
    tag = r.string()
    if tag.v != "meta":
        raise ValueError("meta tag missing")
    meta = []
    while True:
        m = r.u32()
        if m == 0:
            break
        if m != 1:
            raise ValueError("bad meta marker %d" % m)
        key = r.string().v
        t = r.u8()
        if t == 0x19:
            n = r.u32()
            meta.append((key, t, [r.string().v for _ in range(n)]))
        else:
            n = _read_value(r, t)
            meta.append((key, t, n.v if t != 8 else n.v))
    f.meta = meta
    pad_end = off - 1
    if b[pad_end:pad_end + 1] != b"\n" or r.p > pad_end:
        raise ValueError("payload offset does not point after padding+newline")
    f.padding = b[r.p:pad_end]
    pr = _R(b, off)
    root = Obj(pr.u32())
    root.fields = _read_fields(pr)
    if pr.p != len(b):
        raise ValueError("trailing bytes after payload: %d" % (len(b) - pr.p))
    f.root = root
    return f


# ----------------------------------------------------------------------------- writing
def _wstr(out, s, u16=False):
    if u16:
        d = s.encode("utf-16-be", "surrogatepass")
        out += struct.pack(">I", 0x80000000 | (len(d) // 2)) + d
    else:
        d = s.encode("utf-8", "surrogateescape")
        out += struct.pack(">I", len(d)) + d


def _write_value(out, n):
    t, v = n.t, n.v
    out.append(t)
    if t in (1, 5):
        out.append(v)
    elif t == 2:
        out += struct.pack(">H", v)
    elif t in (3, 0xB):
        out += struct.pack(">I", v)
    elif t == 7:
        out += v if isinstance(v, (bytes, bytearray)) else struct.pack(">d", v)
    elif t == 8:
        _wstr(out, v, n.u16)
    elif t == 0xA:
        pass
    elif t in (0x15, 0x16):
        out += v
    elif t == 0xD:
        out += struct.pack(">I", len(v)) + v
    elif t == 0x17:
        out += struct.pack(">I", len(v) // 4) + v
    elif t == 9:
        out += struct.pack(">I", v.cls)
        _write_fields(out, v.fields)
    elif t == 0x12:
        for it in v:
            if isinstance(it, ListItemInt):
                out += struct.pack(">II", 1, it.v)
            else:
                out += struct.pack(">I", it.cls)
                _write_fields(out, it.fields)
        out += struct.pack(">I", 3)
    else:
        raise ValueError("cannot write type %#x" % t)


def _write_fields(out, fields):
    for f in fields:
        out += struct.pack(">I", f.id)
        _write_value(out, f.node)
    out += b"\0\0\0\0"


def dump(f):
    meta = bytearray()
    meta += struct.pack(">I", f.meta_first)
    _wstr(meta, "meta")
    for key, t, v in f.meta:
        meta += struct.pack(">I", 1)
        _wstr(meta, key)
        meta.append(t)
        if t == 8:
            _wstr(meta, v)
        elif t == 3:
            meta += struct.pack(">I", v)
        elif t == 0xD:
            meta += struct.pack(">I", len(v)) + v
        elif t == 0x19:
            meta += struct.pack(">I", len(v))
            for s in v:
                _wstr(meta, s)
        else:
            raise ValueError("meta type %#x" % t)
    meta += struct.pack(">I", 0)
    off = HEADER_LEN + len(meta) + len(f.padding) + 1
    out = bytearray(f.magic + f.hdr_opaque + b"%08x" % off + f.hdr_tail)
    out += meta + f.padding + b"\n"
    out += struct.pack(">I", f.root.cls)
    _write_fields(out, f.root.fields)
    return bytes(out)


def load(path):
    with open(path, "rb") as fh:
        return parse(fh.read())


def save(f, path):
    with open(path, "wb") as fh:
        fh.write(dump(f))


# ----------------------------------------------------------------------------- generic helpers
def f64(n):
    return struct.unpack(">d", n.v)[0]


def set_f64(n, x):
    n.v = struct.pack(">d", float(x))


def walk(obj, path=()):
    """Yield (path, Field) for every field in depth-first order. path = tuple of (class, index-in-parent) elements."""
    for i, fl in enumerate(obj.fields):
        yield path, obj, fl
        v = fl.node.v
        if fl.node.t == 9:
            yield from walk(v, path + ((v.cls, fl.id),))
        elif fl.node.t == 0x12:
            for j, it in enumerate(v):
                if isinstance(it, Obj):
                    yield from walk(it, path + ((it.cls, fl.id, j),))


def meta_get(f, key, default=None):
    for k, t, v in f.meta:
        if k == key:
            return v
    return default


def meta_set(f, key, value):
    for i, (k, t, v) in enumerate(f.meta):
        if k == key:
            f.meta[i] = (k, t, value)
            return
    raise KeyError(key)


# ----------------------------------------------------------------------------- semantic layer (field / class ids)
# Field ids (decoded by comparing ~160 presets; see docs/PRESET_FORMAT.md section 4)
F_NAME, F_PRESET_NAME, F_DEVNAME, F_CREATOR, F_CATEGORY = 0x2B9, 0x12DE, 0x9A, 0x9B, 0x9C
F_DEVICE, F_MODULATORS, F_UUID, F_CONTENTS, F_MEMBERS = 0x1421, 0x18F5, 0x99, 0xA4, 0x20C
F_CONTENT_OBJ, F_TYPE_UUID, F_LIST = 0x18C7, 0x18C6, 0x1A46
F_REAL, F_BOOL, F_INT, F_ENUM, F_PORT_SRC = 0x136, 0x12F, 0x330, 0x273, 0x1C4A
F_MAPPINGS, F_MAP_TARGET, F_MAP_RANGE, F_MAP_AMOUNT = 0xE20, 0xE3D, 0x1334, 0xE32
F_MOD_X, F_MOD_Y, F_MOD_W, F_MOD_H = 0x1A1A, 0x1A1B, 0x2651, 0x2652
# Class ids
C_DEVICE, C_MODULATORS, C_MODULES, C_MODULATOR, C_MODULE, C_CONTENTS = 0x40, 0x75F, 0x771, 0x6C9, 0x76F, 0xD3
C_REAL, C_BOOL, C_INT, C_ENUM, C_PORT, C_MODOUT, C_MAPPING, C_SLOT = 0x85, 0x7F, 0x189, 0xF7, 0x7E2, 0x2FC, 0x2FD, 0x24E
KIND = {C_REAL: "real", C_BOOL: "bool", C_INT: "int", C_ENUM: "enum", C_PORT: "port", C_MODOUT: "modsource",
        C_SLOT: "slot", 0xD94: "poly", 0x37C: "note-source"}


def _s8(v):
    return v - 256 if v > 127 else v


def device_obj(f):
    """The device object (class 0x40) of a preset."""
    o = f.root.get(F_DEVICE)
    if o is None:
        raise ValueError("no device object (this file is not a device preset?)")
    return o


def _hexuuid(b):
    h = b.hex()
    return "%s-%s-%s-%s-%s" % (h[:8], h[8:12], h[12:16], h[16:20], h[20:])


def _uuid_bytes(s):
    return bytes.fromhex(s.replace("-", ""))


def contents_list(o):
    """The member list (field 0x20c) of an object's CONTENTS (0xd3) object, as list of Obj ([] if none)."""
    c = o.get(F_CONTENTS) if o.node(F_CONTENTS) else o.get(F_CONTENT_OBJ)
    if c is None:
        c = o.get(F_CONTENT_OBJ)
    return c.get(F_MEMBERS, []) if c is not None else []


def _member_value(m):
    """Readable value of a CONTENTS member."""
    k = KIND.get(m.cls, "cls%x" % m.cls)
    d = {"name": m.get(F_NAME), "kind": k}
    if m.cls == C_REAL:
        d["value"] = f64(m.node(F_REAL))
    elif m.cls == C_BOOL:
        d["value"] = bool(m.get(F_BOOL))
    elif m.cls == C_INT:
        d["value"] = m.get(F_INT)
    elif m.cls == C_ENUM:
        d["value"] = m.get(F_ENUM)
    elif m.cls == C_PORT:
        d["source"] = m.get(F_PORT_SRC) or None
    elif m.cls == C_MODOUT:
        d["mappings"] = [_mapping_view(x) for x in m.get(F_MAPPINGS, []) if isinstance(x, Obj)]
    return d


def _mapping_view(x):
    rng = x.get(F_MAP_RANGE)
    r = {"target": x.get(F_MAP_TARGET), "amount": f64(x.node(F_MAP_AMOUNT)) if x.node(F_MAP_AMOUNT) else None}
    if isinstance(rng, Obj):
        r["min"] = f64(rng.node(0x124)) if rng.node(0x124) else None
        r["max"] = f64(rng.node(0x125)) if rng.node(0x125) else None
        r["base"] = f64(rng.node(0x37B)) if rng.node(0x37B) else None
    return r


def device_info(f):
    """Dict: device name, preset name, creator, category, uuid, parameters (list of member views)."""
    d = device_obj(f)
    return {"name": d.get(F_DEVNAME), "preset": d.get(F_PRESET_NAME), "creator": d.get(F_CREATOR),
            "category": d.get(F_CATEGORY), "uuid": _hexuuid(f.root.get(F_UUID) or b"\0" * 16),
            "members": [_member_value(m) for m in contents_list(d)]}


def modulators(f):
    """List of modulator Objs (class 0x6c9) of the device."""
    d = device_obj(f)
    mo = d.get(F_MODULATORS)
    return [x for x in (mo.get(F_LIST, []) if mo else []) if isinstance(x, Obj)]


def modulator_view(m):
    return {"id": m.get(F_NAME), "name": m.get(F_DEVNAME), "category": m.get(F_CATEGORY),
            "type_uuid": _hexuuid(m.get(F_TYPE_UUID) or b"\0" * 16),
            "members": [_member_value(x) for x in contents_list(m)]}


def modules_obj(f):
    """The 'MODULES' container (class 0x771) among the device CONTENTS members, or None."""
    for m in contents_list(device_obj(f)):
        if m.cls == C_MODULES:
            return m
    return None


def modules(f):
    mo = modules_obj(f)
    return [x for x in (mo.get(F_LIST, []) if mo else []) if isinstance(x, Obj)]


def module_view(m):
    return {"id": m.get(F_NAME), "name": m.get(F_DEVNAME), "category": m.get(F_CATEGORY),
            "type_uuid": _hexuuid(m.get(F_TYPE_UUID) or b"\0" * 16),
            "x": _s8(m.get(F_MOD_X, 0)), "y": _s8(m.get(F_MOD_Y, 0)), "w": m.get(F_MOD_W), "h": m.get(F_MOD_H),
            "members": [_member_value(x) for x in contents_list(m)]}


def cables(f):
    """[(source path, dest module id, dest port)] from every module input port that has a source."""
    out = []
    for m in modules(f):
        for x in contents_list(m):
            if x.cls == C_PORT and x.get(F_PORT_SRC):
                out.append((x.get(F_PORT_SRC), m.get(F_NAME), x.get(F_NAME)))
    return out


def grid_inspect(f, show_params=True):
    """Human readable text view of a device preset: parameters, modulators (with mappings), grid modules + cables."""
    info = device_info(f)
    L = ["device %r (preset %r, creator %r, category %r, uuid %s)" % (info["name"], info["preset"], info["creator"],
                                                                    info["category"], info["uuid"])]
    L.append("  parameters:")
    for m in info["members"]:
        if m["kind"] in ("real", "bool", "int", "enum"):
            L.append("    %-22s %-5s %s" % (m["name"], m["kind"], m["value"]))
        elif m["kind"] == "modsource" and m["mappings"]:
            L.append("    %-22s modulation source %r" % (m["name"], m["mappings"]))
    mods = modulators(f)
    L.append("  modulators (%d):" % len(mods))
    for m in mods:
        v = modulator_view(m)
        L.append("    [%s] %s (%s) type=%s" % (v["id"], v["name"], v["category"], v["type_uuid"]))
        for x in v["members"]:
            if x["kind"] in ("real", "bool", "int", "enum") and show_params:
                L.append("        %-20s %s" % (x["name"], x["value"]))
            elif x["kind"] == "port" and x.get("source"):
                L.append("        input %-14s <- %s" % (x["name"], x["source"]))
            elif x["kind"] == "modsource":
                for mp in x["mappings"]:
                    L.append("        output %-13s -> %s amount %.6g (target range %s..%s, base %s)" % (
                        x["name"], mp["target"], mp["amount"], mp.get("min"), mp.get("max"), mp.get("base")))
    mm = modules(f)
    if mm or modules_obj(f) is not None:
        L.append("  grid modules (%d):" % len(mm))
        for m in mm:
            v = module_view(m)
            L.append("    [%s] %s (%s) at x=%d y=%d size %sx%s" % (v["id"], v["name"], v["category"], v["x"], v["y"],
                                                                v["w"], v["h"]))
            for x in v["members"]:
                if x["kind"] in ("real", "bool", "int", "enum") and show_params:
                    L.append("        %-22s %s" % (x["name"], x["value"]))
                elif x["kind"] == "modsource":
                    for mp in x["mappings"]:
                        L.append("        output %s -> %s amount %.6g" % (x["name"], mp["target"], mp["amount"]))
        L.append("  cables (%d):" % len(cables(f)))
        for s, mid, port in cables(f):
            L.append("    %s  ->  MODULES/%s/%s" % (s, mid, port))
    return "\n".join(L)


# ----------------------------------------------------------------------------- edits (all operate in memory on a BwFile)
import copy as _copy


def clone(o):
    """Deep copy of an Obj / Node / BwFile."""
    return _copy.deepcopy(o)


def _str_node(s):
    return Node(8, s, False)


def _meta_ref_add(f, key, uuid_str):
    for i, (k, t, v) in enumerate(f.meta):
        if k == key:
            if uuid_str not in v:
                f.meta[i] = (k, t, list(v) + [uuid_str])
            return
    raise KeyError(key)


def set_device_names(f, device_name=None, preset_name=None, instance_name=None):
    """Rename. device_name = field 0x9a of the device (+ meta 'device_name'), preset_name = field 0x12de (what the
    browser calls the preset), instance_name = field 0x2b9 of the device object. Any length."""
    d = device_obj(f)
    if device_name is not None:
        d.set(F_DEVNAME, device_name)
        meta_set(f, "device_name", device_name)
    if preset_name is not None:
        d.set(F_PRESET_NAME, preset_name)
    if instance_name is not None:
        d.set(F_NAME, instance_name)


def get_modulator(f, mid):
    for m in modulators(f):
        if m.get(F_NAME) == str(mid):
            return m
    raise KeyError("modulator %r" % (mid,))


def get_module(f, mid):
    for m in modules(f):
        if m.get(F_NAME) == str(mid):
            return m
    raise KeyError("module %r" % (mid,))


def member(o, name):
    """CONTENTS member of a device/modulator/module by name (Obj) or KeyError."""
    for m in contents_list(o):
        if m.get(F_NAME) == name:
            return m
    raise KeyError(name)


def _mod_sources(m):
    return [x for x in contents_list(m) if x.cls == C_MODOUT]


def set_mapping_amount(f, modulator_id, target, amount, output=None):
    """Change the amount of an existing mapping (target e.g. 'CONTENTS/PITCH_TRANSPOSE'). Value in the target
    parameter's native units (semitones for pitch).  Same-length edit."""
    mod = get_modulator(f, modulator_id)
    for src in _mod_sources(mod):
        if output and src.get(F_NAME) != output:
            continue
        for mp in src.get(F_MAPPINGS, []):
            if isinstance(mp, Obj) and mp.get(F_MAP_TARGET) == target:
                set_f64(mp.node(F_MAP_AMOUNT), amount)
                return mp
    raise KeyError("no mapping to %r on modulator %r" % (target, modulator_id))


def new_mapping(target, amount, rng_min=0.0, rng_max=1.0, base=0.0, tmpl=None):
    """Build a mapping object (class 0x2fd).  tmpl = an existing mapping Obj whose 0x1334 range block is cloned
    (keeps the unknown display-hint bytes 0x126/0x127/0xbc6/0x7c4/0x128); otherwise generic 0..1 hints."""
    def d(x):
        return Node(7, struct.pack(">d", float(x)))
    if tmpl is not None:
        rng = clone(tmpl.get(F_MAP_RANGE))
        for fid, val in ((0x124, rng_min), (0x125, rng_max), (0x37B, base)):
            rng.set(fid, struct.pack(">d", float(val)))
    else:
        rng = Obj(0x7B, [Field(0x411A, Node(5, 0)), Field(0x124, d(rng_min)), Field(0x125, d(rng_max)),
                         Field(0x37B, d(base)), Field(0x126, Node(1, 5)), Field(0x127, Node(1, 0)),
                         Field(0xBC6, Node(1, 0)), Field(0x7C4, d(-1.0)), Field(0x128, Node(1, 2)),
                         Field(0x1151, Node(5, 1)), Field(0x1152, Node(5, 1))])
    return Obj(C_MAPPING, [Field(F_NAME, _str_node("")), Field(F_MAP_TARGET, _str_node(target)),
                           Field(F_MAP_RANGE, Node(9, rng)), Field(F_MAP_AMOUNT, d(amount)),
                           Field(0x2D3B, Node(5, 1)), Field(0x2C4C, Node(1, 0)), Field(0x2D2C, _str_node(""))])


def add_mapping(f, modulator_id, target, amount, rng_min=0.0, rng_max=1.0, base=0.0, output=None, tmpl=None):
    """Append a mapping from a modulator's output to `target` (path relative to the device, e.g.
    'CONTENTS/CUTOFF').  rng_min/rng_max/base = the target parameter's native range and current value
    (stored as a snapshot in the mapping).  Length-changing."""
    mod = get_modulator(f, modulator_id)
    srcs = [s for s in _mod_sources(mod) if not output or s.get(F_NAME) == output]
    if not srcs:
        raise KeyError("modulator %r has no modulation output %r" % (modulator_id, output))
    src = srcs[0]
    if tmpl is None:  # reuse any existing mapping in this file for the hint bytes
        for mm in modulators(f):
            for s in _mod_sources(mm):
                for mp in s.get(F_MAPPINGS, []):
                    if isinstance(mp, Obj) and isinstance(mp.get(F_MAP_RANGE), Obj):
                        tmpl = mp
    mp = new_mapping(target, amount, rng_min, rng_max, base, tmpl)
    src.node(F_MAPPINGS).v.append(mp)
    return mp


def remove_mapping(f, modulator_id, target, output=None):
    mod = get_modulator(f, modulator_id)
    for src in _mod_sources(mod):
        lst = src.node(F_MAPPINGS).v
        for i, mp in enumerate(lst):
            if isinstance(mp, Obj) and mp.get(F_MAP_TARGET) == target:
                del lst[i]
                return True
    return False


def extract_modulator(f, mid):
    """Deep copy of a modulator object (to use as a template for add_modulator on another preset)."""
    return clone(get_modulator(f, mid))


def extract_module(f, mid):
    return clone(get_module(f, mid))


def add_modulator(f, template, new_id=None, keep_mappings=False):
    """Add a copy of a modulator Obj (class 0x6c9, e.g. from extract_modulator of another preset) to the device.
    Mappings are dropped unless keep_mappings; use add_mapping afterwards.  Updates the meta's
    referenced_modulator_ids.  Returns the new modulator Obj."""
    d = device_obj(f)
    mo = d.get(F_MODULATORS)
    if mo is None:
        raise ValueError("device has no MODULATORS container")
    lst = mo.node(F_LIST).v
    m = clone(template)
    ids = [int(x.get(F_NAME)) for x in lst if isinstance(x, Obj) and x.get(F_NAME, "").isdigit()]
    nid = str(new_id if new_id is not None else (max(ids) + 1 if ids else 0))
    m.set(F_NAME, nid)
    idx = len(lst)
    if m.node(F_MOD_Y) is not None:   # grid_y: modulators are stacked one below the other
        m.set(F_MOD_Y, idx)
    if not keep_mappings:
        for s in _mod_sources(m):
            s.node(F_MAPPINGS).v[:] = []
    lst.append(m)
    _meta_ref_add(f, "referenced_modulator_ids", _hexuuid(m.get(F_TYPE_UUID)))
    return m


def _occupied(f):
    cells = set()
    for m in modules(f):
        x, y, w, h = _s8(m.get(F_MOD_X, 0)), _s8(m.get(F_MOD_Y, 0)), m.get(F_MOD_W) or 1, m.get(F_MOD_H) or 1
        cells |= {(x + i, y + j) for i in range(w) for j in range(h)}
    return cells


def add_module(f, template, x=None, y=None, new_id=None, near=None):
    """Add a copy of a Grid module Obj (class 0x76f, e.g. from extract_module of another preset) to the patch.
    All its input ports are unconnected and its modulation mappings dropped.  (x, y) = grid cell (default: first
    free spot right of the existing modules; near=<module id> = right of that module).  Updates
    referenced_module_ids.  Returns the new module Obj."""
    mo = modules_obj(f)
    if mo is None:
        raise ValueError("device has no MODULES container (not a Grid device)")
    lst = mo.node(F_LIST).v
    m = clone(template)
    ids = [int(q.get(F_NAME)) for q in lst if isinstance(q, Obj) and q.get(F_NAME, "").isdigit()]
    nid = str(new_id if new_id is not None else (max(ids) + 1 if ids else 0))
    m.set(F_NAME, nid)
    w, h = m.get(F_MOD_W) or 1, m.get(F_MOD_H) or 1
    occ = _occupied(f)
    if x is None or y is None:
        if near is not None:       # first free spot to the right of module `near` (same row first, then rows below/above)
            nm = get_module(f, near)
            x0, y0 = _s8(nm.get(F_MOD_X, 0)) + (nm.get(F_MOD_W) or 1), _s8(nm.get(F_MOD_Y, 0))
            rows = [0, 1, -1, 2, -2, 3, -3, 4, -4]
        else:
            xs = [_s8(q.get(F_MOD_X, 0)) for q in lst] or [0]
            ys = [_s8(q.get(F_MOD_Y, 0)) for q in lst] or [0]
            x0, y0 = max(xs) + 1, min(ys)
            rows = list(range(0, 12))
        x = y = None
        for dy in rows:
            for dx in range(0, 24):
                cx, cy = x0 + dx, y0 + dy
                if all((cx + i, cy + j) not in occ for i in range(w) for j in range(h)):
                    x, y = cx, cy
                    break
            if x is not None:
                break
        if x is None:
            raise ValueError("no free grid spot found; pass x and y")
    m.set(F_MOD_X, x & 0xFF)
    m.set(F_MOD_Y, y & 0xFF)
    for p in contents_list(m):
        if p.cls == C_PORT:
            p.set(F_PORT_SRC, "")
        elif p.cls == C_MODOUT and p.node(F_MAPPINGS) is not None:
            p.node(F_MAPPINGS).v[:] = []
    lst.append(m)
    _meta_ref_add(f, "referenced_module_ids", _hexuuid(m.get(F_TYPE_UUID)))
    return m


def connect(f, src_module, src_port, dst_module, dst_port):
    """Cable: output `src_port` (usually 'OUT' / 'MOD_OUT') of module id src_module -> input port of dst_module.
    An input holds ONE source (it is a string field); an existing cable on it is replaced."""
    get_module(f, src_module)
    p = member(get_module(f, dst_module), dst_port)
    if p.cls != C_PORT:
        raise ValueError("%s is not an input port" % dst_port)
    p.set(F_PORT_SRC, "CONTENTS/MODULES/%s/CONTENTS/%s" % (src_module, src_port))
    return p


def disconnect(f, dst_module, dst_port):
    p = member(get_module(f, dst_module), dst_port)
    p.set(F_PORT_SRC, "")


# ----------------------------------------------------------------------------- names (harvested from Bitwig's own load errors)
# Method: delete one field of an object, load the file, read "Required property X in class Y not found" from the log.
FIELD_NAMES = {
    0x2B9: "identifier", 0x9A: "device_name", 0x9B: "device_vendor", 0x9C: "device_category", 0x9E: "creator",
    0xA3: "enabled", 0x9D: "device_type", 0x99: "device_UUID", 0xA4: "contents", 0x18C6: "device_UUID(aux)",
    0x18C7: "contents(aux)", 0x1A1A: "grid_x", 0x1A1B: "grid_y", 0x1A19: "is_polyphonic_mode",
    0xE3D: "destination_path", 0xE32: "amount", 0x124: "min", 0x125: "max", 0x37B: "default_value",
    0x126: "domain", 0x127: "engine_domain", 0x128: "unit", 0x1C4A: "source_path", 0x136: "value(decimal)",
    0x12F: "value(boolean)", 0x330: "value(integer)", 0x273: "value(indexed)", 0x20C: "child_presets",
    0x1A46: "auxiliary_devices", 0xE20: "mappings(?)", 0x1334: "value_type(range snapshot)", 0x12DE: "preset_name(?)",
    0x1421: "preset", 0x18F5: "modulators container(?)", 0x1A85: "(?)", 0x1423: "(?)", 0x150A: "(?)", 0x1422: "(?)",
}
CLASS_NAMES = {
    0x561: "preset_document", 0x40: "native_device_preset", 0xD3: "generic_module_preset (CONTENTS)",
    0x771: "module_grid_preset (MODULES)", 0x75F: "(MODULATORS container)", 0x76F: "auxiliary_device_preset (grid module)",
    0x6C9: "modulator_preset", 0x2FC: "(modulation output)", 0x2FD: "device_modulation_mapping_preset",
    0x7B: "decimal_value_type", 0x7E2: "destination_atom_preset (input port)", 0x85: "decimal_value_atom_preset",
    0x7F: "boolean_value_atom_preset", 0x189: "integer_value_atom_preset", 0xF7: "indexed_value_atom_preset",
    0x24E: "(slot, e.g. PRE_FX/POST_FX)", 0xD94: "(POLY voice settings)", 0x37C: "(note source)", 0x18F: "(device chain)",
}


def dump_tree(o, ind=0, out=None):
    """Indented text dump of an Obj with harvested names where known (debug aid)."""
    out = [] if out is None else out
    pad = "  " * ind
    for fl in o.fields:
        n, v = fl.node, fl.node.v
        nm = FIELD_NAMES.get(fl.id, "")
        head = "%s%#x%s " % (pad, fl.id, (" " + nm) if nm else "")
        if n.t == 9:
            out.append("%s{%#x %s}" % (head, v.cls, CLASS_NAMES.get(v.cls, "")))
            dump_tree(v, ind + 1, out)
        elif n.t == 0x12:
            out.append("%slist[%d]" % (head, len(v)))
            for it in v:
                if isinstance(it, Obj):
                    out.append("%s  - {%#x %s}" % (pad, it.cls, CLASS_NAMES.get(it.cls, "")))
                    dump_tree(it, ind + 2, out)
                else:
                    out.append("%s  - int %d" % (pad, it.v))
        elif n.t == 7:
            out.append("%sf64 %r" % (head, f64(n)))
        elif n.t in (0x15, 0x16, 0xD, 0x17):
            out.append("%st%02x %s" % (head, n.t, v.hex() if len(v) <= 20 else v[:20].hex() + "..."))
        elif n.t == 0xA:
            out.append(head + "null")
        else:
            out.append("%s%r" % (head, v))
    return out


# ----------------------------------------------------------------------------- validation + template library
# Required properties per class (harvested live: removing the field makes Bitwig refuse the whole file).
REQUIRED = {
    C_DEVICE: [0x2B9, 0x9A, 0x9B, 0x9C, 0x9E, 0xA3, 0x9D, 0x99, 0xA4],
    C_MODULATOR: [0x2B9, 0x9A, 0x9B, 0x9C, 0x9E, 0xA3, 0x18C6, 0x18C7, 0x1A1A, 0x1A1B, 0x1A19],
    C_MODULE: [0x2B9, 0x9A, 0x9B, 0x9C, 0x9E, 0xA3, 0x18C6, 0x18C7, 0x1A1A, 0x1A1B],
    C_MAPPING: [0x2B9, 0xE3D, 0xE32],
    0x7B: [0x124, 0x125, 0x37B, 0x126, 0x127, 0x128],
    C_PORT: [0x2B9, 0x1C4A], C_REAL: [0x2B9, 0x136], C_BOOL: [0x2B9, 0x12F], C_INT: [0x2B9, 0x330],
    C_ENUM: [0x2B9, 0x273], C_MODOUT: [0x2B9], C_MODULES: [0x2B9], C_MODULATORS: [0x2B9],
}
# Output port names seen in 160 presets (cable source side): 'OUT' for nearly everything, 'MOD_OUT' for the ADSR
# envelope's modulation output, and the Note In module's *_OUT ports.
OUTPUT_PORTS_SEEN = {"OUT", "MOD_OUT", "GATE_OUT", "PITCH_OUT", "VELOCITY_OUT", "CHANNEL_OUT", "TIMBRE_OUT",
                     "PRESSURE_OUT", "GAIN_OUT", "PAN_OUT"}


def check(f):
    """Offline sanity check of a parsed preset. Returns a list of problem strings (empty = nothing found).
    Catches what makes Bitwig refuse a file (missing required properties) and what it silently ignores
    (dangling cables, duplicate ids, mapping targets that do not exist, meta not listing used module types)."""
    probs = []
    for path, o, fl in walk(f.root):
        if fl.node.t == 9:
            subs = [fl.node.v]
        elif fl.node.t == 0x12:
            subs = [x for x in fl.node.v if isinstance(x, Obj)]
        else:
            continue
        for s in subs:
            for req in REQUIRED.get(s.cls, []):
                if s.node(req) is None:
                    probs.append("object %#x (%s) lacks required field %#x %s" % (
                        s.cls, CLASS_NAMES.get(s.cls, ""), req, FIELD_NAMES.get(req, "")))
    try:
        d = device_obj(f)
    except ValueError:
        return probs
    mods = modules(f)
    ids = [m.get(F_NAME) for m in mods]
    if len(set(ids)) != len(ids):
        probs.append("duplicate module ids %s" % ids)
    mids = [m.get(F_NAME) for m in modulators(f)]
    if len(set(mids)) != len(mids):
        probs.append("duplicate modulator ids %s" % mids)
    for s, mid, port in cables(f):
        mm = re.match(r"CONTENTS/MODULES/([^/]+)/CONTENTS/(.+)$", s)
        if not mm or mm.group(1) not in ids:
            probs.append("cable into %s/%s from unknown source %r" % (mid, port, s))
    for key, refs in (("referenced_module_ids", [_hexuuid(m.get(F_TYPE_UUID)) for m in mods if m.get(F_TYPE_UUID)]),
                      ("referenced_modulator_ids", [_hexuuid(m.get(F_TYPE_UUID)) for m in modulators(f) if m.get(F_TYPE_UUID)])):
        have = meta_get(f, key, [])
        for r in set(refs):
            if r not in have:
                probs.append("meta %s does not list %s" % (key, r))
    params = {m.get(F_NAME) for m in contents_list(d)}
    for m in modulators(f):
        for src in _mod_sources(m):
            for mp in src.get(F_MAPPINGS, []):
                t = mp.get(F_MAP_TARGET) or ""
                mm = re.match(r"CONTENTS/([^/]+)$", t)
                if mm and mm.group(1) not in params:
                    probs.append("modulator %s maps to %r which is not a parameter of the device" % (m.get(F_NAME), t))
    return probs


DEVICE_SETTINGS_DIR = r"C:\Program Files\Bitwig Studio\Library\device-settings"


def _preset_files(dirs=None):
    import glob
    out = []
    for d in (dirs or [DEVICE_SETTINGS_DIR]):
        out += glob.glob(os.path.join(d, "**", "*.bwpreset"), recursive=True)
    return out


def module_templates(dirs=None):
    """{type_uuid: (name, category, source_file, module_id)} for every Grid module found in factory presets
    (default dir: device-settings).  Use extract_module(load(source_file), module_id) to get a template."""
    T = {}
    for p in _preset_files(dirs):
        try:
            f = load(p)
            for m in modules(f):
                v = module_view(m)
                T.setdefault(v["type_uuid"], (v["name"], v["category"], p, v["id"]))
        except Exception:
            pass
    return T


def modulator_templates(dirs=None):
    """Same for modulators: {type_uuid: (name, category, source_file, modulator_id)}."""
    T = {}
    for p in _preset_files(dirs):
        try:
            f = load(p)
            for m in modulators(f):
                v = modulator_view(m)
                T.setdefault(v["type_uuid"], (v["name"], v["category"], p, v["id"]))
        except Exception:
            pass
    return T


def roundtrip(paths):
    """(identical, total, failures) for serialize(parse(bytes)) == bytes over the given files."""
    ok, bad = 0, []
    for p in paths:
        b = open(p, "rb").read()
        try:
            if dump(parse(b)) == b:
                ok += 1
            else:
                bad.append((p, "differs"))
        except Exception as e:  # noqa
            bad.append((p, repr(e)))
    return ok, len(paths), bad


if __name__ == "__main__":
    import sys
    usage = "usage: python bwformat.py inspect <file> | tree <file> | check <file> | roundtrip <file>..."
    if len(sys.argv) < 3:
        raise SystemExit(usage)
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "inspect":
        print(grid_inspect(load(args[0])))
    elif cmd == "tree":
        print("\n".join(dump_tree(load(args[0]).root)))
    elif cmd == "check":
        print(check(load(args[0])) or "no problems found")
    elif cmd == "roundtrip":
        print(roundtrip(args))
    else:
        raise SystemExit(usage)


def insert_module_between(f, template, src_module, dst_module, dst_port="IN", src_port="OUT", in_port="IN",
                          out_port="OUT", **kw):
    """Composite: add a module, cable src_module.src_port -> new.in_port and new.out_port -> dst_module.dst_port
    (replaces the cable that was on dst_module.dst_port).  The new module is placed right of src_module.
    Composite of add_module + connect; the pieces were load-tested, the combination on a large patch was NOT
    (see docs/PRESET_FORMAT.md, engine crash)."""
    m = add_module(f, template, near=kw.pop("near", src_module), **kw)
    nid = m.get(F_NAME)
    connect(f, src_module, src_port, nid, in_port)
    connect(f, nid, out_port, dst_module, dst_port)
    return m
