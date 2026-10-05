"""Spire (Reveal Sound) presets for the Spire-1.5 plug-in inside Bitwig.

A Spire preset (.spf2) is plain JSON: {"parameters": {"osc1_type": 0.2, "flt1_cut": 0.63, ...}} with the SAME parameter names and 0..1 values that Bitwig
exposes for the plug-in (deep_params shows all 500). So a preset is loaded without touching Spire's own window: every named value is written with deep_set.
Banks live in %APPDATA%\\RevealSound\\Banks (thousands of presets, many trance soundsets). The index only stores file paths, so building it is fast."""
import json
import os
import re
from pathlib import Path

from bwmcp.core import paths

BANKS = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))) / "RevealSound" / "Banks"
INDEX = paths.DATA / "spire_index.json"
NOT_SET = {"mode", "poly", "bend_up", "bend_dn"}      # not exposed to the host; Spire keeps its own


def build_index(force=False):
    if INDEX.exists() and not force:
        return json.loads(INDEX.read_text(encoding="utf-8"))
    rows = []
    for root, _dirs, files in os.walk(BANKS):
        for f in files:
            if f.lower().endswith(".spf2"):
                p = Path(root) / f
                rel = p.relative_to(BANKS)
                rows.append({"name": p.stem, "bank": rel.parts[0] if len(rel.parts) > 1 else "", "sub": "/".join(rel.parts[1:-1]), "path": str(p)})
    INDEX.write_text(json.dumps(rows), encoding="utf-8")
    return rows


def search(query="", bank=None, limit=30):
    """Words in the query must all appear in the bank/folder/preset name (case-insensitive)."""
    words = [w for w in re.split(r"\s+", query.lower().strip()) if w]
    out = []
    for r in build_index():
        hay = f"{r['bank']} {r['sub']} {r['name']}".lower()
        if bank and bank.lower() not in r["bank"].lower():
            continue
        if all(w in hay for w in words):
            out.append(r)
            if len(out) >= limit:
                break
    return out


def read_preset(path) -> dict:
    d = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
    if "parameters" not in d:
        raise ValueError("not a Spire .spf2 preset (no 'parameters')")
    return d


def apply(bw, deep, track_index, device_index, path):
    """Write every parameter of the preset into the Spire at track_index/device_index. Returns counts and a read-back check."""
    d = read_preset(path)
    deep.goto(track_index, device_index)
    ids, offset = {}, 0
    while True:
        r = deep.params(None, 100, offset)
        for p in r["params"]:
            ids[p["name"]] = p["id"]
        if len(r["params"]) < 100:
            break
        offset += 100
    values, skipped = {}, []
    for name, v in d["parameters"].items():
        if name in ids and name not in NOT_SET and isinstance(v, (int, float)):
            values[ids[name]] = max(0.0, min(1.0, float(v)))
        else:
            skipped.append(name)
    items = list(values.items())
    for i in range(0, len(items), 80):
        deep.set_values(dict(items[i:i + 80]))
    import time
    time.sleep(1.0)                                    # the host reports the new values a moment after they were written
    check = {}
    for name in ("volume", "flt1_cut", "osc1_type", "osc1_ucnt", "env1_att"):
        if name in ids and ids[name] in values:
            got = deep.params(name, 5, 0)["params"]
            hit = next((p for p in got if p["name"] == name), None)
            if hit:
                check[name] = {"wanted": round(values[ids[name]], 3), "got": round(hit["value"], 3)}
    return {"preset": Path(path).stem, "bank": d.get("bank"), "author": d.get("author"), "tags": d.get("tags"), "set": len(values), "skipped": len(skipped), "check": check}
