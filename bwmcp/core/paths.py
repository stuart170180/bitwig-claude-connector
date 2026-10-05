"""Where Bitwig and its folders live on this machine (Windows). Everything can be overridden with environment variables:
BITWIG_MCP_SCRIPTS (the BitwigMCP controller script folder) and BITWIG_INSTALL_DIR (Bitwig's program folder)."""
import ctypes
import os
import sys
from ctypes import wintypes
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))   # True inside the packaged Bitwig Remote app (PyInstaller)
if FROZEN:
    ROOT = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))                                  # read-only bundle: shipped data, monitor page, icon
    DATA = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))) / "BitwigClaude" / "data"   # writable per-user data
    DATA.mkdir(parents=True, exist_ok=True)
    for _f in (ROOT / "data").glob("*.json") if (ROOT / "data").exists() else []:                       # first run: copy the shipped reference data
        if not (DATA / _f.name).exists():
            try:
                (DATA / _f.name).write_bytes(_f.read_bytes())
            except OSError:
                pass
else:
    ROOT = Path(__file__).resolve().parents[2]   # the repository folder
    DATA = ROOT / "data"                          # caches, saved recipes, bookmarks, snapshots (personal and rebuildable files)


def documents_dir() -> Path:
    """The real Documents folder (follows OneDrive or a moved Documents folder), falling back to ~/Documents."""
    if sys.platform == "win32":
        try:

            class GUID(ctypes.Structure):
                _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]

            fid = GUID(0xFDD39AD0, 0x238F, 0x46AF, (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
            out = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(fid), 0, None, ctypes.byref(out)) == 0:
                p = Path(out.value)
                ctypes.windll.ole32.CoTaskMemFree(out)
                if p.exists():
                    return p
        except Exception:
            pass
    return Path.home() / "Documents"


def scripts_dir() -> Path:
    """Folder Bitwig loads the BitwigMCP controller script from."""
    env = os.environ.get("BITWIG_MCP_SCRIPTS")
    if env:
        return Path(env)
    return documents_dir() / "Bitwig Studio" / "Controller Scripts" / "BitwigMCP"


def bitwig_install_dir():
    """Bitwig's program folder, or None when it can't be found."""
    cands = [os.environ.get("BITWIG_INSTALL_DIR"), r"C:\Program Files\Bitwig Studio",
             os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Bitwig Studio")]
    for c in cands:
        if c and (Path(c) / "Bitwig Studio.exe").exists():
            return Path(c)
    return None


def library_devices_dir() -> Path:
    inst = bitwig_install_dir()
    return (inst or Path(r"C:\Program Files\Bitwig Studio")) / "Library" / "devices"
