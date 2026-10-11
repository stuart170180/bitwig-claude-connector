"""Chords & voicings: type a progression, see each voicing on a keyboard, hear it, write it into a Bitwig clip."""
import numpy as np
import sounddevice as sd
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox,
                               QVBoxLayout, QWidget)

from bwapp import theme, work
from bwapp.links import LINK
from bwapp import engine as lm

NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
SCALES = ["major", "minor", "dorian", "mixolydian", "lydian", "phrygian", "harmonic_minor"]
RHYTHMS = ["sustained", "stabs", "pulse", "arp_up", "arp_updown", "strum"]
WHITE = [0, 2, 4, 5, 7, 9, 11]


class Keys(QWidget):
    def __init__(self, label, notes, pitches):
        super().__init__()
        self.pitches = pitches
        self.setFixedSize(260, 84)
        self.label = f"{label}  {notes}"

    def paintEvent(self, _):
        p = QPainter(self)
        lo, hi, top = 36, 96, 18
        whites = [n for n in range(lo, hi + 1) if n % 12 in WHITE]
        kw, h = self.width() / len(whites), self.height() - top
        p.setPen(QColor(theme.FG))
        p.drawText(QRectF(0, 0, self.width(), top), 0x81, self.label)
        for i, n in enumerate(whites):
            p.fillRect(QRectF(i * kw, top, kw - 1, h), QColor(theme.ACCENT if n in self.pitches else "#e8e8ea"))
        for i, n in enumerate(whites):
            b = n + 1
            if b <= hi and b % 12 not in WHITE:
                p.fillRect(QRectF(i * kw + kw * 0.65, top, kw * 0.7, h * 0.6), QColor(theme.ACCENT if b in self.pitches else "#15171b"))


def synth(voicings, sr=44100):
    """Plain triangle-wave chord stabs, 1.4 s each: enough to hear the voicing."""
    out = []
    for v in voicings:
        t = np.arange(int(sr * 1.4)) / sr
        env = np.minimum(t / 0.03, 1) * np.exp(-t * 3.2)
        sig = sum(2 / np.pi * np.arcsin(np.sin(2 * np.pi * 440 * 2 ** ((p - 69) / 12) * t)) for p in v["pitches"])
        out.append((sig * env * 0.25 / max(len(v["pitches"]), 1) ** 0.5).astype(np.float32))
    return np.concatenate(out) if out else np.zeros(1, np.float32)


class Chords(QWidget):
    def __init__(self, feed=None):
        super().__init__()
        self.lib, self.last = lm.chords_lib(), None
        self.genre, self.style = QComboBox(), QComboBox()
        self.genre.addItems(["all styles"] + list(self.lib["genre_styles"]))
        self.key, self.scale, self.rhythm = QComboBox(), QComboBox(), QComboBox()
        self.key.addItems(NOTES)
        self.scale.addItems(SCALES)
        self.rhythm.addItems(RHYTHMS)
        self.bars = QSpinBox()
        self.bars.setRange(1, 8)
        self.chords = QLineEdit("ii7, V7, I, vi")
        self.bass, self.lead = QCheckBox("bass"), QCheckBox("voice-lead")
        self.lead.setChecked(True)
        self.track, self.slot = QSpinBox(), QSpinBox()
        self.msg = QLabel("Preview needs no Bitwig; Write puts the notes in that clip.")
        self.msg.setProperty("role", "dim")
        self.msg.setWordWrap(True)
        grid = QGridLayout()
        for i, (n, w) in enumerate([("Genre", self.genre), ("Voicing", self.style), ("Key", self.key), ("Scale", self.scale), ("Rhythm", self.rhythm),
                                    ("Bars/chord", self.bars)]):
            grid.addWidget(QLabel(n), i // 3 * 2, i % 3)
            grid.addWidget(w, i // 3 * 2 + 1, i % 3)
        show, play, write = QPushButton("Show"), QPushButton("Play"), QPushButton("Write to Bitwig")
        row = QHBoxLayout()
        for w in (self.chords, self.bass, self.lead, show, play):
            row.addWidget(w)
        self.chords.setMinimumWidth(200)
        row2 = QHBoxLayout()
        for w in (QLabel("Track"), self.track, QLabel("Slot"), self.slot, write):
            row2.addWidget(w)
        row2.addStretch()
        self.holder = QWidget()
        self.flow = QGridLayout(self.holder)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.holder)
        lay = QVBoxLayout(self)
        for part in (grid, row):
            lay.addLayout(part)
        lay.addWidget(scroll, 1)
        lay.addLayout(row2)
        lay.addWidget(self.msg)
        self.genre.currentTextChanged.connect(self.fill_styles)
        for w in (self.style, self.key, self.scale):
            w.currentTextChanged.connect(self.show_chords)
        for w in (self.bass, self.lead):
            w.toggled.connect(self.show_chords)
        show.clicked.connect(self.show_chords)
        play.clicked.connect(self.play)
        write.clicked.connect(self.write)
        LINK.key.connect(self.set_key)
        LINK.progression.connect(self.set_progression)
        self.fill_styles()

    def set_key(self, tonic, scale):
        """From the circle of fifths: follow the chosen key."""
        self.key.blockSignals(True)
        self.scale.blockSignals(True)
        self.key.setCurrentText(tonic)
        self.scale.setCurrentText(scale)
        self.key.blockSignals(False)
        self.scale.blockSignals(False)
        self.show_chords()

    def set_progression(self, text):
        self.chords.setText(text)
        self.show_chords()

    def fill_styles(self, *_):
        g = self.genre.currentText()
        names = self.lib["genre_styles"].get(g) if g in self.lib["genre_styles"] else list(self.lib["styles"])
        self.style.blockSignals(True)
        self.style.clear()
        self.style.addItems(names)
        self.style.blockSignals(False)
        self.show_chords()

    def query(self):
        return {"chords": self.chords.text(), "style": self.style.currentText(), "key": self.key.currentText(), "scale": self.scale.currentText(),
                "bass": "1" if self.bass.isChecked() else "0", "lead": "1" if self.lead.isChecked() else "0"}

    def show_chords(self, *_):
        if not self.style.currentText():
            return
        try:
            self.last = lm.chords_voice(self.query())
        except Exception as e:  # noqa: BLE001
            return self.msg.setText(str(e))
        while self.flow.count():
            self.flow.takeAt(0).widget().deleteLater()
        for i, v in enumerate(self.last["voicings"]):
            self.flow.addWidget(Keys(v["chord"], v["notes"], v["pitches"]), i // 2, i % 2)
        self.msg.setText(self.lib["styles"].get(self.style.currentText(), ""))

    def play(self):
        self.show_chords()
        if self.last:
            sd.play(synth(self.last["voicings"]), 44100)

    def write(self):
        self.msg.setText("Writing...")
        body = {"track": self.track.value(), "slot": self.slot.value(), "chords": self.chords.text(), "key": self.key.currentText(),
                "scale": self.scale.currentText(), "style": self.style.currentText(), "rhythm": self.rhythm.currentText(),
                "bars": self.bars.value(), "bass": self.bass.isChecked(), "lead": self.lead.isChecked()}
        work.run(lm.chords_write, lambda r, e: self.msg.setText(f"Failed: {e}" if e else f"Wrote {r['notes']} notes ({' '.join(r['chords'])})"), body)
