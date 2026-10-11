"""BW Remote VST3 link card: the numbers measured inside Bitwig and its 24-band spectrum."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from bwapp import theme


class VstCard(QWidget):
    FIELDS = ["Peak L / R", "Momentary", "Correlation", "Width", "Host", "Link"]

    def __init__(self, feed=None):
        super().__init__()
        self.chip = QLabel("waiting for the plug-in")
        self.chip.setProperty("role", "dim")
        grid = QGridLayout()
        self.vals = {}
        for i, name in enumerate(self.FIELDS):
            cap = QLabel(name.upper())
            cap.setStyleSheet(f"color:{theme.DIM};font-size:10px")
            v = QLabel("-")
            v.setStyleSheet("font-size:16px;font-weight:600")
            grid.addWidget(cap, 0, i)
            grid.addWidget(v, 1, i)
            self.vals[name] = v
        self.plot = pg.PlotWidget()
        self.plot.setMenuEnabled(False)
        self.plot.setYRange(-95, -33)
        self.bars = pg.BarGraphItem(x=np.arange(24), height=np.zeros(24), width=0.8, brush=theme.ACCENT)
        self.plot.addItem(self.bars)
        lay = QVBoxLayout(self)
        lay.addWidget(self.chip)
        lay.addLayout(grid)
        lay.addWidget(self.plot, 1)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(250)

    def poll(self):
        if not self.isVisible():
            return
        try:
            from bwmcp.analysis import vstfeed
            st = vstfeed.feed().status()
        except Exception as e:  # noqa: BLE001
            self.chip.setText(f"VST feed unavailable: {e}")
            return
        self.chip.setText(f"receiving (port {st.get('port')})" if st.get("alive") else "no signal: load BW Remote on the master")
        L = st.get("latest")
        if not L:
            self.vals["Link"].setText(f"packets ok {st.get('packets_ok')}, rejected {st.get('packets_rejected')}")
            return
        f = lambda v: "-" if v is None else f"{v:.1f}"
        self.vals["Peak L / R"].setText(f"{f(L['peak'][0])} / {f(L['peak'][1])}")
        self.vals["Momentary"].setText(f(L.get("lufs_m")))
        self.vals["Correlation"].setText(f"{L['corr']:.2f}")
        self.vals["Width"].setText(f"{L['width'] * 100:.0f} %")
        self.vals["Host"].setText(f"{'playing' if L.get('playing') else 'stopped'} {L['bpm']:.1f} bpm")
        self.vals["Link"].setText(f"ok {st.get('packets_ok')} / rejected {st.get('packets_rejected')} / key {L.get('kid', '?')}")
        b = np.array(L["bands"], float)
        self.bars.setOpts(x=np.arange(len(b)), height=b + 95, y0=-95, width=0.8)
