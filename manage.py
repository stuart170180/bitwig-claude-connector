"""One front door for the project's maintenance commands.

    python manage.py install [--check|--dry-run|--uninstall|--autostart]   install / doctor / uninstall
    python manage.py sync [--install|--check]    mirror the Bitwig controller script <-> bitwig_script/
    python manage.py docs                        regenerate docs/TOOLS.md
    python manage.py monitor [--port 8780]       run the live monitor web page
    python manage.py autostart [--remove|--status]   start the monitor at Windows login
    python manage.py backup [--list|--restore ZIP]   zip backups
    python manage.py recover [--tracks N]        after an audio-engine crash: cancel the dialog, delete the crashed track, reactivate
    python manage.py test                        run the offline tests (live tests: python tests/live_test.py)"""
import runpy
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

COMMANDS = {
    "install": ("path", ROOT / "scripts" / "install.py"),
    "docs": ("path", ROOT / "scripts" / "make_docs.py"),
    "sync": ("module", "bwmcp.library.sync_script"),
    "monitor": ("module", "bwmcp.monitor.live_monitor"),
    "autostart": ("module", "bwmcp.monitor.autostart"),
    "backup": ("module", "bwmcp.library.backup"),
    "recover": ("module", "bwmcp.control.uiclick"),
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in {*COMMANDS, "test"}:
        print(__doc__)
        return 0 if len(sys.argv) < 2 else 2
    cmd, sys.argv = sys.argv[1], [sys.argv[0]] + sys.argv[2:]
    if cmd == "test":
        bad = [t.name for t in sorted((ROOT / "tests").glob("test_*.py")) if subprocess.run([sys.executable, str(t)]).returncode]
        print("FAILED:", bad) if bad else print("all offline tests passed")
        return 1 if bad else 0
    kind, target = COMMANDS[cmd]
    (runpy.run_path(str(target), run_name="__main__") if kind == "path" else runpy.run_module(target, run_name="__main__", alter_sys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
