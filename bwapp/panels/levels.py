"""L / R peak, M / S RMS and clipped-sample count as horizontal bars."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from bwapp import theme

ROWS = [("L", "peak", "l"), ("R", "peak", "r"), ("Mid", "rms", "m"), ("Side", "rms", "s")]


class Levels(QWidget):
    def __init__(self, feed):
        super().__init__()
        self.f = {}
        self.setMinimumSize(200, 130)
        feed.frame.connect(self.update_frame)

    def update_frame(self, f):
        self.f = f
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        y = 6
        for name, grp, key in ROWS:
            v = self.f.get(grp, {}).get(key, -90)
            v = max(-60.0, min(0.0, v if v is not None else -60))
            p.setPen(QColor(theme.DIM))
            p.drawText(QRectF(0, y, 36, 20), Qt.AlignVCenter, name)
            track = QRectF(40, y + 4, self.width() - 100, 12)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.LINE))
            p.drawRoundedRect(track, 5, 5)
            p.setBrush(QColor(theme.BAD if v > -1 else theme.WARN if v > -6 else theme.GOOD))
            p.drawRoundedRect(QRectF(track.left(), track.top(), track.width() * (v + 60) / 60, track.height()), 5, 5)
            p.setPen(QColor(theme.FG))
            p.drawText(QRectF(self.width() - 56, y, 56, 20), Qt.AlignVCenter | Qt.AlignRight, f"{v:.1f}")
            y += 26
        p.setPen(QColor(theme.DIM))
        p.drawText(QRectF(0, y + 2, self.width(), 18), Qt.AlignVCenter, f"Clipped samples: {self.f.get('clipped_samples', 0)}")
