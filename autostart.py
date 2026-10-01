"""Start the live monitor automatically when you log in to Windows (no console window, no admin needed).

    python autostart.py            install (puts BitwigLiveMonitor.vbs in your Startup folder)
    python autostart.py --remove   uninstall
    python autostart.py --status   show whether it is installed and whether the page is answering

Runs pythonw.exe so nothing pops up. Stop it with:  taskkill /im pythonw.exe  (or End task in Task Manager)."""
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PORT = 8780
STARTUP = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup"
LAUNCHER = STARTUP / "BitwigLiveMonitor.vbs"


def pythonw() -> str:
    p = Path(sys.executable).with_name("pythonw.exe")
    return str(p if p.exists() else sys.executable)


def up() -> bool:
    try:
        return urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=2).status == 200
    except Exception:
        return False


def vbs() -> str:
    # window style 0 = hidden; False = don't wait. Doubled quotes are VBScript's escape for ".
    cmd = f'""{pythonw()}"" ""{HERE / "live_monitor.py"}"" --port {PORT}'
    return ('Set sh = CreateObject("WScript.Shell")\n'
            f'sh.CurrentDirectory = "{HERE}"\n'
            f'sh.Run "{cmd}", 0, False\n')


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "--remove":
        LAUNCHER.unlink(missing_ok=True)
        print("removed", LAUNCHER)
    elif mode == "--status":
        print("installed:", LAUNCHER.exists(), "| page answering:", up())
    else:
        LAUNCHER.write_text(vbs(), encoding="utf-8")
        print("installed", LAUNCHER, "- starts at your next login.")
        if not up():
            subprocess.Popen(["wscript", str(LAUNCHER)])
            print("Started it now too.")
