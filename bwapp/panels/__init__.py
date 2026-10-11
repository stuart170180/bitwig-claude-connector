"""Registry of blocks: (id, title, factory). A block is a QWidget built from the shared Feed."""
from bwapp.panels.graphs import History, Spectrum
from bwapp.panels.levels import Levels
from bwapp.panels.readouts import Readouts
from bwapp.panels.scope import Scope
from bwapp.panels.tuner import Tuner

LIVE = [("readouts", "Loudness", Readouts), ("history", "Loudness history", History), ("spectrum", "Spectrum (mid / side)", Spectrum),
        ("scope", "Vectorscope", Scope), ("levels", "Levels", Levels), ("tuner", "Tuner", Tuner)]
