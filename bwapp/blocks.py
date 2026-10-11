"""Every block the app offers. Add a block = add one line in all_blocks() and one placement line in window.layout()."""
from dataclasses import dataclass

from PySide6.QtWidgets import QWidget

from bwapp.panels import LIVE


@dataclass
class Spec:
    id: str
    title: str
    widget: QWidget


def all_blocks(feed):
    out = [Spec(bid, title, cls(feed)) for bid, title, cls in LIVE]
    from bwapp.chat.panel import ChatPanel
    from bwapp.audio.panel import SamplePanel
    out.append(Spec("chat", "Claude chat", ChatPanel()))
    out.append(Spec("samples", "Samples", SamplePanel()))
    return out
