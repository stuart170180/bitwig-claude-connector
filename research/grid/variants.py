"""Variants of the D5 file (Polymer + an extra Low-pass), to find which part crashed the audio engine."""
from lab import OUT, bw, ds

POLY, FPLUS = ds("8f58138b"), ds("6d621c1c")


def fx_lowpass_template():
    fx = bw.load(FPLUS)
    mid = next(bw.module_view(m)["id"] for m in bw.modules(fx) if bw.module_view(m)["name"] == "Low-pass")
    return bw.extract_module(fx, mid)


def poly_lowpass_template():
    f = bw.load(POLY)
    mid = next(bw.module_view(m)["id"] for m in bw.modules(f) if bw.module_view(m)["name"].startswith("Low-pass MG"))
    return bw.extract_module(f, mid)


def build(name, fn):
    f = bw.load(POLY)
    fn(f)
    assert bw.check(f) == [], bw.check(f)
    p = OUT / f"{name}.bwpreset"
    bw.save(f, p)
    assert bw.dump(bw.load(p)) == p.read_bytes()
    return p


def v2(f):   # synth-native Low-pass MG between Pan (13) and Voice Level (15), placed next to Pan
    m = bw.add_module(f, poly_lowpass_template(), near=13)
    n = m.get(bw.F_NAME)
    bw.connect(f, 13, "OUT", n, "IN")
    bw.connect(f, n, "OUT", 15, "IN")


def v1(f):   # effects-family Low-pass added, NOT connected
    bw.add_module(f, fx_lowpass_template(), near=13)


def v0(f):   # exactly D5 (effects-family Low-pass wired between Pan and Voice Level), without the pitch canary
    m = bw.add_module(f, fx_lowpass_template())
    n = m.get(bw.F_NAME)
    bw.connect(f, 13, "OUT", n, "IN")
    bw.connect(f, n, "OUT", 15, "IN")


def all_files():
    return {"V2_poly_native_lowpass": build("V2_poly_native_lowpass", v2),
            "V1_fx_lowpass_unconnected": build("V1_fx_lowpass_unconnected", v1),
            "V0_D5_pure": build("V0_D5_pure", v0)}


# ---- round 2: placement inside the grid, and the audio-proof pair ------------------------------------------------------
def _set_param(f, mod, name, value):
    bw.set_f64(bw.member(mod, name).node(bw.F_REAL), value)


def lp_variant(x, y, wired, cutoff=None):
    def fn(f):
        m = bw.add_module(f, poly_lowpass_template(), x=x, y=y)
        n = m.get(bw.F_NAME)
        if cutoff is not None:
            mod = bw.get_module(f, n)
            _set_param(f, mod, "CUTOFF", cutoff)
        if wired:
            bw.connect(f, 13, "OUT", n, "IN")
            bw.connect(f, n, "OUT", 15, "IN")
    return fn


def round2():
    return {"T2_inside_unconnected": build("T2_inside_unconnected", lp_variant(6, 1, False)),
            "T3_inside_wired": build("T3_inside_wired", lp_variant(6, 1, True)),
            "A_open": build("A_open_cutoff144", lp_variant(6, 1, True, 144.0)),
            "A_closed": build("A_closed_cutoff20", lp_variant(6, 1, True, 20.0))}


# ---- effects Grid (accepted by the engine): Low-pass wired between Audio In and Audio Out ------------------------------
FXGRID = ds("d641f61b")


def fx_variant(cutoff=None, add=True):
    def fn(f):
        if not add:
            return
        ids = {bw.module_view(m)["name"]: bw.module_view(m)["id"] for m in bw.modules(f)}
        lp = fx_lowpass_template()
        m = bw.insert_module_between(f, lp, ids["Audio In"], ids["Audio Out"])
        if cutoff is not None:
            mod = bw.get_module(f, (m if isinstance(m, str) else m.get(bw.F_NAME)))
            _set_param(f, mod, "CUTOFF", cutoff)
    return fn


def build_fx(name, fn):
    f = bw.load(FXGRID)
    fn(f)
    assert bw.check(f) == [], bw.check(f)
    p = OUT / f"{name}.bwpreset"
    bw.save(f, p)
    assert bw.dump(bw.load(p)) == p.read_bytes()
    return p


def fx_files():
    return {"FX_control": build_fx("FX_control", fx_variant(add=False)),
            "FX_open": build_fx("FX_open_cutoff144", fx_variant(144.0)),
            "FX_closed": build_fx("FX_closed_cutoff20", fx_variant(20.0))}
