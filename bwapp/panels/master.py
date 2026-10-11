"""Master chain controls: four sliders applied on release, Build chain, Refresh, Save report (talks to Bitwig through the same bridge as the MCP tools)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QGridLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from bwapp import theme, work
from bwapp import engine as lm

CONTROLS = [("limiter_gain_db", "Limiter gain", 0, 24, 0.1, "dB"), ("ceiling_db", "Ceiling", -12, 0, 0.1, "dB"),
            ("width_pct", "Stereo width", 0, 200, 1, "%"), ("output_gain_db", "Output gain", -12, 12, 0.1, "dB")]


class MasterPanel(QWidget):
    def __init__(self, feed):
        super().__init__()
        self.feed = feed
        self.state = QLabel("")
        self.state.setProperty("role", "dim")
        self.state.setWordWrap(True)
        self.msg = QLabel("Sliders apply when you release them. Uses Bitwig's master track (it will be selected).")
        self.msg.setProperty("role", "dim")
        self.msg.setWordWrap(True)
        self.sliders, self.labels = {}, {}
        grid = QGridLayout()
        for row, (key, name, lo, hi, step, unit) in enumerate(CONTROLS):
            s = QSlider(Qt.Horizontal)
            k = round(1 / step)
            s.setRange(int(lo * k), int(hi * k))
            s.setEnabled(False)
            lab = QLabel(f"{name}: -")
            s.valueChanged.connect(lambda v, key=key, name=name, k=k, unit=unit: self.labels[key].setText(f"{name}: {v / k:.1f} {unit}"))
            s.sliderReleased.connect(lambda key=key, k=k: self.apply(key, self.sliders[key].value() / k))
            grid.addWidget(lab, row, 0)
            grid.addWidget(s, row, 1)
            self.sliders[key], self.labels[key] = s, lab
            s.k = k
        self.style_box = QComboBox()
        self.style_box.addItems(["streaming", "club", "gentle"])
        build, refresh, report = QPushButton("Build chain"), QPushButton("Refresh values"), QPushButton("Save report")
        build.clicked.connect(self.build)
        refresh.clicked.connect(lambda: self.load(True))
        report.clicked.connect(self.save_report)
        lay = QVBoxLayout(self)
        lay.addWidget(self.state)
        lay.addLayout(grid)
        row = QGridLayout()
        for i, w in enumerate((self.style_box, build, refresh, report)):
            row.addWidget(w, 0, i)
        lay.addLayout(row)
        lay.addWidget(self.msg)
        lay.addStretch()

    def note(self, text, bad=False):
        self.msg.setText(text)
        self.msg.setStyleSheet(f"color:{theme.BAD if bad else theme.DIM}")

    def showEvent(self, e):
        super().showEvent(e)
        if not self.state.text():
            self.load(False)

    def load(self, refresh):
        self.note("Reading master chain...")
        work.run(lm.master_state, self.loaded, refresh)

    def loaded(self, m, err):
        if err:
            return self.note("Couldn't read Bitwig: " + err, True)
        self.state.setText(" > ".join(d["name"] + ("" if d["enabled"] else " (off)") for d in m["devices"]) if m["built"]
                           else "No mastering chain yet - press Build chain")
        for key, s in self.sliders.items():
            v = m["values"].get(key)
            s.setEnabled(bool(m["built"]))
            if v is not None:
                s.blockSignals(True)
                s.setValue(round(v * s.k))
                s.blockSignals(False)
                self.labels[key].setText(self.labels[key].text().split(":")[0] + f": {v:.1f}")
        self.note("Sliders apply when you release them. Uses Bitwig's master track (it will be selected).")

    def apply(self, key, value):
        self.note("Applying...")
        work.run(lm.master_set, lambda r, e: self.note(e, True) if e else self.note("Bitwig shows: " + str(list(r["set"].values())[0])), {key: value})

    def build(self):
        self.note(f"Building {self.style_box.currentText()} chain... (a few seconds)")
        work.run(lm.master_build, lambda r, e: self.note(e, True) if e else (self.loaded(r, None), self.note("Chain built.")),
                 {"style": self.style_box.currentText(), "target": self.feed.target})

    def save_report(self):
        work.run(lm.save_report, lambda r, e: self.note(e, True) if e else self.note("Saved " + r["saved"]), self.feed.cap)
