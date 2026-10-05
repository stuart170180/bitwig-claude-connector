r"""Package Bitwig Remote (the desktop app) as a Windows program with PyInstaller.

    python packaging/build_app.py            build dist/Bitwig Remote/ (a folder with 'Bitwig Remote.exe')
    python packaging/build_app.py --installer   also build the installer (needs Inno Setup 6: winget install JRSoftware.InnoSetup)

The app needs no Python on the target PC. It runs the live monitor inside its own process, reads Bitwig's audio from the BW Remote VST3 (or loopback), and talks to Bitwig through the
Bitwig controller script (installed by the installer into Documents\Bitwig Studio\Controller Scripts\BitwigMCP). Build the VST3 plug-ins first (python manage.py vst) if the installer should carry them."""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
NAME = "Bitwig Remote"


def run(*cmd, **kw):
    print(">", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def build_exe():
    sep = ";"
    args = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", NAME,
        "--icon", ROOT / "bwmcp" / "monitor" / "assets" / "bitwig_remote.ico",
        "--paths", ROOT,
        "--add-data", f"{ROOT / 'bwmcp' / 'monitor' / 'live_monitor.html'}{sep}bwmcp/monitor",
        "--add-data", f"{ROOT / 'bwmcp' / 'monitor' / 'assets'}{sep}bwmcp/monitor/assets",
        "--add-data", f"{ROOT / 'data' / 'device_ranges.json'}{sep}data",
        "--add-data", f"{ROOT / 'data' / 'bitwig_device_ids.json'}{sep}data",
        "--add-data", f"{ROOT / 'data' / 'spire_params.json'}{sep}data",
        "--collect-submodules", "bwmcp", "--hidden-import", "server",
        "--collect-all", "webview", "--collect-all", "pyloudnorm", "--collect-all", "pyaudiowpatch",
        "--exclude-module", "matplotlib", "--exclude-module", "rapidocr_onnxruntime", "--exclude-module", "onnxruntime", "--exclude-module", "tkinter",
        "--distpath", DIST, "--workpath", ROOT / "build" / "pyinstaller", "--specpath", ROOT / "build",
        ROOT / "BitwigRemote.pyw",
    ]
    run(*args)
    out = DIST / NAME
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file()) / 1e6
    print(f"built {out}  ({size:.0f} MB)")
    return out


def build_installer():
    iscc = shutil.which("iscc") or next((str(p) for p in (Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"), Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
                                                         Path.home() / "AppData/Local/Programs/Inno Setup 6/ISCC.exe") if p.exists()), None)
    if not iscc:
        raise SystemExit("Inno Setup 6 not found: winget install JRSoftware.InnoSetup")
    run(iscc, ROOT / "packaging" / "BitwigRemote.iss")
    print("installer:", DIST / "BitwigRemote-Setup.exe")


if __name__ == "__main__":
    build_exe()
    if "--installer" in sys.argv:
        build_installer()
