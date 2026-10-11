"""Dark palette and a small stylesheet shared by every block."""
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

BG, PANEL, LINE, FG, DIM = "#111317", "#1a1d23", "#2a2e37", "#e6e8ec", "#8b93a1"
ACCENT, GOOD, WARN, BAD = "#4da3ff", "#4cd08a", "#f0b429", "#ff5d5d"

QSS = f"""
QMainWindow, QWidget {{ background: {BG}; color: {FG}; }}
QPushButton {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 6px; padding: 5px 12px; }}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:pressed, QPushButton:checked {{ background: {ACCENT}; color: #000; }}
QLineEdit, QTextEdit, QTextBrowser, QComboBox, QListWidget, QTreeView {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 6px; padding: 4px; }}
QMenuBar, QMenu {{ background: {PANEL}; }} QMenu::item:selected {{ background: {ACCENT}; color: #000; }}
QSlider::groove:horizontal {{ height: 4px; background: {LINE}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {ACCENT}; width: 14px; margin: -6px 0; border-radius: 7px; }}
QLabel[role="dim"] {{ color: {DIM}; }}
ads--CDockWidgetTab {{ background: {BG}; border: none; padding: 0 6px; }}
ads--CDockWidgetTab[activeTab="true"] {{ background: {PANEL}; border-bottom: 2px solid {ACCENT}; }}
ads--CDockWidgetTab[focused="true"] {{ background: {PANEL}; border-bottom: 2px solid {ACCENT}; }}
ads--CDockWidgetTab QLabel {{ color: {DIM}; }}
ads--CDockWidgetTab[focused="true"] QLabel {{ color: {FG}; }}
ads--CDockWidgetTab[activeTab="true"] QLabel {{ color: {FG}; }}
ads--CDockAreaTitleBar {{ background: {BG}; }}
"""


def apply(app: QApplication):
    app.setStyle("Fusion")
    p = QPalette()
    for role, col in ((QPalette.Window, BG), (QPalette.Base, PANEL), (QPalette.AlternateBase, BG), (QPalette.Text, FG),
                      (QPalette.WindowText, FG), (QPalette.Button, PANEL), (QPalette.ButtonText, FG),
                      (QPalette.Highlight, ACCENT), (QPalette.HighlightedText, "#000000"), (QPalette.ToolTipBase, PANEL),
                      (QPalette.ToolTipText, FG)):
        p.setColor(role, QColor(col))
    app.setPalette(p)
    app.setStyleSheet(QSS)
