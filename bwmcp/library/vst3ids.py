"""Find VST3 class IDs on this PC from the plug-ins' own moduleinfo.json (a public file inside every modern .vst3 bundle)."""
import json
import os
import re
from pathlib import Path


def roots():
    base = Path(os.environ.get("CommonProgramFiles", r"C:\Program Files\Common Files")) / "VST3"
    extra = [Path(p) for p in os.environ.get("BW_VST3_PATHS", "").split(os.pathsep) if p]
    return [base, *extra]


def scan():
    """[{name, bundle, cid}] for the Audio Module class of every plug-in that ships a moduleinfo.json."""
    found = []
    for root in roots():
        if not root.exists():
            continue
        for mi in root.rglob("moduleinfo.json"):
            try:
                data = json.loads(re.sub(r",\s*([}\]])", r"\1", mi.read_text(encoding="utf-8-sig")))
            except (OSError, ValueError):
                continue
            bundle = next((p for p in mi.parents if p.suffix.lower() == ".vst3"), mi.parent)
            for c in data.get("Classes", []):
                if "Audio Module" in c.get("Category", ""):
                    found.append({"name": c.get("Name", bundle.stem), "bundle": bundle.name, "cid": c["CID"]})
    return found


def find(name):
    n = name.lower()
    return [f for f in scan() if n in f["name"].lower() or n in f["bundle"].lower()]
