"""Sample player on a sounddevice callback: play / pause / seek / rewind / fast-forward / loop, with speed (varispeed)."""
import numpy as np
import sounddevice as sd


class Player:
    def __init__(self):
        self.data = np.zeros((0, 2), np.float32)
        self.sr = 44100
        self.pos = 0.0           # frames (float so slow / fast speeds stay accurate)
        self.rate = 1.0          # 1.0 = normal; negative = reverse (used while rewinding)
        self.playing = False
        self.loop = False
        self.gain = 0.9
        self.stream = None

    def load(self, data, sr):
        self.pause()
        self.data, self.sr, self.pos = data.astype(np.float32), int(sr), 0.0
        self._open()

    def _open(self):
        if self.stream is not None:
            self.stream.close()
        self.stream = sd.OutputStream(samplerate=self.sr, channels=2, dtype="float32", callback=self._cb, latency="low")
        self.stream.start()

    def _cb(self, out, frames, _t, _status):
        n = len(self.data)
        if not self.playing or n < 2:
            out[:] = 0
            return
        idx = self.pos + np.arange(frames) * self.rate
        if self.loop:
            idx = idx % n
        valid = (idx >= 0) & (idx < n - 1)
        i0 = np.clip(idx.astype(np.int64), 0, n - 2)
        frac = (idx - i0).astype(np.float32)[:, None]
        sig = self.data[i0] * (1 - frac) + self.data[i0 + 1] * frac
        sig[~valid] = 0
        out[:] = sig * self.gain
        self.pos = float(idx[-1] + self.rate)
        if not self.loop and (self.pos >= n - 1 or self.pos < 0):
            self.playing = False
            self.pos = min(max(self.pos, 0.0), float(n - 1))

    def play(self):
        if self.pos >= len(self.data) - 2:
            self.pos = 0.0
        self.rate = abs(self.rate) or 1.0
        self.playing = True

    def pause(self):
        self.playing = False

    def toggle(self):
        self.pause() if self.playing else self.play()

    def seek(self, seconds):
        self.pos = float(np.clip(seconds * self.sr, 0, max(len(self.data) - 1, 0)))

    @property
    def seconds(self):
        return self.pos / self.sr if self.sr else 0.0

    @property
    def duration(self):
        return len(self.data) / self.sr if self.sr else 0.0

    def close(self):
        self.playing = False
        if self.stream is not None:
            self.stream.close()
            self.stream = None
