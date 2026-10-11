"""Connection lights in the toolbar: Bitwig (the controller script answers) and Audio (measurements are arriving).
Green = connected, amber = connected but something is missing (no signal yet), red = not connected."""
import time

from PySide6.QtCore import QRectF, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from bwapp import theme, work
from bwmcp.core.bridge import bw

GREEN, AMBER, RED, OFF = theme.GOOD, theme.WARN, theme.BAD, "#4a505c"


class Led(QWidget):
    def __init__(self):
        super().__init__()
        self.colour = OFF
        self.setFixedSize(QSize(16, 16))

    def set(self, colour, tip):
        self.colour = colour
        self.setToolTip(tip)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QColor(self.colour)
        glow = QColor(c)
        glow.setAlpha(70)
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QRectF(0, 0, 16, 16))
        p.setBrush(c)
        p.drawEllipse(QRectF(3, 3, 10, 10))


class Lights(QWidget):
    """Two lights and the project name. Bitwig is probed every 3 s on a worker thread (a busy bridge counts as connected)."""

    def __init__(self, feed):
        super().__init__()
        self.feed = feed
        self.bitwig, self.audio = Led(), Led()
        self.project = QLabel("")
        self.project.setProperty("role", "dim")
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 0, 6, 0)
        for led, name in ((self.bitwig, "Bitwig"), (self.audio, "Audio")):
            row.addWidget(led)
            row.addWidget(QLabel(name))
        row.addWidget(self.project)
        self.last_frame = 0.0
        self.src = ""
        feed.frame.connect(self._frame)
        feed.status.connect(self._status)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.probe)
        self.timer.start(3000)
        self.view = QTimer(self)
        self.view.timeout.connect(self.refresh_audio)
        self.view.start(500)
        self.probe()
        self.refresh_audio()

    # Bitwig ---------------------------------------------------------------------------------------------------------
    def probe(self):
        work.run(self._ping, self._pinged)

    @staticmethod
    def _ping():
        if not bw.lock.acquire(blocking=False):           # a long command is running: the link is in use, so it is up
            return {"busy": True}
        bw.lock.release()
        t0 = time.time()
        caps = bw.call("capabilities")
        name = None
        try:
            name = bw.call("proj_state").get("project")
        except Exception:  # noqa: BLE001
            pass
        return {"ms": (time.time() - t0) * 1000, "script": caps.get("version"), "project": name}

    def _pinged(self, r, err):
        if err:
            self.bitwig.set(RED, f"Bitwig is not reachable: {err}\nIs Bitwig open with Claude > Bitwig MCP enabled (Settings > Controllers)?")
            self.project.setText("")
        elif r.get("busy"):
            self.bitwig.set(GREEN, "Bitwig connected (busy with a command)")
        else:
            self.bitwig.set(GREEN, f"Bitwig connected: controller script {r['script']}, {r['ms']:.0f} ms\nProject: {r['project']}")
            self.project.setText(r["project"] or "")

    # Audio ----------------------------------------------------------------------------------------------------------
    def _frame(self, f):
        self.last_frame = time.time()
        self.quiet = (f.get("momentary") is None) or f["momentary"] < -70

    def _status(self, state, device):
        self.state = state
        self.src = device if state == "capturing" else state

    quiet = True
    state = "starting"

    def refresh_audio(self):
        age = time.time() - self.last_frame
        if self.state != "capturing":
            self.audio.set(RED, f"No audio source ({self.src or 'starting'}).\nUse the BW Remote VST3 on the master, or Windows Audio (WASAPI) in Bitwig.")
        elif self.last_frame == 0.0 or age > 2.0:
            self.audio.set(AMBER, f"Audio source connected ({self.src}) but no data is arriving yet: press play in Bitwig.")
        elif self.quiet:
            self.audio.set(AMBER, f"Audio source connected ({self.src}) but silent: press play in Bitwig.")
        else:
            self.audio.set(GREEN, f"Audio connected: {self.src}")
