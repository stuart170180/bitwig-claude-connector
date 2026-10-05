"""Bitwig Remote - the live remote as a desktop app: a native window (Edge WebView2 through pywebview) around the monitor page.

    python manage.py app                open the app (starts the monitor service itself; a second launch just brings the first window forward)
    python manage.py app --shortcut     put "Bitwig Remote" (with its icon) on the Desktop and in the Start menu
    python manage.py app --top          keep the window on top of Bitwig
    BitwigRemote.pyw                    double-click version, no console window

Behaviour: one window at a time (named mutex), remembers its size and position (%APPDATA%\\BitwigClaude\\app.json), own taskbar identity and icon, and stops the
monitor service on exit if it was the app that started it (a service started by autostart keeps running). The page is the same as http://127.0.0.1:8780."""
import ctypes
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from bwmcp.core import paths

PORT = 8780
URL = f"http://127.0.0.1:{PORT}/"
TITLE = "Bitwig Remote"
APP_ID = "Caviio.BitwigRemote.1"
ASSETS = Path(__file__).resolve().parent / "assets"
ICON = ASSETS / "bitwig_remote.ico"
SETTINGS = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))) / "BitwigClaude" / "app.json"


def server_up() -> bool:
    try:
        return urllib.request.urlopen(URL, timeout=2).status == 200
    except Exception:
        return False


def ensure_server():
    """Start the monitor in the background if nothing answers; returns the process (None when it was already running)."""
    if server_up():
        return None
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    exe = Path(sys.executable).with_name("pythonw.exe")
    proc = subprocess.Popen([str(exe if exe.exists() else sys.executable), "-m", "bwmcp.monitor.live_monitor", "--port", str(PORT)], cwd=str(paths.ROOT),
                            creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    for _ in range(60):
        time.sleep(0.25)
        if server_up():
            return proc
    proc.terminate()
    raise RuntimeError("the monitor service did not start")


def load_settings() -> dict:
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(d: dict):
    try:
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS.write_text(json.dumps(d), encoding="utf-8")
    except OSError:
        pass


def _single_instance():
    """Returns a handle to keep alive, or None when another copy is already running (that one is brought to the front)."""
    k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
    handle = k32.CreateMutexW(None, False, "Local\\BitwigRemoteDesktopApp")
    if k32.GetLastError() == 183:                                  # ERROR_ALREADY_EXISTS
        hwnd = u32.FindWindowW(None, TITLE)
        if hwnd:
            u32.ShowWindow(hwnd, 9)
            u32.SetForegroundWindow(hwnd)
        return None
    return handle


def _set_window_icon():
    """Give the native window the app icon (pywebview only does this on some platforms)."""
    try:
        u32 = ctypes.windll.user32
        hwnd = u32.FindWindowW(None, TITLE)
        if not hwnd or not ICON.exists():
            return
        for size, which in ((16, 0), (32, 1)):                     # ICON_SMALL, ICON_BIG
            h = u32.LoadImageW(None, str(ICON), 1, size, size, 0x10)   # IMAGE_ICON, LR_LOADFROMFILE
            u32.SendMessageW(hwnd, 0x80, which, h)                 # WM_SETICON
    except Exception:
        pass


def open_window(on_top: bool = False):
    import webview

    guard = _single_instance()
    if guard is None:
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)   # own taskbar button + icon instead of Python's
    except Exception:
        pass
    started = ensure_server()
    cfg = load_settings()
    win = webview.create_window(TITLE, URL, width=int(cfg.get("w", 1320)), height=int(cfg.get("h", 900)),
                                x=cfg.get("x"), y=cfg.get("y"), min_size=(520, 600), on_top=on_top, background_color="#111317")

    def remember():
        try:
            save_settings({"x": win.x, "y": win.y, "w": win.width, "h": win.height})
        except Exception:
            pass

    win.events.closing += remember
    win.events.shown += lambda: _set_window_icon()
    try:
        webview.start()
    finally:
        if started is not None:                                    # this app started the service: stop it again (autostart-started services keep running)
            started.terminate()


def make_shortcut() -> list[Path]:
    pyw = Path(sys.executable).with_name("pythonw.exe")
    target = str(pyw if pyw.exists() else sys.executable)
    out = []
    for folder in (Path.home() / "Desktop", Path.home() / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs"):
        if not folder.exists():
            continue
        lnk = folder / "Bitwig Remote.lnk"
        ps = (f'$s=(New-Object -ComObject WScript.Shell).CreateShortcut("{lnk}");$s.TargetPath="{target}";$s.Arguments="manage.py app";'
              f'$s.WorkingDirectory="{paths.ROOT}";$s.IconLocation="{ICON}";$s.Description="Live remote for the Claude Bitwig connector";$s.Save()')
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
        out.append(lnk)
    return out


if __name__ == "__main__":
    if "--shortcut" in sys.argv:
        for p in make_shortcut():
            print("created", p)
    else:
        open_window(on_top="--top" in sys.argv)
