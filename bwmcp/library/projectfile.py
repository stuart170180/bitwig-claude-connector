"""Read-only inventory of a Bitwig project file (.bwproject), without opening it in Bitwig.

The file is Bitwig's binary container (see docs/PRESET_FORMAT.md). Names are stored as length-prefixed strings, so a scan of those
reliably finds the stock devices, audio files and plug-ins a project uses and the Bitwig version that saved it. It does NOT
recover the track tree, and parameter values are not read. Never modifies anything."""
import os
import re
from collections import Counter
from pathlib import Path

from bwmcp.core import paths

AUDIO_EXT = (".wav", ".aif", ".aiff", ".flac", ".mp3", ".ogg", ".m4a", ".wma")
PLUGIN_EXT = (".vst3", ".vst", ".clap", ".dll")
STRING_MARK = re.compile(rb"\x08\x00\x00[\x00-\x03].", re.S)   # type byte 8 + 4-byte big-endian length (< 1024)


def projects_dir() -> Path:
    return paths.documents_dir() / "Bitwig Studio" / "Projects"


def list_projects() -> list:
    """Project files (not auto-backups), newest first."""
    return sorted(projects_dir().glob("*/*.bwproject"), key=lambda p: p.stat().st_mtime, reverse=True)


def strings(data: bytes):
    """Every length-prefixed string in file order."""
    for m in STRING_MARK.finditer(data):
        n = int.from_bytes(m.group()[1:5], "big")
        if 4 <= n <= 1000:
            raw = data[m.end():m.end() + n]
            if all(32 <= c < 127 for c in raw):
                yield raw.decode("ascii")


def meta_string(data: bytes, key: bytes):
    """Value of a meta string stored right after its key (type byte 8 + length + text), or None."""
    i = data.find(key)
    if i < 0:
        return None
    j = i + len(key)
    if data[j:j + 1] != b"\x08":
        return None
    n = int.from_bytes(data[j + 1:j + 5], "big")
    return data[j + 5:j + 5 + n].decode("utf-8", "replace") if n < 200 else None


def _dir_size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0


def _base(s: str) -> str:
    return re.split(r"[\\/]", s)[-1]


def report(path=None) -> dict:
    found = list_projects()
    p = Path(path) if path else (found[0] if found else None)
    if p is None or not p.exists():
        raise FileNotFoundError("no .bwproject found (give a path)")
    if p.suffix.lower() != ".bwproject":
        raise ValueError("not a .bwproject file")
    data = p.read_bytes()
    if data[:4] != b"BtWg":
        raise ValueError("not a Bitwig container")
    devices, samples, presets, plugins = Counter(), set(), set(), set()
    for s in strings(data):
        low = s.lower()
        if low.endswith(".bwdevice") and ("\\" in s or "/" in s):
            devices[_base(s)[:-9]] += 1          # one per reference to the device file
        elif low.endswith(AUDIO_EXT):
            samples.add(s)
        elif low.endswith(".bwpreset"):
            presets.add(s)
        elif low.endswith(PLUGIN_EXT):
            plugins.add(s)
    absolute = sorted(s for s in samples if re.match(r"[A-Za-z]:[\\/]", s))
    root = p.parent
    return {
        "file": str(p), "size_mb": round(p.stat().st_size / 1e6, 1), "container": data[:16].decode("ascii", "replace"),
        "saved_by_bitwig": meta_string(data, b"application_version_name"),
        "stock_devices": dict(devices.most_common()),
        "audio_files": sorted({_base(s) for s in samples}),
        "audio_paths_checked": len(absolute), "audio_paths_missing": [s for s in absolute if not os.path.exists(s)],
        "plugins": sorted(plugins), "presets_used": sorted({_base(s) for s in presets})[:40],
        "folder_mb": {"master_recordings": round(_dir_size(root / "master-recordings") / 1e6, 1),
                      "bounce": round(_dir_size(root / "bounce") / 1e6, 1),
                      "auto_backups": round(_dir_size(root / "auto-backups") / 1e6, 1),
                      "audio": round(_dir_size(root / "audio") / 1e6, 1)},
        "limits": "string scan only: no track tree and no parameter values; read-only",
    }
