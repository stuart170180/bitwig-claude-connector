"""The live remote as a desktop app: a native window (Edge WebView2 through pywebview) around the monitor page.

    python manage.py app                open the window (starts the monitor server first if it is not running)
    python manage.py app --shortcut     add a Start-menu shortcut "Bitwig Remote"
    python manage.py app --top          keep the window on top of Bitwig

The window is the same page as http://127.0.0.1:8780 (loudness, meters, tuner, master controls, compressors, chords and voicings)."""
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from bwmcp.core import paths

PORT = 8780
URL = f"http://127.0.0.1:{PORT}/"


def server_up() -> bool:
    try:
        return urllib.request.urlopen(URL, timeout=2).status == 200
    except Exception:
        return False


def ensure_server():
    """Start the monitor in the background if nothing answers; returns the process (or None when it was already running)."""
    if server_up():
        return None
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen([sys.executable, "-m", "bwmcp.monitor.live_monitor", "--port", str(PORT)], cwd=str(paths.ROOT),
                            creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    for _ in range(40):
        time.sleep(0.25)
        if server_up():
            return proc
    raise RuntimeError("the monitor server did not start")


def open_window(on_top: bool = False):
    import webview

    started = ensure_server()
    webview.create_window("Bitwig Remote", URL, width=1320, height=900, min_size=(520, 600), on_top=on_top, background_color="#111317")
    try:
        webview.start()
    finally:
        if started is not None:            # we started the server for this window: leave it running (autostart may rely on it)
            pass


def make_shortcut() -> Path:
    start = Path.home() / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs"
    lnk = start / "Bitwig Remote.lnk"
    pyw = Path(sys.executable).with_name("pythonw.exe")
    target = str(pyw if pyw.exists() else sys.executable)
    ps = (f'$s=(New-Object -ComObject WScript.Shell).CreateShortcut("{lnk}");$s.TargetPath="{target}";'
          f'$s.Arguments="manage.py app";$s.WorkingDirectory="{paths.ROOT}";$s.Description="Live remote for the Claude Bitwig connector";$s.Save()')
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    return lnk


if __name__ == "__main__":
    if "--shortcut" in sys.argv:
        print("created", make_shortcut())
    else:
        open_window(on_top="--top" in sys.argv)
