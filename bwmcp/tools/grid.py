"""Grid patch editing: add modules to a Grid device by editing a copy of its preset file, then (optionally) load it and verify.

Proven live (docs/PRESET_FORMAT.md, section 11): a module added to an effects Grid or a Poly Grid processes audio. Guard rails come
from the crash tests: Polymer files with more than 19 modules crash Bitwig's audio engine, so Polymer is refused, and edited Grids
are capped at 32 modules (tested). Nothing in the original preset is modified; the edited copy goes to data/patched_presets/."""
import re
import time
from pathlib import Path

from bwmcp.core import paths
from bwmcp.core.bridge import bw, tool
from bwmcp.devices import gridedit as ge

BASES = {"fx": "d641f61b", "poly": "a33bba66"}      # factory Default presets: FX Grid, Poly Grid
MAX_MODULES = 32
OUT = paths.DATA / "patched_presets"


def _settings_dir() -> Path:
    inst = paths.bitwig_install_dir()
    return (inst or Path(r"C:\Program Files\Bitwig Studio")) / "Library" / "device-settings"


def _base_path(base: str) -> Path:
    if base.lower() in BASES:
        hits = list(_settings_dir().glob(BASES[base.lower()] + "*/Default.bwpreset"))
        if not hits:
            raise FileNotFoundError(f"factory preset for '{base}' not found in {_settings_dir()}")
        return hits[0]
    p = Path(base)
    if p.suffix.lower() != ".bwpreset" or not p.exists():
        raise ValueError("base must be 'fx', 'poly' or the path of a plain (v0002) .bwpreset file")
    return p


def _templates():
    return ge.module_templates([str(_settings_dir())])


def _find_template(name: str):
    tpl = _templates()
    want = name.strip().lower()
    exact = [(u, v) for u, v in tpl.items() if v[0].lower() == want]
    part = [(u, v) for u, v in tpl.items() if want in v[0].lower()]
    hits = exact or part
    if not hits:
        raise ValueError(f"no module called '{name}'. Available: {sorted({v[0] for v in tpl.values()})}")
    if len(hits) > 1 and not exact:
        raise ValueError(f"'{name}' is ambiguous: {sorted(v[0] for _, v in hits)}")
    uuid, (nm, cat, file, mid) = hits[0]
    src = ge.load(file)
    return ge.extract_module(src, mid), nm


def _set_param(f, mod_id, name, value):
    mod = ge.get_module(f, mod_id)
    for kind, fid in (("real", ge.F_REAL), ("int", ge.F_INT)):
        try:
            node = ge.member(mod, name).node(fid)
        except Exception:
            continue
        if kind == "real":
            ge.set_f64(node, float(value))
        else:
            node.v = int(value)
        return kind
    raise ValueError(f"module has no real/int parameter '{name}'")


@tool()
def grid_templates() -> dict:
    """The Grid modules that grid_add_module can add (name and category), harvested from Bitwig's factory presets."""
    out = {}
    for _u, (name, cat, _file, _id) in _templates().items():
        out.setdefault(cat, []).append(name)
    return {k: sorted(set(v)) for k, v in sorted(out.items())}


@tool()
def grid_inspect(base: str = "fx") -> str:
    """Readable view of a Grid preset: device values, modulators, every module with its parameters, and all cables.
    base = 'fx' (FX Grid), 'poly' (Poly Grid) or the path of a plain .bwpreset file."""
    return ge.grid_inspect(ge.load(_base_path(base)))


@tool()
def grid_add_module(base: str, module: str, between: list | None = None, params: dict | None = None, x: int | None = None,
                    y: int | None = None, name: str | None = None, load_to_track: int | None = None) -> dict:
    """Add one module to a copy of a Grid preset (the original is never changed).
    base: 'fx' (FX Grid), 'poly' (Poly Grid) or a plain .bwpreset path. module: a name from grid_templates (e.g. 'Low-pass').
    between: [source, destination] module names or ids to wire the new module into the signal path, e.g. ['Audio In', 'Audio Out']
    (FX Grid) - the cable from source to destination is replaced by source -> new -> destination. params: {PARAMETER: value} on the new
    module, e.g. {'CUTOFF': 20} (look at grid_inspect for names and units). x, y: grid cell (default: next free spot).
    load_to_track: also insert the edited device on that track and check that Bitwig accepted it and the audio engine stayed up.
    Refuses Polymer files (more than 19 modules crash the audio engine) and anything over 32 modules."""
    src = _base_path(base)
    f = ge.load(src)
    dev = ge.device_info(f)
    dname = str(dev.get("name") if isinstance(dev, dict) else dev)
    count = len(ge.modules(f))
    if "polymer" in dname.lower():
        raise ValueError("Polymer is refused: an added module takes it past 19 modules and crashes Bitwig's audio engine. Use 'poly' or 'fx'.")
    if count + 1 > MAX_MODULES:
        raise ValueError(f"this Grid already has {count} modules; the tested limit is {MAX_MODULES}")
    tpl, tname = _find_template(module)
    m = ge.add_module(f, tpl, x=x, y=y)
    new_id = m.get(ge.F_NAME)
    if between:
        ids = {}
        for mv in (ge.module_view(q) for q in ge.modules(f)):
            ids.setdefault(mv["name"].lower(), mv["id"])
            ids[mv["id"]] = mv["id"]

        def resolve(v):
            k = str(v).lower()
            if k not in ids:
                raise ValueError(f"no module '{v}' in this Grid (have {sorted(set(ids))})")
            return ids[k]

        s, d = resolve(between[0]), resolve(between[1])
        ge.connect(f, s, "OUT", new_id, "IN")
        ge.connect(f, new_id, "OUT", d, "IN")
    applied = {}
    for pname, value in (params or {}).items():
        applied[pname] = {"value": value, "kind": _set_param(f, new_id, pname, value)}
    problems = ge.check(f)
    if problems:
        raise RuntimeError(f"the edited preset failed validation: {problems[:3]}")
    OUT.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", name or f"{dname}_{tname}_{new_id}")
    out = OUT / f"{stem}.bwpreset"
    ge.save(f, out)
    assert ge.dump(ge.load(out)) == out.read_bytes()
    result = {"file": str(out), "device": dname, "added": tname, "module_id": new_id, "modules_now": count + 1,
              "wired": between, "params": applied}
    if load_to_track is not None:
        result["load"] = _load_and_verify(out, load_to_track)
    return result


def _engine_up():
    try:
        return bool(bw.call("engine", action="state")["active"])
    except Exception:
        return None


def _load_and_verify(path, track_index, watch=6.0):
    bw.call("select_track", track_index=track_index)
    time.sleep(0.5)
    before = len(bw.call("list_devices")["devices"])
    bw.call("insert_file", path=str(path))
    t0 = time.time()
    while time.time() - t0 < watch:
        time.sleep(0.4)
        if _engine_up() is not True:
            return {"accepted": False, "engine_crashed": True,
                    "next": "the audio engine died: run engine_recover; if Bitwig shows a crash dialog press Cancel, delete the track, then reactivate"}
    after = len(bw.call("list_devices")["devices"])
    return {"accepted": after > before, "engine_crashed": False, "devices": after,
            "note": None if after > before else "Bitwig refused the file (see its log)"}
