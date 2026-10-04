"""One-step installer for the Bitwig connector for Claude (Windows).

    python manage.py install               install everything, then check it
    python manage.py install --check         only check (a doctor: what works, what is missing)
    python manage.py install --dry-run       show what would happen, change nothing
    python manage.py install --uninstall     remove the Claude registration, the controller script and the autostart
    options: --no-deps  --no-mcp  --autostart  --scripts-dir PATH  --yes

What it does: installs the Python packages, copies the controller script into Bitwig's Controller Scripts folder,
registers the MCP server with Claude Code (claude mcp add ... --scope user), and optionally starts the live monitor at login.
Afterwards, one manual step in Bitwig: Settings > Controllers > Add controller > Claude > Bitwig MCP."""
import argparse
import filecmp
import importlib
import shutil
import socket
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]   # repository folder
sys.path.insert(0, str(HERE))

from bwmcp.core import paths  # noqa: E402

SRC = HERE / "bitwig_script"
SERVER = HERE / "server.py"
MCP_NAME = "bitwig"
MODULES = {"mcp": "mcp", "numpy": "numpy", "scipy": "scipy", "pyloudnorm": "pyloudnorm",
           "pyaudiowpatch": "PyAudioWPatch (live capture, optional)", "matplotlib": "matplotlib"}
OPTIONAL = {"pyaudiowpatch"}
STEPS = []


def say(ok, text, hint=""):
    mark = {True: "OK  ", False: "FAIL", None: "..  "}[ok]
    print(f"[{mark}] {text}" + (f"\n        -> {hint}" if hint and ok is not True else ""))
    STEPS.append(ok)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


# ---- checks -------------------------------------------------------------------------------------------------------
def check_python():
    ok = sys.version_info >= (3, 10)
    say(ok, f"Python {sys.version.split()[0]} ({sys.executable})", "Python 3.10 or newer is needed")
    return ok


def check_modules():
    allok = True
    for mod, label in MODULES.items():
        try:
            importlib.import_module(mod)
            say(True, f"package {label}")
        except Exception as e:
            opt = mod in OPTIONAL
            say(None if opt else False, f"package {label} not importable ({type(e).__name__})",
                f"pip install -r {HERE / 'requirements.txt'}")
            allok = allok and opt
    return allok


def check_bitwig():
    inst = paths.bitwig_install_dir()
    say(bool(inst), f"Bitwig Studio program folder: {inst}" if inst else "Bitwig Studio not found",
        "install Bitwig Studio, or set BITWIG_INSTALL_DIR")
    return bool(inst)


def script_state(dst: Path):
    want = sorted(p.name for p in SRC.glob("*.js"))
    have = sorted(p.name for p in dst.glob("*.js")) if dst.exists() else []
    missing = [n for n in want if n not in have]
    differ = [n for n in want if n in have and not filecmp.cmp(SRC / n, dst / n, shallow=False)]
    return want, missing, differ


def check_script(dst: Path):
    if not SRC.exists() or not list(SRC.glob("*.js")):
        say(False, "bitwig_script/ is missing from this download")
        return False
    want, missing, differ = script_state(dst)
    ok = not missing and not differ
    say(ok, f"controller script in {dst}" + ("" if ok else f" (missing {missing}, different {differ})"),
        "run: python manage.py install")
    return ok


def port_free(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def check_connection():
    """Talks to the running Bitwig through the controller script."""
    try:
        sys.path.insert(0, str(HERE))
        import server
        caps = server.bw.call("capabilities")
        say(True, f"Bitwig answers: controller script v{caps.get('version')}, missing API features: {caps.get('missing_apis') or 'none'}")
        return True
    except Exception as e:
        say(None, "Bitwig did not answer", f"open Bitwig and enable Settings > Controllers > Claude > Bitwig MCP ({str(e)[:120]})")
        return False


def claude_cli():
    return shutil.which("claude")


def mcp_registered():
    cli = claude_cli()
    if not cli:
        return None
    r = run([cli, "mcp", "get", MCP_NAME])
    return r.returncode == 0 and "Connected" in (r.stdout + r.stderr)


def check_mcp():
    st = mcp_registered()
    if st is None:
        say(None, "Claude Code CLI ('claude') not found on PATH", f"register by hand: claude mcp add --scope user {MCP_NAME} -- \"{sys.executable}\" \"{SERVER}\"")
    else:
        say(st, f"Claude MCP server '{MCP_NAME}' registered and connected", "run: python manage.py install")
    return bool(st)


def doctor(dst):
    print("\nChecking the installation\n")
    check_python()
    check_modules()
    check_bitwig()
    check_script(dst)
    check_mcp()
    check_connection()
    print()
    for port in (8765,):
        # Bitwig itself binds 8765 while the controller is active, so "in use" is the healthy state here.
        say(None, f"port {port} {'free (controller not active yet)' if port_free(port) else 'in use (Bitwig controller is listening)'}")
    print()


# ---- actions ------------------------------------------------------------------------------------------------------
def install_deps(dry):
    req = HERE / "requirements.txt"
    print(f"Installing Python packages from {req.name} ...")
    if dry:
        say(None, "would run: pip install -r requirements.txt")
        return True
    r = run([sys.executable, "-m", "pip", "install", "-r", str(req)])
    say(r.returncode == 0, "pip install -r requirements.txt", (r.stderr or r.stdout)[-400:])
    return r.returncode == 0


def install_script(dst: Path, dry):
    want, missing, differ = script_state(dst)
    print(f"Installing the controller script into {dst} ...")
    if dry:
        say(None, f"would copy {len(want)} files ({len(missing)} new, {len(differ)} changed)")
        return True
    dst.mkdir(parents=True, exist_ok=True)
    for n in differ:  # keep a copy of anything we overwrite
        shutil.copy2(dst / n, dst / (n + ".bak"))
    for n in want:
        shutil.copy2(SRC / n, dst / n)
    for stale in set(p.name for p in dst.glob("*.js")) - set(want):
        say(None, f"left alone: {stale} (not part of this version)")
    say(True, f"copied {len(want)} files" + (f" (backed up {len(differ)} changed ones as .bak)" if differ else ""))
    return True


def register_mcp(dry):
    cli = claude_cli()
    cmd = ["claude", "mcp", "add", "--scope", "user", MCP_NAME, "--", sys.executable, str(SERVER)]
    if not cli:
        say(None, "Claude Code CLI not found, skipping registration", "install Claude Code, then run: " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
        return False
    if dry:
        say(None, "would run: " + " ".join(cmd))
        return True
    run([cli, "mcp", "remove", "--scope", "user", MCP_NAME])  # replace an older registration with the right paths
    r = run([cli] + cmd[1:])
    say(r.returncode == 0, f"claude mcp add {MCP_NAME}", (r.stderr or r.stdout)[-300:])
    return r.returncode == 0


def unregister():
    cli = claude_cli()
    if cli:
        r = run([cli, "mcp", "remove", "--scope", "user", MCP_NAME])
        say(r.returncode == 0, "removed the Claude registration", (r.stderr or r.stdout)[-200:])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--no-deps", action="store_true")
    ap.add_argument("--no-mcp", action="store_true")
    ap.add_argument("--autostart", action="store_true", help="start the live monitor automatically at Windows login")
    ap.add_argument("--scripts-dir", help="Bitwig Controller Scripts target (default: Documents\\Bitwig Studio\\Controller Scripts\\BitwigMCP)")
    ap.add_argument("--yes", action="store_true", help="don't ask before uninstalling")
    a = ap.parse_args()
    dst = Path(a.scripts_dir) if a.scripts_dir else paths.scripts_dir()

    if a.check:
        doctor(dst)
        return 0 if all(s is not False for s in STEPS) else 1
    if a.uninstall:
        if not a.yes and input(f"Remove the Claude registration, {dst} and the monitor autostart? [y/N] ").lower() != "y":
            print("cancelled")
            return 1
        unregister()
        if dst.exists():
            shutil.rmtree(dst)
            say(True, f"removed {dst}")
        from bwmcp.monitor import autostart
        autostart.LAUNCHER.unlink(missing_ok=True)
        say(True, "removed the monitor autostart")
        return 0

    print("Installing the Bitwig connector for Claude\n")
    if not check_python():
        return 1
    if not a.no_deps:
        install_deps(a.dry_run)
    install_script(dst, a.dry_run)
    if not a.no_mcp:
        register_mcp(a.dry_run)
    if a.autostart:
        if a.dry_run:
            say(None, "would install the monitor autostart (python manage.py autostart)")
        else:
            from bwmcp.monitor import autostart
            autostart.LAUNCHER.parent.mkdir(parents=True, exist_ok=True)
            autostart.LAUNCHER.write_text(autostart.vbs(), encoding="utf-8")
            say(True, f"monitor autostart installed ({autostart.LAUNCHER.name})")
    if not a.dry_run:
        doctor(dst)
    print("Next steps")
    print("  1. In Bitwig: Settings > Controllers > Add controller > Claude > Bitwig MCP (once).")
    print("  2. For live measurements set Settings > Audio > Driver model to Windows Audio (WASAPI).")
    print("  3. Start a NEW Claude Code session; the Bitwig tools load when a session starts.")
    print("  4. Try: 'run health_check'. Live dashboard: double-click scripts/start_monitor.bat (http://127.0.0.1:8780).")
    return 0 if all(s is not False for s in STEPS) else 1


if __name__ == "__main__":
    sys.exit(main())
