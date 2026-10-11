"""Sample mode block: sample list, waveform, BPM / length / bars, play / pause / rewind / fast-forward / loop, send to Bitwig."""
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPushButton, QSlider, QVBoxLayout, QWidget)

from bwapp import work
from bwapp.links import LINK, SHARP
from bwapp.audio import decode, process, tempo
from bwapp.audio.player import Player
from bwapp.audio.waveform import Waveform
from bwmcp.core.bridge import bw
from bwmcp.library import samples


class Loader(QThread):
    ready = Signal(str, object, int, dict)       # path, data, sr, analysis

    def __init__(self, path, beats):
        super().__init__()
        self.path, self.beats = path, beats

    def run(self):
        data, sr = decode.load(self.path)
        info = tempo.analyse(data.mean(axis=1), sr, self.beats)
        info["key"], info["key_conf"] = process.detect_key(data.mean(axis=1), sr)
        self.ready.emit(self.path, data, sr, info)


class SamplePanel(QWidget):
    sent = Signal(str)

    def __init__(self):
        super().__init__()
        self.player, self.path, self.info, self.loader = Player(), None, {}, None
        self.orig, self.processed, self.project_bpm, self.tag = None, False, None, "processed"
        self.factor, self.st = 1.0, 0.0
        self.setAcceptDrops(True)
        self.setMinimumWidth(430)
        self.files = []
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter by name...")
        self.add_folder_b, self.add_files_b = QPushButton("Add folder"), QPushButton("Add files")
        self.list = QListWidget()
        self.list.setMinimumHeight(110)
        self.wave = Waveform()
        self.title = QLabel("No sample loaded")
        self.title.setStyleSheet("font-size:15px;font-weight:600")
        self.stats = QLabel("")
        self.stats.setProperty("role", "dim")
        self.sig = QComboBox()
        self.sig.addItems(["4/4", "3/4", "6/8", "5/4", "7/8", "2/4"])
        self.time = QLabel("0:00.0 / 0:00.0")
        self.rew, self.play, self.fwd = QPushButton("<<"), QPushButton("Play"), QPushButton(">>")
        self.stop_b = QPushButton("Stop")
        self.loop = QCheckBox("Loop")
        self.speed = QSlider()
        self.speed.setOrientation(Qt.Horizontal)
        self.speed.setRange(50, 200)
        self.speed.setValue(100)
        self.speed_l = QLabel("1.00x")
        self.vol = QSlider()
        self.vol.setOrientation(Qt.Horizontal)
        self.vol.setRange(0, 100)
        self.vol.setValue(40)
        self.vol.setMaximumWidth(90)
        self.vol.setMinimumWidth(60)
        self.speed.setMinimumWidth(70)
        self.vol.setToolTip("Playback volume")
        self.player.gain = 0.16
        self.send_b = QPushButton("Send to Bitwig")
        self.send_b.setToolTip("Puts the sample on a new audio track as a clip in the first slot")
        self.msg = QLabel("")
        self.msg.setProperty("role", "dim")
        self.proj = QLabel("Project: -")
        self.match_b = QPushButton("Match tempo")
        self.match_b.setMinimumWidth(110)
        self.match_b.setToolTip("Time-stretches a copy so the sample's BPM equals the Bitwig project tempo (pitch stays the same)")
        self.semi = QDoubleSpinBox()
        self.semi.setRange(-12, 12)
        self.semi.setSingleStep(1)
        self.semi.setSuffix(" st")
        self.pitch_b, self.orig_b, self.save_b = QPushButton("Shift pitch"), QPushButton("Original"), QPushButton("Save copy")
        proc = QHBoxLayout()
        for w in (self.proj, self.match_b):
            proc.addWidget(w)
        proc.addStretch()
        proc2 = QHBoxLayout()
        for w in (QLabel("Pitch"), self.semi, self.pitch_b, self.orig_b, self.save_b):
            proc2.addWidget(w)
        proc2.addStretch()
        top = QHBoxLayout()
        for w in (self.add_folder_b, self.add_files_b, self.filter):
            top.addWidget(w)
        ctl = QHBoxLayout()
        for w in (self.rew, self.play, self.fwd, self.stop_b, self.loop, QLabel("Speed"), self.speed, self.speed_l, QLabel("Vol"), self.vol):
            ctl.addWidget(w)
        ctl.addStretch()
        ctl.addWidget(self.time)
        meta = QHBoxLayout()
        for w in (QLabel("Time signature"), self.sig):
            meta.addWidget(w)
        meta.addStretch()
        meta.addWidget(self.send_b)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.list, 2)
        lay.addWidget(self.title)
        lay.addWidget(self.stats)
        lay.addWidget(self.wave, 2)
        lay.addLayout(ctl)
        lay.addLayout(meta)
        lay.addLayout(proc)
        lay.addLayout(proc2)
        lay.addWidget(self.msg)
        self.add_folder_b.clicked.connect(self.pick_folder)
        self.add_files_b.clicked.connect(self.pick_files)
        self.filter.textChanged.connect(self.refill)
        self.list.currentItemChanged.connect(lambda cur, _p: cur and self.open(cur.data(0x100)))
        self.play.clicked.connect(self.toggle)
        self.stop_b.clicked.connect(self.stop)
        self.rew.pressed.connect(lambda: self.hold(-4.0))
        self.rew.released.connect(self.release)
        self.fwd.pressed.connect(lambda: self.hold(4.0))
        self.fwd.released.connect(self.release)
        self.loop.toggled.connect(lambda on: setattr(self.player, "loop", on))
        self.speed.valueChanged.connect(self.set_speed)
        self.vol.valueChanged.connect(lambda v: setattr(self.player, "gain", (v / 100) ** 2))
        self.sig.currentTextChanged.connect(self.regrid)
        self.wave.seek.connect(self.player.seek)
        self.send_b.clicked.connect(self.send)
        self.match_b.clicked.connect(self.match_tempo)
        self.pitch_b.clicked.connect(self.shift)
        self.orig_b.clicked.connect(self.restore)
        self.save_b.clicked.connect(self.save_copy)
        self.sent.connect(self.msg.setText)
        self.tick = QTimer(self)
        self.tick.timeout.connect(self.update_time)
        self.tick.start(40)
        self.load_library()

    # library ---------------------------------------------------------------------------------------------------------
    def load_library(self):
        self.files = []
        for folder in samples.folders():
            if Path(folder).is_dir():
                self.files += decode.scan_folder(folder, 3000)
        self.refill()

    def refill(self):
        q = self.filter.text().lower()
        self.list.clear()
        for p in self.files:
            if q in p.name.lower():
                it = QListWidgetItem(p.name)
                it.setData(0x100, str(p))
                it.setToolTip(str(p))
                self.list.addItem(it)

    def pick_folder(self):
        f = QFileDialog.getExistingDirectory(self, "Add a sample folder")
        if f:
            samples.add_folder(f)
            self.load_library()

    def pick_files(self):
        fs, _ = QFileDialog.getOpenFileNames(self, "Add samples", "", "Audio (*.wav *.aif *.aiff *.flac *.ogg *.mp3)")
        self.files = sorted({*self.files, *[Path(f) for f in fs]}, key=lambda p: p.name.lower())
        self.refill()
        if fs:
            self.open(fs[0])

    # loading ---------------------------------------------------------------------------------------------------------
    def beats(self):
        num, den = self.sig.currentText().split("/")
        return int(num) * 4 / int(den)

    def open(self, path):
        self.stop()
        self.path = str(path)
        self.title.setText(Path(path).name)
        self.stats.setText("analysing...")
        self.loader = Loader(self.path, self.beats())
        self.loader.ready.connect(self.loaded)
        self.loader.start()

    def loaded(self, path, data, sr, info):
        if path != self.path:
            return
        self.info, self.orig, self.processed, self.factor, self.st = info, (data, sr, dict(info)), False, 1.0, 0.0
        self.player.load(data, sr)
        self.wave.set_sample(data, sr)
        self.show_stats(sr, data.shape[0])
        self.wave.set_grid(info["bpm"], self.beats())
        if info.get("key") and info.get("key_conf", 0) > 0.6:
            tonic, scale = info["key"].split()
            LINK.sample_key.emit(SHARP.get(tonic, tonic), scale)

    def show_stats(self, sr=None, frames=None):
        i = self.info
        bpm = f"{i['bpm']:.1f} BPM ({i['method']}, confidence {i['confidence']:.0%})" if i.get("bpm") else "no tempo (one-shot)"
        bars = f"  |  {i['bars']:.2f} bars" if i.get("bars") else ""
        key = f"  |  key {i['key']}" if i.get("key") and i.get("key_conf", 0) > 0.6 else ""
        tag = "  |  PROCESSED" if self.processed else ""
        self.stats.setText(f"{bpm}  |  {i['seconds']:.2f} s{bars}{key}  |  {self.player.sr} Hz{tag}")

    def regrid(self, *_):
        if self.player.duration:
            from bwapp.audio import tempo as t
            self.info = t.analyse(self.player.data.mean(axis=1), self.player.sr, self.beats())
            self.show_stats()
            self.wave.set_grid(self.info["bpm"], self.beats())

    # transport -------------------------------------------------------------------------------------------------------
    def toggle(self):
        self.player.toggle()
        self.play.setText("Pause" if self.player.playing else "Play")

    def stop(self):
        self.player.pause()
        self.player.seek(0)
        self.play.setText("Play")

    def hold(self, rate):
        """Rewind / fast-forward while the button is held: plays at -4x / +4x, then goes back to the set speed."""
        self._resume = self.player.playing
        self.player.rate = rate
        self.player.playing = True

    def release(self):
        self.player.rate = self.speed.value() / 100
        self.player.playing = getattr(self, "_resume", False)
        self.play.setText("Pause" if self.player.playing else "Play")

    def set_speed(self, v):
        self.speed_l.setText(f"{v / 100:.2f}x")
        self.player.rate = v / 100

    def update_time(self):
        s, d = self.player.seconds, self.player.duration
        self.time.setText(f"{int(s // 60)}:{s % 60:04.1f} / {int(d // 60)}:{d % 60:04.1f}")
        self.wave.set_position(s)
        if not self.player.playing and self.play.text() == "Pause":
            self.play.setText("Play")

    # processing ------------------------------------------------------------------------------------------------------
    def showEvent(self, e):
        super().showEvent(e)
        self.read_project()

    def read_project(self, then=None):
        def got(r, err):
            if err:
                return self.proj.setText("Project: Bitwig not reachable")
            self.project_bpm = float(r["tempo"])
            self.proj.setText(f"Project: {self.project_bpm:g} BPM")
            if then:
                then()
        work.run(lambda: bw.call("get_session"), got)

    def match_tempo(self):
        if not self.orig or not self.orig[2].get("bpm"):
            return self.msg.setText("Load a loop with a detected tempo first.")
        def go():
            self.factor = self.project_bpm / self.orig[2]["bpm"]
            self.render()
        self.read_project(go)

    def shift(self):
        self.st = self.semi.value()
        self.render()

    def render(self):
        """Renders the original with the current tempo factor and pitch shift together."""
        if not self.orig:
            return
        data, sr, info = self.orig
        factor, semitones = self.factor, self.st
        self.msg.setText("rendering...")
        self.tag = (f"{self.project_bpm:g}bpm" if abs(factor - 1) > 1e-4 else "") + (f"{semitones:+.0f}st" if abs(semitones) > 1e-4 else "") or "processed"

        def done(y, err):
            if err:
                return self.msg.setText("Could not process: " + err)
            keep = self.player.loop
            self.player.load(y, sr)
            self.player.loop = keep
            self.wave.set_sample(y, sr)
            i = dict(info)
            i["seconds"] = len(y) / sr
            if i.get("bpm"):
                i["bpm"] *= factor
            self.info, self.processed = i, True
            self.show_stats()
            self.wave.set_grid(i.get("bpm"), self.beats())
            self.msg.setText(f"Processed: speed x{factor:.3f}, pitch {semitones:+.0f} st. Send to Bitwig uses this version.")
        work.run(process.stretch, done, data, sr, factor, semitones)

    def restore(self):
        if self.orig:
            data, sr, info = self.orig
            self.player.load(data, sr)
            self.wave.set_sample(data, sr)
            self.info, self.processed, self.factor, self.st = dict(info), False, 1.0, 0.0
            self.semi.setValue(0)
            self.show_stats()
            self.wave.set_grid(info.get("bpm"), self.beats())
            self.msg.setText("Original restored.")

    def save_copy(self):
        if self.path and self.processed:
            self.msg.setText("Saved " + str(process.save_copy(self.player.data, self.player.sr, self.path, self.tag)))
        else:
            self.msg.setText("Nothing processed yet.")

    # drag and drop ---------------------------------------------------------------------------------------------------
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        added = []
        for u in e.mimeData().urls():
            p = Path(u.toLocalFile())
            if p.is_dir():
                added += decode.scan_folder(p, 2000)
            elif p.suffix.lower() in decode.EXTS:
                added.append(p)
        if added:
            self.files = sorted({*self.files, *added}, key=lambda q: q.name.lower())
            self.refill()
            self.open(added[0])

    # Bitwig ----------------------------------------------------------------------------------------------------------
    def send(self):
        if not self.path:
            return
        self.msg.setText("sending...")
        path = str(process.save_copy(self.player.data, self.player.sr, self.path, self.tag)) if self.processed else self.path

        def job():
            try:
                from bwmcp.tools.library import load_sample
                r = load_sample(path, mode="clip")
                self.sent.emit(f"Sent to Bitwig: track {r.get('track_index', r.get('track', '?'))}")
            except Exception as e:  # noqa: BLE001
                self.sent.emit(f"Could not send: {e}")
        threading.Thread(target=job, daemon=True).start()

    def closeEvent(self, e):
        self.player.close()
        super().closeEvent(e)

