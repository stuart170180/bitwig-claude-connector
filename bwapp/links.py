"""Signals shared between blocks so they stay linked (circle of fifths <-> chords <-> samples)."""
from PySide6.QtCore import QObject, Signal

SHARP = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#", "Cb": "B"}      # chords block uses sharp names


class Links(QObject):
    key = Signal(str, str)           # tonic (C, C#, ...), scale ("major" | "minor"): the key the user picked
    sample_key = Signal(str, str)    # key detected in the loaded sample
    progression = Signal(str)        # chord text for the chords block, e.g. "I, V, vi, IV"


LINK = Links()
