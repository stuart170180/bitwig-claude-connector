"""Greedy minimisation of the Polymer crash: keep the added module, remove existing modules one at a time; keep each removal that
still crashes the engine. The smallest crashing patch points at what the engine trips over. Fully automatic (crashes are recovered)."""
import json
import sys
import time

import lab
import variants
from lab import bw, ds

LOGF = lab.OUT.parent / "bisect_log.json"


def remove_module(f, mid):
    mo = bw.modules_obj(f)
    lst = mo.node(bw.F_LIST).v
    lst[:] = [m for m in lst if not (isinstance(m, bw.Obj) and m.get(bw.F_NAME) == str(mid))]
    for m in lst:
        for p in bw.contents_list(m):
            if p.cls == bw.C_PORT and f"/MODULES/{mid}/" in (p.get(bw.F_PORT_SRC) or ""):
                p.set(bw.F_PORT_SRC, "")


def build(removed, add=True):
    f = bw.load(ds("8f58138b"))
    dev = bw.device_obj(f)
    dev.get(0x1a85).node(0x1a7e).v = []                      # remote pages (already shown not to matter) so removals cannot dangle
    for mid in removed:
        remove_module(f, mid)
    if add:
        bw.add_module(f, variants.poly_lowpass_template(), x=6, y=4)
    name = "B_" + ("_".join(map(str, removed)) or "none") + ("" if add else "_noadd")
    p = lab.OUT / (name[:80] + ".bwpreset")
    bw.save(f, p)
    return p


def crashed(r):
    return r.get("engine_died_after_s") is not None


def run():
    log, removed = [], []
    ids = [i for i in range(18, 0, -1)]
    for mid in ids:
        trial = removed + [mid]
        r = lab.case(f"remove {trial}", build(trial), watch=9)
        entry = {"removed": trial, "devices_added": r["devices_added"], "crashed": crashed(r)}
        log.append(entry)
        if r["devices_added"] == 0 and not crashed(r):       # loader refused: this removal is not allowed, keep the module
            entry["verdict"] = "refused"
        elif crashed(r):
            removed = trial                                   # still crashes without that module: it was not needed
            entry["verdict"] = "still crashes -> removed for good"
        else:
            entry["verdict"] = "NO CRASH -> this module matters"
        LOGF.write_text(json.dumps({"kept_removed": removed, "log": log}, indent=1))
    print("MINIMAL CRASHING PATCH removes:", removed, "keeps:", [i for i in range(19) if i not in removed], flush=True)


if __name__ == "__main__":
    run()
