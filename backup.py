"""Back up the whole Bitwig connector (Python server + the Bitwig controller script) into a timestamped zip.

    python backup.py            make a backup (keeps the newest 10)
    python backup.py --list     show existing backups
    python backup.py --restore <zip>   restore from a backup (asks first; current files are zipped as a safety copy)

Rebuildable caches (preset/sample indexes, __pycache__) are skipped."""
import argparse
import shutil
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = Path.home() / "Documents" / "Bitwig Studio" / "Controller Scripts" / "BitwigMCP"
BACKUPS = HERE.parent / "backups"
KEEP = 10
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git"}
SKIP_FILES = {"preset_index.json", "sample_index.json"}


def files():
    """(source path, path inside the zip) for everything worth keeping."""
    for root, arc in ((HERE, "bitwig_mcp"), (SCRIPTS, "controller_script_BitwigMCP")):
        if not root.exists():
            continue
        for p in sorted(root.rglob("*")):
            if p.is_dir() or SKIP_DIRS & set(p.parts) or p.name in SKIP_FILES:
                continue
            yield p, f"{arc}/{p.relative_to(root).as_posix()}"


def make_backup(tag="") -> Path:
    import sync_script
    sync_script.sync_to_repo()  # keep the git-tracked copy of the Bitwig script current
    BACKUPS.mkdir(exist_ok=True)
    path = BACKUPS / f"bitwig_connector_{time.strftime('%Y%m%d_%H%M%S')}{tag}.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for src, arc in files():
            z.write(src, arc)
    old = sorted(BACKUPS.glob("bitwig_connector_*.zip"))[:-KEEP]
    for o in old:
        o.unlink()
    return path


def restore(zip_path: str):
    zp = Path(zip_path)
    if not zp.exists():
        sys.exit(f"no such backup: {zp}")
    if input(f"Restore {zp.name}? This overwrites the current connector files (a safety backup is made first). [y/N] ").lower() != "y":
        sys.exit("cancelled")
    print("safety copy:", make_backup("_before_restore"))
    with zipfile.ZipFile(zp) as z:
        for info in z.infolist():
            top, _, rel = info.filename.partition("/")
            dest = {"bitwig_mcp": HERE, "controller_script_BitwigMCP": SCRIPTS}.get(top)
            if dest is None or not rel:
                continue
            target = (dest / rel).resolve()
            if dest.resolve() not in target.parents:  # refuse paths that escape the folder
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as s, open(target, "wb") as d:
                shutil.copyfileobj(s, d)
    print("restored. Restart Claude (and Bitwig will reload the controller script automatically).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--restore", metavar="ZIP")
    a = ap.parse_args()
    if a.list:
        for p in sorted(BACKUPS.glob("bitwig_connector_*.zip")):
            print(f"{p.name}  {p.stat().st_size / 1024:.0f} KB")
    elif a.restore:
        restore(a.restore)
    else:
        p = make_backup()
        n = sum(1 for _ in files())
        print(f"backed up {n} files -> {p} ({p.stat().st_size / 1024:.0f} KB)")
