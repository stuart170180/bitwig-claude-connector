"""Toolbar chips: UK clock (Europe/London, GMT/BST automatic) and weather for a UK place (click to change it)."""
import datetime as dt
from zoneinfo import ZoneInfo

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QInputDialog, QLabel, QPushButton

from bwapp import work
from bwapp import engine as lm

LONDON = ZoneInfo("Europe/London")


class Clock(QLabel):
    def __init__(self):
        super().__init__()
        self.setToolTip("UK time (Europe/London)")
        t = QTimer(self)
        t.timeout.connect(self.tick)
        t.start(1000)
        self.tick()

    def tick(self):
        n = dt.datetime.now(LONDON)
        self.setText(f" {n:%H:%M:%S} {n.tzname()}   {n:%a} {n.day} {n:%b} ")


class Weather(QPushButton):
    def __init__(self):
        super().__init__("weather...")
        self.setFlat(True)
        self.settings = QSettings("BitwigClaude", "BitwigRemote")
        self.city = self.settings.value("city", "London")
        self.clicked.connect(self.ask)
        t = QTimer(self)
        t.timeout.connect(self.load)
        t.start(10 * 60 * 1000)
        self.load()

    def load(self):
        work.run(lm.get_weather, self.show_weather, self.city)

    def show_weather(self, w, err):
        if err:
            return self.setText(f"weather unavailable ({self.city})")
        self.setText(f"{w['icon']} {w['temp_c']}°C {w['place']} - {w['desc']}, feels {w['feels_c']}°, {w['wind_mph']} mph")
        self.setToolTip(f"Observed {w['observed'].replace('T', ' ')} - click to change location")

    def ask(self):
        c, ok = QInputDialog.getText(self, "Weather", "UK town or city:", text=self.city)
        if ok and c.strip():
            self.city = c.strip()
            self.settings.setValue("city", self.city)
            self.load()
