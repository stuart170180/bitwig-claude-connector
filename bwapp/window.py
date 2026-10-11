"""Main window: QtAds docking (drag, tab, float, resize, close, re-add from the View menu), layout saved between runs."""
import PySide6QtAds as ads
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QComboBox, QLabel, QMainWindow, QPushButton, QToolBar

from bwapp import blocks
from bwapp.feed import Feed
from bwmcp.analysis import mastering

ORG, APP = "BitwigClaude", "BitwigRemote"
LAYOUT_VERSION = 2       # bump when blocks change shape so an old saved layout is dropped


class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bitwig Remote")
        self.resize(1360, 900)
        ads.CDockManager.setConfigFlags(ads.CDockManager.DefaultOpaqueConfig | ads.CDockManager.FocusHighlighting)
        self.dm = ads.CDockManager(self)
        self.feed = Feed()
        self.docks = {}
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

    def _add(self, spec):
        d = ads.CDockWidget(spec.title)
        d.setObjectName(spec.id)
        d.setWidget(spec.widget)
        d.setFeature(ads.CDockWidget.DockWidgetClosable, True)
        d.setFeature(ads.CDockWidget.DockWidgetFloatable, True)
        d.setFeature(ads.CDockWidget.DockWidgetMovable, True)
        self.docks[spec.id] = (d, spec)

    def _default_layout(self):
        """Left: loudness over history over meters. Centre: spectrum tabbed with samples. Right: chat."""
        d = {k: v[0] for k, v in self.docks.items()}
        add, TOP, BOT, RIGHT, CEN = self.dm.addDockWidget, ads.TopDockWidgetArea, ads.BottomDockWidgetArea, ads.RightDockWidgetArea, ads.CenterDockWidgetArea
        left = add(TOP, d["readouts"])
        hist = add(BOT, d["history"], left)
        meters = add(BOT, d["levels"], hist)
        add(CEN, d["tuner"], meters)
        add(RIGHT, d["scope"], meters)
        mid = add(RIGHT, d["spectrum"])
        add(CEN, d["samples"], mid)
        add(RIGHT, d["chat"])
        mid.setCurrentIndex(0)
        try:                                                    # first-run proportions; the user's own resizing is saved afterwards
            self.dm.setSplitterSizes(left, [190, 330, 250])
            self.dm.setSplitterSizes(mid, [560, 360])
        except Exception:
            pass

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
        self.feed.status.connect(lambda st, dev: self.status.setText(f" {st}: {dev}" if st == "capturing" else f" {st}"))

    def _fill_view_menu(self):
        for d, _ in self.docks.values():
            self.view_menu.addAction(d.toggleViewAction())
        self.view_menu.addSeparator()
        self.view_menu.addAction("Show all blocks", lambda: [d.toggleView(True) for d, _ in self.docks.values()])
        self.view_menu.addAction("Reset layout", self.reset_layout)

    def reset_layout(self):
        s = QSettings(ORG, APP)
        s.clear()
        for d, _ in self.docks.values():
            d.toggleView(False)
        self._default_layout()
        for d, _ in self.docks.values():
            d.toggleView(True)

    def closeEvent(self, e):
        s = QSettings(ORG, APP)
        s.setValue("layout_version", LAYOUT_VERSION)
        s.setValue("geometry", self.saveGeometry())
        s.setValue("dock", self.dm.saveState())
        self.dm.deleteLater()
        super().closeEvent(e)
