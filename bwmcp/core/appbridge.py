"""File link between the MCP server and the Bitwig Remote app (two processes, no network): the app writes its latest measurements,
the server reads them and can leave one-line commands (reset, target, quit) for the app to pick up."""
import json
import os
import time

from bwmcp.core import paths

LATEST = paths.DATA / "app_latest.json"
CMD = paths.DATA / "app_cmd.json"


def _atomic(path, obj):
    paths.DATA.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj), encoding="utf-8")
    os.replace(tmp, path)


def write_latest(frame: dict):
    _atomic(LATEST, {**frame, "written": time.time()})


def read_latest(max_age: float = 3.0):
    """The app's newest frame, or None when the app is not running (file missing or older than max_age seconds)."""
    try:
        d = json.loads(LATEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if time.time() - d.get("written", 0) <= max_age else None


def send(cmd: str, **args):
    _atomic(CMD, {"cmd": cmd, "args": args, "at": time.time()})


def take():
    """App side: the pending command (and clear it), or None. Commands older than 10 s are ignored."""
    try:
        d = json.loads(CMD.read_text(encoding="utf-8"))
        CMD.unlink()
    except (OSError, ValueError):
        return None
    return d if time.time() - d.get("at", 0) < 10 else None
