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
        self._seq = -1
        self.last = None

    def _tick(self):
        a = self.cap.analyzer
        st = (self.cap.status, self.cap.device or "")
        if st != self._last_status:
            self._last_status = st
            self.status.emit(*st)
        cap, f = self.cap, None
        if a is not None:
            if cap.frame_cache is None:
                f = a.frame(with_history=False)               # synthetic feeds (tests) that bypass the capture thread
            elif cap.frame_seq != self._seq:                  # a new block was analysed: draw it once (10 Hz), not the same frame again
                self._seq, f = cap.frame_seq, cap.frame_cache
        if f is not None:
            self.last = f
            self.frame.emit(f)
        self._n += 1
        if self._n % 4 == 0:                                   # ~4 Hz hand-over to the MCP server (live_monitor tool), even when the audio is stalled
            if self.last is not None:
                appbridge.write_latest({**{k: v for k, v in self.last.items() if k not in ("scope", "history")}, "status": st[0], "device": st[1]})
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
