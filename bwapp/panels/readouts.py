"""Loudness numbers: momentary / short-term / integrated, distance to target, true peak, LRA, PLR, width."""
from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from bwapp import theme

CELLS = [("Momentary", "momentary", "LUFS"), ("Short-term", "short_term", "LUFS"), ("Integrated", "integrated", "LUFS"),
         ("To target", "gain_to_target", "dB"), ("True peak (max)", "true_peak_max", "dBTP"), ("LRA", "lra", "LU"),
         ("PLR", "plr", "dB"), ("Width (S/M)", "width_pct", "%")]


class Readouts(QWidget):
    def __init__(self, feed):
        super().__init__()
        self.setMinimumHeight(165)
        g = QGridLayout(self)
        self.vals = {}
        self.styled = {}                                    # last colour per label: setStyleSheet is slow, so only call it when the colour changes
        for i, (title, key, unit) in enumerate(CELLS):
            cap = QLabel(title.upper())
            cap.setStyleSheet(f"color:{theme.DIM};font-size:10px;letter-spacing:1px")
            v = QLabel("-")
            v.setStyleSheet("font-size:22px;font-weight:600")
            u = QLabel(unit)
            u.setStyleSheet(f"color:{theme.DIM}")
            g.addWidget(cap, (i // 4) * 3, i % 4)
            g.addWidget(v, (i // 4) * 3 + 1, i % 4)
            g.addWidget(u, (i // 4) * 3 + 2, i % 4)
            self.vals[key] = v
        feed.frame.connect(self.update_frame)

    def update_frame(self, f):
        t = f.get("target", {})
        for key, lab in self.vals.items():
            v = f.get(key)
            lab.setText("-" if v is None else f"{v:.1f}")
            col = theme.FG
            if key == "true_peak_max" and v is not None and v > t.get("tp", -1):
                col = theme.BAD
            elif key == "momentary" and v is not None and abs(v - t.get("lufs", -14)) < 1:
                col = theme.GOOD
            if self.styled.get(key) != col:
                self.styled[key] = col
                lab.setStyleSheet(f"font-size:22px;font-weight:600;color:{col}")
