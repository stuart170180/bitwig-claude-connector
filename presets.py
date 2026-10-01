"""Index of Bitwig presets and built-in devices on disk, for loading sounds onto tracks by name."""
import json
import os
import time
from pathlib import Path

ROOTS = [
    Path(os.path.expandvars(r"%LOCALAPPDATA%\Bitwig Studio\installed-packages")),  # sound packages
    Path(os.path.expandvars(r"%USERPROFILE%\Documents\Bitwig Studio\Library")),    # user presets
    Path(r"C:\Program Files\Bitwig Studio\Library\devices"),                       # built-in devices
]
EXTS = {".bwpreset", ".bwdevice", ".multisample", ".vstpreset"}
CACHE = Path(__file__).with_name("preset_index.json")
MAX_AGE = 24 * 3600

# Default sounds per role and genre (names resolved through the index).
DEFAULT_KITS = {
    "house": "Legend 909 Normal Kit", "techno": "Legend 909 Multi Kit", "garage": "Legend 909 Normal Kit",
    "hiphop": "Legend 808 Normal Kit", "trap": "Legend 808 Heavyweight Kit", "dnb": "Legend 707 Kit",
    "breakbeat": "Legend 707 Kit", "rock": "California Kit Mid", "funk": "Kansas Kit Mid",
    "reggaeton": "Legend 808 Multi Kit",
}
DEFAULT_SOUNDS = {
    "bass": {"default": "Rippin' Bass", "techno": "Techno Stac Bass", "funk": "Funk Bottom End",
             "hiphop": "Grime Bass", "trap": "Grime Bass"},
    "chords": {"default": "Jupiter Pad", "house": "House Minor", "garage": "House Groove 5th",
               "funk": "Rhodes", "hiphop": "Rusty Rhodes", "techno": "Dub Techno Minor"},
    "lead": {"default": "Bobs Lead", "house": "Schnauss Pluck", "techno": "Dusty 101 Lead",
             "funk": "Clavinet", "hiphop": "Wide Pluck"},
}


def _scan():
    items = []
    for root in ROOTS:
        if not root.exists():
            continue
        for dirpath, _, files in os.walk(root):
            for f in files:
                p = Path(dirpath, f)
                if p.suffix.lower() in EXTS:
                    rel = p.relative_to(root).parts
                    items.append({"name": p.stem, "type": "device" if p.suffix == ".bwdevice" else "preset",
                                  "pack": rel[2] if len(rel) > 3 and "installed-packages" in str(root) else
                                  ("Built-in" if p.suffix == ".bwdevice" else "User"),
                                  "path": str(p)})
    return items


def index(refresh: bool = False):
    if not refresh and CACHE.exists() and time.time() - CACHE.stat().st_mtime < MAX_AGE:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    items = _scan()
    CACHE.write_text(json.dumps(items), encoding="utf-8")
    return items


def search(query: str, kind: str | None = None, limit: int = 25):
    """Rank presets: exact name > prefix > all words in name > words in name+pack."""
    words = query.lower().split()
    q = query.lower()
    scored = []
    for it in index():
        if kind and it["type"] != kind:
            continue
        name, hay = it["name"].lower(), (it["name"] + " " + it["pack"]).lower()
        if name == q:
            score = 0
        elif name.startswith(q):
            score = 1
        elif all(w in name for w in words):
            score = 2
        elif all(w in hay for w in words):
            score = 3
        else:
            continue
        scored.append((score, len(name), it))
    scored.sort(key=lambda x: (x[0], x[1]))
    return [it for _, _, it in scored[:limit]]


def resolve(name_or_path: str, kind: str | None = None):
    if os.path.isfile(name_or_path):
        return name_or_path
    hits = search(name_or_path, kind, 1)
    if not hits:
        raise ValueError(f"no preset or device matching {name_or_path!r} (try search_presets)")
    return hits[0]["path"]


def default_sound(role: str, genre: str) -> str:
    if role == "drums":
        return DEFAULT_KITS.get(genre, "Legend 909 Normal Kit")
    table = DEFAULT_SOUNDS[role]
    return table.get(genre, table["default"])
