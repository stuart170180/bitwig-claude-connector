"""Pitch tuner: note name, Hz and a needle showing cents sharp / flat."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from bwapp import theme


class Tuner(QWidget):
    def __init__(self, feed):
        super().__init__()
        self.pitch = None
        self.setMinimumSize(150, 130)
        feed.frame.connect(self.update_frame)

    def update_frame(self, f):
        self.pitch = f.get("pitch")
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        bar = QRectF(16, h - 40, w - 32, 10)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.LINE))
        p.drawRoundedRect(bar, 5, 5)
        p.setBrush(QColor(theme.GOOD))
        p.drawRect(QRectF(bar.center().x() - bar.width() * 0.05, bar.top(), bar.width() * 0.1, bar.height()))
        p.setPen(QColor(theme.DIM))
        for c in (-50, 0, 50):
            x = bar.center().x() + c / 50 * bar.width() / 2
            p.drawText(QRectF(x - 20, h - 26, 40, 16), Qt.AlignCenter, f"{c:+d}" if c else "0")
        pt = self.pitch
        if not pt:
            p.setFont(QFont("Segoe UI", 12))
            p.drawText(QRectF(0, 0, w, h - 40), Qt.AlignCenter, "no steady pitch")
            return
        cents = max(-50, min(50, pt["cents"]))
        good = abs(pt["cents"]) <= 5
        p.setPen(QColor(theme.GOOD if good else theme.WARN))
        p.setFont(QFont("Segoe UI", 34, QFont.Bold))
        p.drawText(QRectF(0, 4, w, 56), Qt.AlignCenter, pt["note"])
        p.setFont(QFont("Segoe UI", 11))
        p.setPen(QColor(theme.FG))
        p.drawText(QRectF(0, 60, w, 20), Qt.AlignCenter, f"{pt['hz']:.1f} Hz   {pt['cents']:+.0f} cents")
        x = bar.center().x() + cents / 50 * bar.width() / 2
        p.setPen(QPen(QColor(theme.FG), 3))
        p.drawLine(int(x), int(bar.top() - 6), int(x), int(bar.bottom() + 6))
