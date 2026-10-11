"""Vectorscope (mid up, side across) and the phase-correlation bar."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from bwapp import theme


class Scope(QWidget):
    def __init__(self, feed):
        super().__init__()
        self.pts, self.corr = [], 1.0
        self.setMinimumSize(150, 150)
        feed.frame.connect(self.update_frame)

    def update_frame(self, f):
        self.pts, self.corr = f.get("scope", []), f.get("correlation", 1.0)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height() - 22
        r = min(w, h) / 2 - 6
        c = QPointF(w / 2, h / 2)
        p.setPen(QPen(QColor(theme.LINE), 1))
        p.drawEllipse(c, r, r)
        p.drawLine(QPointF(c.x() - r, c.y()), QPointF(c.x() + r, c.y()))
        p.drawLine(QPointF(c.x(), c.y() - r), QPointF(c.x(), c.y() + r))
        p.setPen(QPen(QColor(77, 163, 255, 150), 2))
        for s, m in self.pts:
            p.drawPoint(QPointF(c.x() + s * r, c.y() - m * r))
        bar = QRectF(10, self.height() - 14, w - 20, 8)           # correlation -1 .. +1
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.LINE))
        p.drawRoundedRect(bar, 4, 4)
        x = bar.left() + (self.corr + 1) / 2 * bar.width()
        p.setBrush(QColor(theme.GOOD if self.corr > 0.3 else theme.WARN if self.corr > -0.1 else theme.BAD))
        p.drawEllipse(QPointF(x, bar.center().y()), 6, 6)
