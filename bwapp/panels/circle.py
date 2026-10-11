"""Circle of fifths: click a key to link the chords block (key + scale), hear its triad, see its diatonic chords and the sample's key."""
import math

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from bwapp import theme
from bwapp.links import LINK, SHARP

MAJOR = ["C", "G", "D", "A", "E", "B", "F#", "Db", "Ab", "Eb", "Bb", "F"]        # clockwise from the top
MINOR = ["Am", "Em", "Bm", "F#m", "C#m", "G#m", "Ebm", "Bbm", "Fm", "Cm", "Gm", "Dm"]
PC = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
SIGNATURE = ["0", "1#", "2#", "3#", "4#", "5#", "6#/6b", "5b", "4b", "3b", "2b", "1b"]
PROGRESSIONS = [("I  V  vi  IV", "I, V, vi, IV"), ("ii  V  I", "ii7, V7, Imaj7"), ("vi  IV  I  V", "vi, IV, I, V"), ("I  vi  IV  V", "I, vi, IV, V")]


def triad(root_pc, minor, octave_c=60):
    return [octave_c + (root_pc % 12), octave_c + (root_pc % 12) + (3 if minor else 4), octave_c + (root_pc % 12) + 7]


class Circle(QWidget):
    def __init__(self, feed=None):
        super().__init__()
        self.sel = (0, False)             # (position on the circle, minor?)
        self.sample = None                # (position, minor) of the loaded sample
        self.setMinimumSize(260, 260)
        self.info = QLabel("")
        self.info.setWordWrap(True)
        self.info.setProperty("role", "dim")
        row = QHBoxLayout()
        for label, text in PROGRESSIONS:
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, t=text: LINK.progression.emit(t))
            row.addWidget(b)
        lay = QVBoxLayout(self)
        lay.addStretch(1)
        lay.addWidget(self.info)
        lay.addLayout(row)
        self.setMouseTracking(False)
        LINK.sample_key.connect(self.set_sample_key)
        self.refresh_info()

    # geometry -------------------------------------------------------------------------------------------------------
    def dims(self):
        top = self.height() - 100
        r = max(min(self.width(), top) / 2 - 8, 60)
        return QPointF(self.width() / 2, top / 2 + 4), r

    def sector(self, i, r0, r1, c):
        a0 = -90 - 15 + 30 * i                                   # degrees, 0 = three o'clock, clockwise on screen
        p = QPainterPath()
        outer, inner = QRectF(c.x() - r1, c.y() - r1, 2 * r1, 2 * r1), QRectF(c.x() - r0, c.y() - r0, 2 * r0, 2 * r0)
        p.arcMoveTo(outer, -a0)
        p.arcTo(outer, -a0, -30)
        p.arcTo(inner, -a0 - 30, 30)
        p.closeSubpath()
        return p

    def hit(self, pos):
        c, r = self.dims()
        d = math.hypot(pos.x() - c.x(), pos.y() - c.y())
        if d > r or d < r * 0.42:
            return None
        ang = (math.degrees(math.atan2(pos.y() - c.y(), pos.x() - c.x())) + 90 + 15) % 360
        return int(ang // 30) % 12, d < r * 0.70

    # painting -------------------------------------------------------------------------------------------------------
    def family(self):
        """Positions of the keys that share the selected key's notes: (I IV V and ii iii vi as major/minor positions)."""
        i, minor = self.sel
        base = i                                                   # a minor key sits at the same position as its relative major
        return {(base, False), ((base - 1) % 12, False), ((base + 1) % 12, False),
                (base, True), ((base - 1) % 12, True), ((base + 1) % 12, True)}

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c, r = self.dims()
        fam = self.family()
        for ring, (r0, r1, names) in enumerate(((r * 0.70, r, MAJOR), (r * 0.42, r * 0.70, MINOR))):
            minor = bool(ring)
            for i, name in enumerate(names):
                path = self.sector(i, r0, r1, c)
                if (i, minor) == self.sel:
                    col = QColor(theme.ACCENT)
                elif (i, minor) in fam:
                    col = QColor(77, 163, 255, 70)
                else:
                    col = QColor(theme.PANEL)
                p.setPen(QPen(QColor(theme.LINE), 1.2))
                p.setBrush(col)
                p.drawPath(path)
                if self.sample == (i, minor):
                    p.setPen(QPen(QColor(theme.WARN), 3))
                    p.setBrush(Qt.NoBrush)
                    p.drawPath(path)
                mid = math.radians(-90 + 30 * i)
                rr = (r0 + r1) / 2
                x, y = c.x() + rr * math.cos(mid), c.y() + rr * math.sin(mid)
                p.setPen(QColor("#000000" if (i, minor) == self.sel else theme.FG))
                p.setFont(QFont("Segoe UI", 12 if not minor else 10, QFont.Bold if not minor else QFont.Normal))
                p.drawText(QRectF(x - 24, y - 12, 48, 24), Qt.AlignCenter, name)
        i, minor = self.sel
        p.setPen(QColor(theme.FG))
        p.setFont(QFont("Segoe UI", 15, QFont.Bold))
        p.drawText(QRectF(c.x() - r * 0.4, c.y() - 22, r * 0.8, 26), Qt.AlignCenter, (MINOR if minor else MAJOR)[i].replace("m", "") + (" min" if minor else " maj"))
        p.setPen(QColor(theme.DIM))
        p.setFont(QFont("Segoe UI", 10))
        p.drawText(QRectF(c.x() - r * 0.4, c.y() + 4, r * 0.8, 20), Qt.AlignCenter, SIGNATURE[i] + " in the key signature")

    # interaction ----------------------------------------------------------------------------------------------------
    def mousePressEvent(self, e):
        h = self.hit(e.position())
        if h is None:
            return
        self.sel = h
        i, minor = h
        name = (MINOR if minor else MAJOR)[i].replace("m", "")
        tonic = SHARP.get(name, name)
        LINK.key.emit(tonic, "minor" if minor else "major")
        sd.play((self.tone(PC[name], minor)), 44100)
        self.refresh_info()
        self.update()

    @staticmethod
    def tone(root_pc, minor, sr=44100):
        t = np.arange(int(sr * 0.9)) / sr
        env = np.minimum(t / 0.02, 1) * np.exp(-t * 3.0)
        sig = sum(np.sin(2 * np.pi * 440 * 2 ** ((p - 69) / 12) * t) for p in triad(root_pc, minor))
        return (sig * env * 0.06).astype(np.float32)               # quiet on purpose

    def set_sample_key(self, tonic, scale):
        flat = {v: k for k, v in SHARP.items()}
        for cand in (tonic, flat.get(tonic, tonic)):
            names = MINOR if scale == "minor" else MAJOR
            for i, n in enumerate(names):
                if (n.replace("m", "") if scale == "minor" else n) == cand:
                    self.sample = (i, scale == "minor")
                    self.refresh_info()
                    self.update()
                    return

    def refresh_info(self):
        i, minor = self.sel
        base = i
        degrees = [("I", MAJOR[base]), ("ii", MINOR[(base - 1) % 12]), ("iii", MINOR[(base + 1) % 12]), ("IV", MAJOR[(base - 1) % 12]),
                   ("V", MAJOR[(base + 1) % 12]), ("vi", MINOR[base])]
        txt = "Chords in this key: " + "   ".join(f"{d} {n}" for d, n in degrees)
        note = ""
        if self.sample:
            si, sm = self.sample
            sbase = si
            diff = (base - sbase) % 12
            steps = {0: "the same notes", 1: "one step clockwise (a fifth up): mixes well", 11: "one step anticlockwise: mixes well"}.get(diff, f"{min(diff, 12 - diff)} steps apart")
            note = f"\nSample key {(MINOR if sm else MAJOR)[si]}: {steps}."
        self.info.setText(txt + note)
