"""Open Bitwig Remote automatically when you log in to Windows (no console window, no admin needed).

    python manage.py autostart            install (puts BitwigRemote.vbs in your Startup folder)
    python manage.py autostart --remove   uninstall
    python manage.py autostart --status   show whether it is installed and whether the app is running

Uses pythonw.exe so nothing but the app window appears."""
import os
import sys
from pathlib import Path

from bwmcp.core import appbridge, paths

STARTUP = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup"
LAUNCHER = STARTUP / "BitwigRemote.vbs"
OLD = STARTUP / "BitwigLiveMonitor.vbs"      # the web monitor's launcher from before the native app


def pythonw() -> str:
    p = Path(sys.executable).with_name("pythonw.exe")
    return str(p if p.exists() else sys.executable)


def vbs() -> str:
    cmd = f'""{pythonw()}"" ""{paths.ROOT / "BitwigRemote.pyw"}""'
    return f'Set sh = CreateObject("WScript.Shell")\nsh.CurrentDirectory = "{paths.ROOT}"\nsh.Run "{cmd}", 1, False\n'


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "--remove":
        LAUNCHER.unlink(missing_ok=True)
        print("removed", LAUNCHER)
    elif mode == "--status":
        print("installed:", LAUNCHER.exists(), "| app running:", appbridge.read_latest() is not None)
    else:
        OLD.unlink(missing_ok=True)
        LAUNCHER.write_text(vbs(), encoding="utf-8")
        print("installed", LAUNCHER, "- Bitwig Remote opens at your next login.")


if __name__ == "__main__":
    main()
