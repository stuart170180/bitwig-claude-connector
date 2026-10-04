"""LFO modulator variants (timebase / rate) mapped to the Filter's POST_GAIN, to find out whether any setting makes the added modulator audible."""
import glob
import sys
from pathlib import Path

_R = Path(__file__).resolve()
while not (_R / "server.py").exists():
    _R = _R.parent
sys.path[:0] = [str(_R), str(_R / "research" / "grid")]
import modproof2 as m2  # noqa: E402
from bwmcp.devices import gridedit as ge  # noqa: E402

D = m2.D


def set_param(obj, name, value):
    node = ge.member(obj, name)
    for fid in (ge.F_REAL, ge.F_INT, ge.F_ENUM):
        n = node.node(fid)
        if n is None:
            continue
        if fid == ge.F_REAL:
            ge.set_f64(n, float(value))
        else:
            n.v = int(value)
        return
    raise ValueError(name)


def lfo_variant(name, amount=1.0, **params):
    f = ge.load(glob.glob(D + "4ccfc70e*/Default.bwpreset")[0])
    tpl = ge.modulator_templates([D.rstrip("/")])
    uuid, (nm, cat, file, mid) = next((u, v) for u, v in tpl.items() if v[0] == "LFO")
    m = ge.add_modulator(f, ge.extract_modulator(ge.load(file), mid))
    ge.add_mapping(f, m.get(ge.F_NAME), "CONTENTS/POST_GAIN", amount, rng_min=-24.0, rng_max=24.0, base=0.0)
    for k, v in params.items():
        set_param(m, k, v)
    assert ge.check(f) == [], ge.check(f)
    p = m2.mp.OUT / (name + ".bwpreset")
    ge.save(f, p)
    return p


if __name__ == "__main__":
    for tb in (0, 1, 2, 3):
        m2.measure(lfo_variant(f"mp_tb{tb}", TIMEBASE=tb, RATE=1.0), f"LFO->gain TIMEBASE={tb} RATE=1.0")
