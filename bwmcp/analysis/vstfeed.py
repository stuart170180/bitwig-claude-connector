"""Receiver for the BW Remote VST3 (bwremote_vst/): audio and meters straight from inside Bitwig instead of through the sound card.

Two channels, both local only:
  1. Telemetry: signed UDP packets to 127.0.0.1:8790, ten per second - {"sig": HMAC-SHA256(key, body), "body": {...}} - peak, RMS, momentary LUFS,
     correlation, width, 24 spectrum bands, host tempo / position / playing. Packets with a wrong signature are counted and dropped.
  2. Audio: the plug-in keeps the last 30 s of whatever reaches it in a memory-mapped ring file (%APPDATA%\\BitwigClaude\\vst_capture.bin);
     `read_audio` copies the newest frames out, so analysis does not depend on the sound card, its driver or loopback.
The dedicated API key: every plug-in instance makes its own 256-bit key at load and writes it to a new file in %APPDATA%/BitwigClaude/keys (Bitwig's
plug-in host shows plug-ins a private copy of existing files, so a key file shared by both sides cannot work). Each packet carries an 8-character key id
("kid" = first 8 hex of HMAC(key, "kid")); the receiver finds the key with that id. Keys never travel over UDP and are never printed or returned."""
import hashlib
import hmac
import json
import os
import socket
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np

PORTS = range(8790, 8796)      # the plug-in sends every packet to all six; each receiver (MCP server, live monitor, desktop app...) owns one
HEADER = 64


def data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    d = Path(base) / "BitwigClaude"
    d.mkdir(parents=True, exist_ok=True)
    return d


def keys_dir() -> Path:
    d = data_dir() / "keys"
    d.mkdir(parents=True, exist_ok=True)
    return d


def kid_of(key: str) -> str:
    return hmac.new(key.encode("utf-8"), b"kid", hashlib.sha256).hexdigest()[:8]


def load_keys() -> dict:
    """{kid: key} from every vst_key_*.txt file; keys older than two days are deleted."""
    out = {}
    now = time.time()
    for f in keys_dir().glob("vst_key_*.txt"):
        try:
            if now - f.stat().st_mtime > 2 * 86400:
                f.unlink()
                continue
            k = f.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if len(k) >= 32:
            out[kid_of(k)] = k
    return out


def forget_keys() -> int:
    """Delete every key file (running plug-in instances keep working only until they are reloaded; they cannot be verified any more)."""
    n = 0
    for f in keys_dir().glob("vst_key_*.txt"):
        try:
            f.unlink()
            n += 1
        except OSError:
            pass
    return n


class Feed:
    def __init__(self):
        self.keys = load_keys()
        self._rescanned = 0.0
        self.latest = None
        self.latest_at = 0.0
        self.history = deque(maxlen=600)          # one minute of telemetry
        self.ok = 0
        self.bad = 0
        self.unknown = 0
        self.port = None
        self._sock = None
        self._thread = None
        self._stop = threading.Event()

    def start(self):
        if self._thread and self._thread.is_alive():
            return self
        self._stop.clear()
        s = None
        for port in PORTS:
            t = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                t.bind(("127.0.0.1", port))                  # no SO_REUSEADDR: on Windows that would let two receivers share a port and split the packets
                s, self.port = t, port
                break
            except OSError:
                t.close()
        if s is None:
            raise RuntimeError("all VST telemetry ports (8790-8795) are taken")
        s.settimeout(0.5)
        self._sock = s
        self._thread = threading.Thread(target=self._loop, daemon=True, name="vstfeed")
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._sock:
            self._sock.close()

    def _loop(self):
        while not self._stop.is_set():
            try:
                data, _ = self._sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                return
            self.handle(data.decode("utf-8", "replace"))

    def _key_for(self, kid):
        k = self.keys.get(kid)
        if k is None and time.time() - self._rescanned > 1.0:       # a plug-in instance started after us: look for its new key file
            self._rescanned = time.time()
            self.keys = load_keys()
            k = self.keys.get(kid)
        return k

    def handle(self, text: str) -> bool:
        """Verify and store one packet (also used by the tests)."""
        i = text.find('"body":')
        if not text.startswith('{"sig":"') or i < 0 or not text.endswith("}"):
            self.bad += 1
            return False
        sig = text[8:text.index('"', 8)]
        body = text[i + 7:-1]
        try:
            msg = json.loads(body)
        except ValueError:
            self.bad += 1
            return False
        key = self._key_for(msg.get("kid") if isinstance(msg, dict) else None)
        if key is None:
            self.unknown += 1
            return False
        want = hmac.new(key.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, want):
            self.bad += 1
            return False
        self.latest, self.latest_at = msg, time.time()
        self.history.append((self.latest_at, msg))
        self.ok += 1
        return True

    def alive(self, max_age=2.0) -> bool:
        return self.latest is not None and time.time() - self.latest_at < max_age

    def status(self) -> dict:
        cap = capture_info()
        return {"listening": bool(self._thread and self._thread.is_alive()), "port": self.port, "alive": self.alive(), "packets_ok": self.ok, "packets_rejected": self.bad, "packets_unknown_key": self.unknown, "keys_known": len(self.keys),
                "age_s": round(time.time() - self.latest_at, 2) if self.latest else None, "latest": self.latest, "capture": cap,
                "keys_dir": str(keys_dir())}


_feed = None


def feed() -> Feed:
    global _feed
    if _feed is None:
        _feed = Feed().start()
    return _feed


# ---------------------------------------------------------------- audio from the memory-mapped ring
def _capture_file() -> Path:
    return data_dir() / "vst_capture.bin"


def capture_info():
    p = _capture_file()
    if not p.exists() or p.stat().st_size < HEADER:
        return None
    with open(p, "rb") as f:
        h = f.read(HEADER)
    if h[:4] != b"BWRC":
        return None
    ver, ch, sr = np.frombuffer(h[4:16], dtype="<u4")
    cap, total = np.frombuffer(h[16:32], dtype="<u8")
    return {"version": int(ver), "channels": int(ch), "sample_rate": int(sr), "capacity_frames": int(cap), "frames_written": int(total)}


def read_audio(seconds: float, wait: bool = True, timeout: float = 5.0):
    """Newest `seconds` of audio as (float32 array [frames, 2], sample_rate). With wait=True, waits until that much new audio has arrived first
    (so the result starts now, like a live capture); with wait=False returns what is already in the ring."""
    info = capture_info()
    if not info:
        raise RuntimeError("no BW Remote capture file: load the BW Remote VST3 on the master track and press play")
    sr, ch, cap = info["sample_rate"], info["channels"], info["capacity_frames"]
    frames = int(seconds * sr)
    if frames > cap - sr:
        raise ValueError(f"the ring holds {cap / sr:.0f} s; ask for at most {(cap - sr) / sr:.0f} s")
    if wait:
        start = info["frames_written"]
        t0 = time.time()
        while True:
            info = capture_info()
            if info["frames_written"] - start >= frames:
                break
            if time.time() - t0 > seconds + timeout:
                raise RuntimeError("the VST is not delivering audio (is Bitwig playing and the plug-in enabled?)")
            time.sleep(0.05)
    total = info["frames_written"]
    mm = np.memmap(_capture_file(), dtype="<f4", mode="r", offset=HEADER, shape=(cap, ch))
    end = total
    idx = (np.arange(end - frames, end) % cap).astype(np.int64)
    out = np.array(mm[idx], dtype=np.float32)
    del mm
    if info["frames_written"] - total > cap - frames - sr:       # overwritten while copying: do not return torn data
        raise RuntimeError("capture ring overwritten while reading; try again")
    return out, sr


def read_frames(start: int, count: int):
    """Frames [start, start+count) of the ring (absolute frame numbers as in frames_written), or None if they were already overwritten / not written yet."""
    info = capture_info()
    if not info:
        return None, None
    cap, ch, sr, total = info["capacity_frames"], info["channels"], info["sample_rate"], info["frames_written"]
    if start + count > total or total - start > cap - sr:
        return None, sr
    mm = np.memmap(_capture_file(), dtype="<f4", mode="r", offset=HEADER, shape=(cap, ch))
    out = np.array(mm[(np.arange(start, start + count) % cap).astype(np.int64)], dtype=np.float32)
    del mm
    return out, sr
