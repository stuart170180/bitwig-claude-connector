"""Read and patch Bitwig preset files (.bwpreset, container version 0002 - the plain one) and write a patched copy.

Only same-length edits are supported: a named numeric value (a double stored as [name][field 0x136][07 + 8-byte
big-endian double]) is overwritten in a COPY of the preset. Adding modules, cables or modulators is not possible
(the payload's length fields are not decoded). Factory device/module/modulator files in Bitwig's Library (version
0004) are scrambled and can't be read; presets from device-settings/ and user presets are version 0002."""
import hashlib
import re
import struct
from pathlib import Path

OUT = Path(__file__).resolve().parent / "patched_presets"
MAGIC = b"BtWg00030002"
PARAM = re.compile(rb"\x08\x00\x00\x00(.)([A-Za-z0-9_/ >+.-]+)\x00\x00\x01\x36\x07(.{8})", re.S)


def _read(path):
    b = Path(path).read_bytes()
    if b[:12] != MAGIC:
        raise ValueError("not a plain (version 0002) preset: Bitwig's factory device/module/modulator files are "
                         "scrambled; use a preset from device-settings/ or one you saved yourself")
    return b


def _meta(b):
    return b[0x2a:0x2a + int(b[0x10:0x18], 16)]


def _params(b):
    """[(name, value, offset_of_double)] for every plain double value in the payload."""
    out = []
    for m in PARAM.finditer(b):
        name = m.group(2)
        if len(name) == m.group(1)[0]:
            out.append((name.decode(), struct.unpack(">d", m.group(3))[0], m.start(3)))
    return out


def inspect(path):
    b = _read(path)
    meta = _meta(b)
    dn = re.search(rb"device_name\x08\x00\x00\x00.([^\x00]*)", meta)
    refs = {}
    for k in ("referenced_module_ids", "referenced_modulator_ids", "referenced_device_ids"):
        m = re.search(k.encode() + rb"\x19\x00\x00\x00(....)", meta)
        refs[k.replace("referenced_", "").replace("_ids", "s")] = struct.unpack("<I", m.group(1))[0] if m else 0
    names = [s.decode() for s in re.findall(rb"\x08\x00\x00\x00.([\x20-\x7e]{2,})", b[0x2a + len(meta):])]
    seen, values = {}, []
    for name, val, _ in _params(b):
        seen[name] = seen.get(name, 0) + 1
        values.append({"name": name, "occurrence": seen[name] - 1, "value": val})
    return {"device_name": dn.group(1).decode() if dn else None, "size_bytes": len(b), "contains": refs,
            "values": values, "strings_in_payload": sorted(set(names))[:120]}


def patch(path, changes: dict):
    """changes: {name: value} or {name: {"value": v, "occurrence": n}}; a bare value edits the last occurrence of the
    name (the device-level one). Returns (path_of_patched_copy, report)."""
    b = bytearray(_read(path))
    plist = _params(bytes(b))
    report = []
    for name, spec in changes.items():
        value, occ = (spec["value"], spec.get("occurrence", -1)) if isinstance(spec, dict) else (spec, -1)
        hits = [(v, off) for n, v, off in plist if n == name]
        if not hits:
            raise ValueError(f"{name!r} is not a plain numeric value in this preset (see preset_inspect)")
        old, off = hits[occ]
        b[off:off + 8] = struct.pack(">d", float(value))
        report.append({"name": name, "old": old, "new": float(value), "occurrences_in_file": len(hits)})
    OUT.mkdir(exist_ok=True)
    tag = hashlib.sha1(bytes(b)).hexdigest()[:8]
    dst = OUT / f"{Path(path).stem}_{tag}.bwpreset"
    dst.write_bytes(bytes(b))
    return str(dst), report
