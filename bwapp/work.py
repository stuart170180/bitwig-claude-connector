"""Run a slow call (anything that talks to Bitwig) off the GUI thread and deliver the result back on it."""
import threading

from PySide6.QtCore import QObject, Signal


class _Bus(QObject):
    done = Signal(object, object, object)     # callback, result, error


_bus = None


def _deliver(cb, result, error):
    cb(result, error)


def run(fn, callback, *args, **kwargs):
    """fn(*args) runs in a thread; callback(result, error) runs on the GUI thread (error is a string or None)."""
    global _bus
    if _bus is None:
        _bus = _Bus()
        _bus.done.connect(_deliver)

    def work():
        try:
            r, e = fn(*args, **kwargs), None
        except Exception as ex:  # noqa: BLE001
            r, e = None, str(ex) or ex.__class__.__name__
        _bus.done.emit(callback, r, e)
    threading.Thread(target=work, daemon=True).start()
