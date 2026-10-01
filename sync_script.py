"""Keep the Bitwig controller script (which must live inside Bitwig's folder) mirrored into this repo.

    python sync_script.py             copy Bitwig's script files -> bitwig_script/ (what you run before committing)
    python sync_script.py --install   copy bitwig_script/ -> Bitwig's folder (new machine, or after a git checkout)
    python sync_script.py --check     report whether the two copies match (exit 1 if not)

Bitwig loads the script from SCRIPTS; the copy in bitwig_script/ is the one git tracks."""
import argparse
import filecmp
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_COPY = HERE / "bitwig_script"
SCRIPTS = Path.home() / "Documents" / "Bitwig Studio" / "Controller Scripts" / "BitwigMCP"


def js_files(folder: Path):
    return sorted(p.name for p in folder.glob("*.js")) if folder.exists() else []


def differences():
    """(only in Bitwig, only in repo, differing) file-name lists."""
    a, b = set(js_files(SCRIPTS)), set(js_files(REPO_COPY))
    diff = sorted(n for n in a & b if not filecmp.cmp(SCRIPTS / n, REPO_COPY / n, shallow=False))
    return sorted(a - b), sorted(b - a), diff


def copy(src: Path, dst: Path):
    dst.mkdir(parents=True, exist_ok=True)
    for stale in set(js_files(dst)) - set(js_files(src)):  # mirror deletions too
        (dst / stale).unlink()
    for n in js_files(src):
        shutil.copy2(src / n, dst / n)
    return js_files(dst)


def sync_to_repo() -> list:
    if not js_files(SCRIPTS):
        sys.exit(f"no controller script found in {SCRIPTS}")
    return copy(SCRIPTS, REPO_COPY)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    new, gone, diff = differences()
    if a.check:
        print("in sync" if not (new or gone or diff) else f"out of sync: only-in-Bitwig={new} only-in-repo={gone} changed={diff}")
        sys.exit(0 if not (new or gone or diff) else 1)
    if a.install:
        if not js_files(REPO_COPY):
            sys.exit("bitwig_script/ is empty - nothing to install")
        if (new or diff) and input(f"Bitwig's copy differs ({new + diff}). Overwrite it from the repo? [y/N] ").lower() != "y":
            sys.exit("cancelled")
        print("installed:", ", ".join(copy(REPO_COPY, SCRIPTS)))
    else:
        print("synced to bitwig_script/:", ", ".join(sync_to_repo()))
