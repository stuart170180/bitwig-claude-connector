"""Entry point: python -m bwapp.main   (or double-click BitwigRemote.pyw).

Never fails silently: a second launch brings the running window forward, and any start-up error is shown in a dialog and written to
%APPDATA%\\BitwigClaude\\app_error.log (pythonw has no console)."""
import ctypes
import os
import sys
import time
import traceback
from pathlib import Path

LOG = Path(os.environ.get("APPDATA", str(Path.home()))) / "BitwigClaude" / "app_error.log"


def log(text):
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}\n")
    except OSError:
        pass


def fail(app, err):
    """Show the problem instead of exiting without a window."""
    text = "".join(traceback.format_exception(type(err), err, err.__traceback__))
    log(text)
    try:
        from PySide6.QtWidgets import QMessageBox
        box = QMessageBox(QMessageBox.Critical, "Bitwig Remote could not start", f"{err}\n\nDetails were saved to:\n{LOG}")
        box.exec()
    except Exception:  # noqa: BLE001
        pass
    return 1


def run():
    try:                                                     # a hard crash (native code) leaves its stack here instead of vanishing
        import faulthandler
        LOG.parent.mkdir(parents=True, exist_ok=True)
        faulthandler.enable(open(LOG.with_name("app_crash.log"), "a", buffering=1))
    except Exception:  # noqa: BLE001
        pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Caviio.BitwigRemote.2")
    except Exception:  # noqa: BLE001
        pass
    app = None
    try:
        from PySide6.QtCore import QLockFile, QStandardPaths
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication
        app = QApplication(sys.argv)
        app.setApplicationName("Bitwig Remote")
        app.setWindowIcon(QIcon(str(Path(__file__).parent / "assets" / "bitwig_remote.ico")))
        lock = QLockFile(QStandardPaths.writableLocation(QStandardPaths.TempLocation) + "/bitwig_remote_app.lock")
        lock.setStaleLockTime(0)
        if not lock.tryLock(100):                   # a copy is already open: ask it to come to the front (it may be minimised or behind Bitwig)
            from bwmcp.core import appbridge
            appbridge.send("raise")
            log("second launch: asked the running copy to come forward")
            return 0
        from bwapp import theme
        from bwapp.window import Main
        theme.apply(app)
        w = Main()
        w.show()
        w.bring_forward()
        return app.exec()
    except Exception as e:  # noqa: BLE001
        return fail(app, e)


if __name__ == "__main__":
    sys.exit(run())
