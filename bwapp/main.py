"""Entry point: python -m bwapp.main   (or double-click BitwigRemote.pyw)."""
import ctypes
import sys

from PySide6.QtCore import QLockFile, QStandardPaths
from PySide6.QtWidgets import QApplication

from bwapp import theme
from bwapp.window import Main


def run():
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Caviio.BitwigRemote.2")
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setApplicationName("Bitwig Remote")
    lock = QLockFile(QStandardPaths.writableLocation(QStandardPaths.TempLocation) + "/bitwig_remote_app.lock")
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):                       # a copy is already open: do not start a second capture
        return 0
    theme.apply(app)
    w = Main()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(run())
