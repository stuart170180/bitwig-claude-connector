import sys
from pathlib import Path

_R = Path(__file__).resolve()
while not (_R / "server.py").exists():
    _R = _R.parent
sys.path[:0] = [str(_R), str(_R / "research")]   # repo root (server, bwmcp) and research/ (bwlock, bwformat)
"""Offline tests for research/bwformat.py (no Bitwig needed).  Run: python research/test_bwformat.py"""
import os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bwformat as bw

ROOTS = [r"C:\Program Files\Bitwig Studio\Library", r"C:\Users\stuar\AppData\Local\Bitwig Studio\installed-packages",
         r"C:\Users\stuar\Documents\Bitwig Studio"]


def v2_files():
    out = []
    for r in ROOTS:
        for ext in ("*.bwpreset", "*.bwremotecontrols"):
            for p in glob.glob(os.path.join(r, "**", ext), recursive=True):
                with open(p, "rb") as fh:
                    if fh.read(12) == b"BtWg00030002":
                        out.append(p)
    return out


def main():
    files = v2_files()
    ok, total, bad = bw.roundtrip(files)
    print("round trip: %d of %d identical" % (ok, total), bad[:3])
    assert ok == total

    ds = bw.DEVICE_SETTINGS_DIR
    pg = bw.load(os.path.join(ds, "a33bba66-8cd4-4f89-aee5-68bf67f70a54", "Default.bwpreset"))
    fx = bw.load(os.path.join(ds, "d641f61b-d4db-4006-930e-cdd7aeb3e9d7", "Default.bwpreset"))
    flt = bw.load(os.path.join(ds, "4ccfc70e-59bd-4e97-a8a7-d8cdce88bf42", "Default.bwpreset"))
    assert [m.get(bw.F_DEVNAME) for m in bw.modules(pg)] == ["Multiosc", "ADSR", "Audio Out"]
    assert len(bw.cables(pg)) == 2 and bw.check(pg) == []

    # edits survive serialize -> parse
    f = bw.clone(pg)
    bw.set_mapping_amount(f, 0, "CONTENTS/PITCH_TRANSPOSE", 12.0)
    bw.add_mapping(f, 0, "CONTENTS/OUTPUT", 0.25, 0.0, 1.0, 1.0)
    bw.set_device_names(f, device_name="A much longer device name", preset_name="p")
    g = bw.parse(bw.dump(f))
    mp = bw.modulator_view(bw.get_modulator(g, 0))["members"]
    maps = [m for x in mp if x["kind"] == "modsource" for m in x["mappings"]]
    assert [(m["target"], m["amount"]) for m in maps] == [("CONTENTS/PITCH_TRANSPOSE", 12.0), ("CONTENTS/OUTPUT", 0.25)]
    assert bw.device_info(g)["name"] == "A much longer device name" and bw.check(g) == []

    fp = bw.load(os.path.join(ds, "6d621c1c-ab64-43b4-aea3-dad37e6f649c", "Default.bwpreset"))
    lp = bw.extract_module(fp, [m.get(bw.F_NAME) for m in bw.modules(fp) if m.get(bw.F_DEVNAME) == "Low-pass"][0])
    f = bw.clone(fx)
    bw.insert_module_between(f, lp, 0, 1)
    g = bw.parse(bw.dump(f))
    assert len(bw.modules(g)) == 3 and len(bw.cables(g)) == 2 and bw.check(g) == []

    vib = bw.extract_modulator(pg, 0)
    f = bw.clone(flt)
    m = bw.add_modulator(f, vib)
    bw.add_mapping(f, m.get(bw.F_NAME), "CONTENTS/RESONANCE", 0.2, 0.0, 1.0, 0.5)
    g = bw.parse(bw.dump(f))
    assert len(bw.modulators(g)) == 1 and bw.check(g) == []
    assert "c" in "".join(bw.meta_get(g, "referenced_modulator_ids"))

    # the validator catches what Bitwig refuses / ignores
    f = bw.clone(fx)
    bw.get_module(f, 1).fields = [x for x in bw.get_module(f, 1).fields if x.id != bw.F_TYPE_UUID]
    assert any("required" in p for p in bw.check(f))
    f = bw.clone(fx)
    bw.member(bw.get_module(f, 1), "IN").set(bw.F_PORT_SRC, "CONTENTS/MODULES/99/CONTENTS/OUT")
    assert any("unknown source" in p for p in bw.check(f))
    print("all offline tests passed")


if __name__ == "__main__":
    main()
