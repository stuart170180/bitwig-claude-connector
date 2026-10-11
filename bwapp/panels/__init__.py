"""Registry of blocks: (id, title, factory). A block is a QWidget built from the shared Feed."""
from bwapp.panels.advice import Advice
from bwapp.panels.chords import Chords
from bwapp.panels.comps import Compressors
from bwapp.panels.graphs import History, Spectrum
from bwapp.panels.levels import Levels
from bwapp.panels.master import MasterPanel
from bwapp.panels.readouts import Readouts
from bwapp.panels.scope import Scope
from bwapp.panels.tuner import Tuner
from bwapp.panels.vst import VstCard

LIVE = [("readouts", "Loudness", Readouts), ("history", "Loudness history", History), ("spectrum", "Spectrum (mid / side)", Spectrum),
        ("scope", "Vectorscope", Scope), ("levels", "Levels", Levels), ("tuner", "Tuner", Tuner),
        ("advice", "Advice", Advice), ("vst", "BW Remote VST link", VstCard), ("master", "Master chain controls", MasterPanel),
        ("comps", "Compressors", Compressors), ("chords", "Chords & voicings", Chords)]
