"""Sample library index (Bitwig packages, Splice, user folders) with metadata parsed from names."""
import json
import os
import re
import time
import wave
from pathlib import Path

HERE = Path(__file__).parent
CACHE = HERE / "sample_index.json"
CONFIG = HERE / "sample_folders.json"
MAX_AGE = 24 * 3600
AUDIO_EXTS = {".wav", ".aif", ".aiff", ".flac", ".mp3", ".ogg"}
DEFAULT_FOLDERS = [
    os.path.expandvars(r"%LOCALAPPDATA%\Bitwig Studio\installed-packages"),
    os.path.expandvars(r"%USERPROFILE%\Documents\Splice"),
    os.path.expandvars(r"%USERPROFILE%\Music"),
]

CATEGORIES = {  # first match wins; checked against lowercased path
    "808": ["808"], "kick": ["kick", "kck", "bd_", "bassdrum"], "snare": ["snare", "snr", "sd_"],
    "clap": ["clap", "clp"], "hat": ["hihat", "hi-hat", "hi hat", "hat", "hh_"], "cymbal": ["cymbal", "crash", "ride"],
    "tom": ["tom"], "perc": ["perc", "shaker", "conga", "bongo", "rim", "tamb", "cowbell", "clave"],
    "drum loop": ["drum loop", "drumloop", "drum_loop", "break", "top loop", "groove"],
    "bass": ["bass", "sub"], "vocal": ["vocal", "vox", "voice", "acapella", "chant"],
    "guitar": ["guitar", "gtr"], "piano": ["piano", "keys", "rhodes", "wurli"], "pad": ["pad", "atmos", "drone", "texture"],
    "synth": ["synth", "lead", "pluck", "arp", "chord", "stab"], "strings": ["string", "violin", "cello"],
    "brass": ["brass", "horn", "trumpet", "sax"], "fx": ["fx", "riser", "impact", "sweep", "noise", "whoosh", "downlifter"],
}
_KEY_RE = re.compile(r"(?:^|[ _\-(])([A-G](?:#|b|♯|♭)?)\s?(maj|min|minor|major|m)?(?=$|[ _\-).])", re.I)
_BPM_RE = re.compile(r"(?:^|[ _\-(])(\d{2,3})\s?(?:bpm)?(?=$|[ _\-).])", re.I)


def folders():
    if CONFIG.exists():
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    return DEFAULT_FOLDERS


def add_folder(path: str):
    p = os.path.abspath(os.path.expandvars(path))
    if not os.path.isdir(p):
        raise ValueError(f"not a folder: {p}")
    fs = folders()
    if p not in fs:
        fs.append(p)
        CONFIG.write_text(json.dumps(fs, indent=1), encoding="utf-8")
    return fs


def _meta(path: Path, root: str):
    stem = path.stem
    low = str(path).lower()
    bpm = None
    for m in _BPM_RE.finditer(stem):
        v = int(m.group(1))
        if 60 <= v <= 200 and ("bpm" in stem.lower() or "loop" in low or v not in (808, 909)):
            bpm = v
            break
    key = None
    for m in _KEY_RE.finditer(stem):
        root_note, q = m.group(1), (m.group(2) or "").lower()
        if len(stem) > 2:
            key = root_note[0].upper() + root_note[1:].replace("♯", "#").replace("♭", "b") + (
                "m" if q in ("m", "min", "minor") else "")
    cat = next((c for c, words in CATEGORIES.items() if any(w in low for w in words)), "other")
    name_low = stem.lower()
    if "loop" in name_low:
        kind = "loop"
    elif "one shot" in name_low or "one-shot" in name_low or "oneshot" in name_low:
        kind = "one-shot"
    else:
        kind = "loop" if ("loop" in low or bpm) and cat not in ("kick", "snare", "clap", "808") else "one-shot"
    rel = os.path.relpath(path, root).split(os.sep)
    pack = rel[2] if "installed-packages" in root and len(rel) > 3 else rel[0] if len(rel) > 1 else os.path.basename(root)
    if "Splice" in root and "packs" in rel:
        pack = rel[rel.index("packs") + 1] if rel.index("packs") + 1 < len(rel) - 1 else pack
    return {"name": stem, "path": str(path), "pack": pack, "category": cat, "kind": kind, "bpm": bpm, "key": key}


def index(refresh: bool = False):
    if not refresh and CACHE.exists() and time.time() - CACHE.stat().st_mtime < MAX_AGE:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    items = []
    for root in folders():
        if not os.path.isdir(root):
            continue
        for dirpath, _, files in os.walk(root):
            for f in files:
                p = Path(dirpath, f)
                if p.suffix.lower() in AUDIO_EXTS:
                    items.append(_meta(p, root))
    CACHE.write_text(json.dumps(items), encoding="utf-8")
    return items


def duration(path: str):
    try:
        with wave.open(path) as w:
            return round(w.getnframes() / w.getframerate(), 2)
    except Exception:
        return None


def search(query: str = "", category: str | None = None, kind: str | None = None, bpm: float | None = None,
           bpm_tolerance: float = 3, key: str | None = None, pack: str | None = None, limit: int = 20):
    words = query.lower().split()
    res = []
    for it in index():
        if category and it["category"] != category.lower():
            continue
        if kind and it["kind"] != kind:
            continue
        if pack and pack.lower() not in it["pack"].lower():
            continue
        if bpm and not (it["bpm"] and (abs(it["bpm"] - bpm) <= bpm_tolerance or abs(it["bpm"] * 2 - bpm) <= bpm_tolerance
                                         or abs(it["bpm"] / 2 - bpm) <= bpm_tolerance)):
            continue
        if key and (it["key"] or "").lower() != key.lower():
            continue
        hay = (it["name"] + " " + it["pack"] + " " + it["category"]).lower()
        if words and not all(w in hay for w in words):
            continue
        score = 0 if words and all(w in it["name"].lower() for w in words) else 1
        res.append((score, it["name"].lower(), it))
    res.sort(key=lambda x: (x[0], x[1]))
    return [r[2] for r in res[:limit]]


def resolve(name_or_path: str):
    if os.path.isfile(name_or_path):
        return name_or_path
    hits = search(name_or_path, limit=1)
    if not hits:
        raise ValueError(f"no sample matching {name_or_path!r} (try search_samples)")
    return hits[0]["path"]
