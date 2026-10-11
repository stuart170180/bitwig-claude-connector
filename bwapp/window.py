"""Main window: QtAds docking (drag, tab, float, resize, close, re-add from the View menu), layout saved between runs."""
import PySide6QtAds as ads
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QComboBox, QLabel, QMainWindow, QPushButton, QSizePolicy, QToolBar

from bwapp import blocks
from bwapp.feed import Feed
from bwapp.header import Clock, Weather
from bwmcp.analysis import mastering

ORG, APP = "BitwigClaude", "BitwigRemote"
LAYOUT_VERSION = 8       # bump when blocks change shape so an old saved layout is dropped


class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bitwig Remote")
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.resize(min(1500, screen.width() - 40), min(960, screen.height() - 40))
        ads.CDockManager.setConfigFlags(ads.CDockManager.DefaultOpaqueConfig)     # no focus highlight: it painted the focused tab's title invisible
        self.dm = ads.CDockManager(self)
        self.feed = Feed()
        self.feed.command.connect(self.on_command)
        self.docks = {}
        self.default_state = None
        self._build_toolbar()
        for spec in blocks.all_blocks(self.feed):
            self._add(spec)
        self._default_layout()
        self.view_menu = self.menuBar().addMenu("&View")
        self._fill_view_menu()
        s = QSettings(ORG, APP)
        if s.value("layout_version") == LAYOUT_VERSION:
            if s.value("geometry"):
                self.restoreGeometry(s.value("geometry"))
            if s.value("dock"):
                self.dm.restoreState(s.value("dock"))

    def on_command(self, cmd, args):
        """Commands the MCP server leaves for the app (live_monitor tool)."""
        if cmd == "reset":
            self.feed.reset()
        elif cmd == "target" and args.get("name") in mastering.TARGETS:
            self.target.setCurrentText(args["name"])
        elif cmd == "quit":
            self.close()

    def _add(self, spec):
        d = ads.CDockWidget(spec.title)
        d.setObjectName(spec.id)
        d.setWidget(spec.widget)
        d.setFeature(ads.CDockWidget.DockWidgetClosable, True)
        d.setFeature(ads.CDockWidget.DockWidgetFloatable, True)
        d.setFeature(ads.CDockWidget.DockWidgetMovable, True)
        self.docks[spec.id] = (d, spec)

    def _default_layout(self):
        """Left column: loudness, advice, history, then levels | tuner | vectorscope. Centre: spectrum over the tool tabs (samples first). Right: chat."""
        d = {k: v[0] for k, v in self.docks.items()}
        add, TOP, BOT, RIGHT, CEN = self.dm.addDockWidget, ads.TopDockWidgetArea, ads.BottomDockWidgetArea, ads.RightDockWidgetArea, ads.CenterDockWidgetArea
        left = add(TOP, d["readouts"])
        adv = add(BOT, d["advice"], left)
        hist = add(BOT, d["history"], adv)
        levels = add(BOT, d["levels"], hist)
        tuner = add(RIGHT, d["tuner"], levels)
        add(RIGHT, d["scope"], tuner)
        mid = add(RIGHT, d["spectrum"])
        tools = add(BOT, d["samples"], mid)
        for k in ("master", "vst", "comps", "chords", "circle"):
            add(CEN, d[k], tools)
        add(RIGHT, d["chat"])
        tools.setCurrentIndex(0)
        QTimer.singleShot(0, lambda: self._proportions(left, mid))

    def _proportions(self, left, mid):
        """First-run sizes (the user's own resizing is saved and restored afterwards)."""
        try:
            h = max(self.height() - 90, 600)
            self.dm.setSplitterSizes(left, [int(h * 0.20), int(h * 0.06), int(h * 0.34), int(h * 0.30)])
            self.dm.setSplitterSizes(mid, [int(h * 0.36), int(h * 0.64)])
            root = self.dm.rootSplitter() if hasattr(self.dm, "rootSplitter") else None
            if root is not None:
                w = max(self.width(), 1000)
                root.setSizes([int(w * 0.35), int(w * 0.36), int(w * 0.29)])
        except Exception:  # noqa: BLE001
            pass
        QTimer.singleShot(50, lambda: setattr(self, "default_state", self.dm.saveState()))   # what Reset layout returns to

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)
        self.status = QLabel("starting...")
        self.target = QComboBox()
        self.target.addItems(list(mastering.TARGETS))
        self.target.currentTextChanged.connect(self.feed.set_target)
        reset = QPushButton("Reset")
        reset.setToolTip("Restart integrated loudness, LRA and peak hold")
        reset.clicked.connect(self.feed.reset)
        tb.addWidget(QLabel(" Target "))
        tb.addWidget(self.target)
        tb.addWidget(reset)
        tb.addSeparator()
        tb.addWidget(self.status)
        spacer = QLabel()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        tb.addWidget(Weather())
        tb.addSeparator()
        tb.addWidget(Clock())
        self.feed.status.connect(lambda st, dev: self.status.setText(f" {st}: {dev}" if st == "capturing" else f" {st}"))

    def _fill_view_menu(self):
        for d, _ in self.docks.values():
            self.view_menu.addAction(d.toggleViewAction())
        self.view_menu.addSeparator()
        self.view_menu.addAction("Show all blocks", lambda: [d.toggleView(True) for d, _ in self.docks.values()])
        self.view_menu.addAction("Reset layout", self.reset_layout)

    def reset_layout(self):
        s = QSettings(ORG, APP)
        for k in ("dock", "geometry", "layout_version"):
            s.remove(k)
        for d, _ in self.docks.values():
            d.toggleView(True)
        if self.default_state is not None:
            self.dm.restoreState(self.default_state)
        for d, _ in self.docks.values():
            d.toggleView(True)

    def closeEvent(self, e):
        s = QSettings(ORG, APP)
        s.setValue("layout_version", LAYOUT_VERSION)
        s.setValue("geometry", self.saveGeometry())
        s.setValue("dock", self.dm.saveState())
        self.dm.deleteLater()
        super().closeEvent(e)
