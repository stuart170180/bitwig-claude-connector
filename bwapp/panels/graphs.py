"""pyqtgraph blocks: 60 s loudness history and the mid/side spectrum."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QVBoxLayout, QWidget

from bwapp import theme

pg.setConfigOptions(antialias=True, background=theme.PANEL, foreground=theme.DIM)


def _plot(title=None):
    w = pg.PlotWidget()
    w.showGrid(x=True, y=True, alpha=0.15)
    w.setMenuEnabled(False)
    return w


class History(QWidget):
    def __init__(self, feed):
        super().__init__()
        self.feed = feed
        self.t, self.mom, self.st = [], [], []
        w = _plot()
        w.setLabel("left", "LUFS")
        w.setYRange(-40, 0)
        self.target = pg.InfiniteLine(angle=0, pen=pg.mkPen(theme.WARN, style=pg.QtCore.Qt.DashLine))
        w.addItem(self.target)
        self.cm = w.plot(pen=pg.mkPen(theme.ACCENT, width=2), name="momentary")
        self.cs = w.plot(pen=pg.mkPen(theme.GOOD, width=2), name="short-term")
        QVBoxLayout(self).addWidget(w)
        self.layout().setContentsMargins(0, 0, 0, 0)
        feed.frame.connect(self.update_frame)

    def update_frame(self, f):
        h = f.get("history") or []
        for t, m, s in h:
            self.t.append(t)
            self.mom.append(np.nan if m is None else m)
            self.st.append(np.nan if s is None else s)
        self.t, self.mom, self.st = self.t[-600:], self.mom[-600:], self.st[-600:]
        if self.t:
            x = np.array(self.t) - self.t[-1]
            self.cm.setData(x, self.mom)
            self.cs.setData(x, self.st)
        self.target.setValue(f.get("target", {}).get("lufs", -14))


class Spectrum(QWidget):
    def __init__(self, feed):
        super().__init__()
        w = _plot()
        w.setLogMode(x=True, y=False)
        w.setXRange(np.log10(20), np.log10(20000), padding=0)
        ticks = [(np.log10(f), lab) for f, lab in ((30, "30"), (60, "60"), (100, "100"), (200, "200"), (500, "500"), (1000, "1k"),
                                                     (2000, "2k"), (5000, "5k"), (10000, "10k"), (20000, "20k"))]
        w.getAxis("bottom").setTicks([ticks])
        w.setYRange(-110, -10)
        w.setLabel("left", "dBFS")
        self.mid = w.plot(pen=pg.mkPen(theme.ACCENT, width=2), fillLevel=-120, brush=(77, 163, 255, 50))
        self.side = w.plot(pen=pg.mkPen(theme.WARN, width=2))
        QVBoxLayout(self).addWidget(w)
        self.layout().setContentsMargins(0, 0, 0, 0)
        feed.frame.connect(self.update_frame)

    def update_frame(self, f):
        s = f.get("spectrum")
        if s:
            x = np.log10(s["freqs"])
            self.mid.setData(x, np.clip(s["mid"], -120, 0))
            self.side.setData(x, np.clip(s["side"], -120, 0))
