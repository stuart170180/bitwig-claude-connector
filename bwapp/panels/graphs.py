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
    """60 s of momentary and short-term loudness. Fixed axes (auto-ranging re-laid the axis on every frame and made it feel sluggish)."""
    SPAN = 60.0

    def __init__(self, feed):
        super().__init__()
        self.feed = feed
        self.t = np.empty(0)
        self.mom = np.empty(0)
        self.st = np.empty(0)
        w = _plot()
        w.disableAutoRange()
        w.setMouseEnabled(False, False)
        w.setXRange(-self.SPAN, 0, padding=0)
        w.setYRange(-40, 0, padding=0)
        w.setLabel("left", "LUFS")
        w.setLabel("bottom", "seconds ago")
        w.getAxis("bottom").setTickSpacing(major=10, minor=5)
        w.getAxis("left").setTickSpacing(major=10, minor=5)
        self.target = pg.InfiniteLine(angle=0, pen=pg.mkPen(theme.WARN, style=pg.QtCore.Qt.DashLine))
        w.addItem(self.target)
        self.cm = w.plot(pen=pg.mkPen(theme.ACCENT, width=2), name="momentary", skipFiniteCheck=True)
        self.cs = w.plot(pen=pg.mkPen(theme.GOOD, width=2), name="short-term", skipFiniteCheck=True)
        QVBoxLayout(self).addWidget(w)
        self.layout().setContentsMargins(0, 0, 0, 0)
        feed.frame.connect(self.update_frame)

    def update_frame(self, f):
        t = f.get("t")
        if t is None:
            return
        if len(self.t) and t < self.t[-1]:                      # Reset pressed: the clock restarted
            self.t, self.mom, self.st = self.t[:0], self.mom[:0], self.st[:0]
        if len(self.t) == 0 or t > self.t[-1]:
            nan = lambda v: np.nan if v is None else v
            self.t = np.append(self.t, t)[-700:]
            self.mom = np.append(self.mom, nan(f.get("momentary")))[-700:]
            self.st = np.append(self.st, nan(f.get("short_term")))[-700:]
        x = self.t - self.t[-1]
        keep = x >= -self.SPAN
        self.cm.setData(x[keep], self.mom[keep], connect="finite")
        self.cs.setData(x[keep], self.st[keep], connect="finite")
        self.target.setValue(f.get("target", {}).get("lufs", -14))


class Spectrum(QWidget):
    def __init__(self, feed):
        super().__init__()
        w = _plot()
        w.disableAutoRange()                                    # auto-ranging on every frame costs more than the drawing
        w.setMouseEnabled(False, False)
        w.setXRange(np.log10(20), np.log10(20000), padding=0)
        ticks = [(np.log10(f), lab) for f, lab in ((30, "30"), (60, "60"), (100, "100"), (200, "200"), (500, "500"), (1000, "1k"),
                                                     (2000, "2k"), (5000, "5k"), (10000, "10k"), (20000, "20k"))]
        w.getAxis("bottom").setTicks([ticks])
        w.setYRange(-110, -10, padding=0)
        w.setLabel("left", "dBFS")
        self.mid = w.plot(pen=pg.mkPen(theme.ACCENT, width=2), fillLevel=-120, brush=(77, 163, 255, 50), skipFiniteCheck=True)
        self.side = w.plot(pen=pg.mkPen(theme.WARN, width=2), skipFiniteCheck=True)
        QVBoxLayout(self).addWidget(w)
        self.layout().setContentsMargins(0, 0, 0, 0)
        feed.frame.connect(self.update_frame)

    def update_frame(self, f):
        s = f.get("spectrum")
        if s:
            x = np.log10(s["freqs"])
            self.mid.setData(x, np.clip(s["mid"], -120, 0))
            self.side.setData(x, np.clip(s["side"], -120, 0))
