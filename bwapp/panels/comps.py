"""Compressor+ settings in real units for every compressor in the project (reading selects each device in Bitwig)."""
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from bwapp import work
from bwapp import engine as lm

COLS = [("ATTACK", "Attack"), ("RELEASE", "Release"), ("RATIO", "Ratio"), ("THRESHOLD", "Threshold"), ("SMOOTH", "Knee"),
        ("MAKEUP", "Make-up"), ("MIX", "Mix")]


class Compressors(QWidget):
    def __init__(self, feed=None):
        super().__init__()
        self.table = QTableWidget(0, 1 + len(COLS))
        self.table.setHorizontalHeaderLabels(["Track"] + [c[1] for c in COLS])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.msg = QLabel("Press Read compressors (it selects each Compressor+ in Bitwig).")
        self.msg.setProperty("role", "dim")
        b = QPushButton("Read compressors")
        b.clicked.connect(self.read)
        row = QHBoxLayout()
        row.addWidget(b)
        row.addWidget(self.msg, 1)
        lay = QVBoxLayout(self)
        lay.addWidget(self.table, 1)
        lay.addLayout(row)

    def read(self):
        self.msg.setText("Reading...")
        work.run(lm.compressors_state, self.show_result)

    def show_result(self, r, err):
        if err:
            return self.msg.setText("Couldn't read Bitwig: " + err)
        comps = r["compressors"]
        self.table.setRowCount(len(comps))
        for i, c in enumerate(comps):
            self.table.setItem(i, 0, QTableWidgetItem(c["track"] + ("" if c["enabled"] else " (off)")))
            for j, (k, _) in enumerate(COLS):
                self.table.setItem(i, j + 1, QTableWidgetItem(str(c["values"].get(k, "-"))))
        self.msg.setText(r["note"] if comps else "No Compressor+ in the project.")
