"""Waveform view: drawn from min/max peaks, bar/beat grid when the tempo is known, playhead, click or drag to seek."""
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from bwapp import theme
from bwapp.audio import decode


class Waveform(QWidget):
    seek = Signal(float)      # seconds

    def __init__(self):
        super().__init__()
        self.mono, self.sr, self.pos = np.zeros(0, np.float32), 44100, 0.0
        self.bpm, self.beats_per_bar = None, 4
        self._peaks, self._cols = None, 0
        self.setMinimumHeight(110)
        self.setCursor(Qt.PointingHandCursor)

    def set_sample(self, data, sr):
        self.mono = data.mean(axis=1) if len(data) else np.zeros(0, np.float32)
        self.sr, self.pos, self._peaks, self._cols = sr, 0.0, None, 0
        self.update()

    def set_grid(self, bpm, beats_per_bar):
        self.bpm, self.beats_per_bar = bpm, beats_per_bar
        self.update()

    def set_position(self, seconds):
        self.pos = seconds
        self.update()

    def _dur(self):
        return len(self.mono) / self.sr if self.sr else 0.0

    def _seek_to(self, x):
        if self._dur():
            self.seek.emit(max(0.0, min(1.0, x / max(self.width(), 1))) * self._dur())

    def mousePressEvent(self, e):
        self._seek_to(e.position().x())

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            self._seek_to(e.position().x())

    def paintEvent(self, _):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(theme.PANEL))
        dur = self._dur()
        if not dur:
            p.setPen(QColor(theme.DIM))
            p.drawText(self.rect(), Qt.AlignCenter, "Pick a sample from the list")
            return
        if self._peaks is None or self._cols != w:
            self._peaks, self._cols = decode.peaks(self.mono, w), w
        if self.bpm:
            spb = 60.0 / self.bpm
            t, n = 0.0, 0
            while t < dur:
                x = t / dur * w
                bar = n % self.beats_per_bar == 0
                p.setPen(QPen(QColor(theme.LINE if bar else "#20242b"), 1))
                p.drawLine(int(x), 0, int(x), h)
                t, n = t + spb, n + 1
        mid = h / 2
        p.setPen(QPen(QColor(theme.ACCENT), 1))
        for x, (lo, hi) in enumerate(self._peaks):
            p.drawLine(x, int(mid - hi * mid * 0.95), x, int(mid - lo * mid * 0.95))
        px = self.pos / dur * w
        p.setPen(QPen(QColor(theme.WARN), 2))
        p.drawLine(int(px), 0, int(px), h)
