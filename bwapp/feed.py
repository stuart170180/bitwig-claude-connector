"""Runs the existing capture + analysis in this process and publishes a frame ~15x a second (no HTTP, no browser)."""
from PySide6.QtCore import QObject, QTimer, Signal

from bwapp import engine as lm
from bwmcp.core import appbridge


class Feed(QObject):
    frame = Signal(dict)       # everything the blocks draw (see Analyzer.frame)
    status = Signal(str, str)  # (state, device or message)
    command = Signal(str, dict)  # from the MCP server: reset | target | quit

    def __init__(self, target="streaming"):
        super().__init__()
        self.target = target
        self.cap = lm.Capture(target)
        self.cap.start()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(66)
        self._last_status = None
        self._n = 0

    def _tick(self):
        a = self.cap.analyzer
        st = (self.cap.status, self.cap.device or "")
        if st != self._last_status:
            self._last_status = st
            self.status.emit(*st)
        if a is not None:
            f = a.frame(with_history=False)
            self.frame.emit(f)
            if self._n % 4 == 0:                               # ~4 Hz hand-over for the MCP server (live_monitor tool)
                appbridge.write_latest({**{k: v for k, v in f.items() if k not in ("scope", "history")},
                                        "status": st[0], "device": st[1]})
        self._n += 1
        if self._n % 4 == 0:
            c = appbridge.take()
            if c:
                self.command.emit(c["cmd"], c.get("args") or {})

    def history(self):
        a = self.cap.analyzer
        return a.frame(with_history=True).get("history", []) if a else []

    def reset(self):
        if self.cap.analyzer:
            self.cap.analyzer.reset()

    def set_target(self, name):
        self.target = self.cap.target = name
        if self.cap.analyzer:
            self.cap.analyzer.target = name
