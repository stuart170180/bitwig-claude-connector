"""Drive Bitwig's own user interface with the mouse and keyboard, for what the controller API cannot do (sidechain source, FX track names).

How it works: take a real screen grab of Bitwig's window (a grab, not PrintWindow, so popup menus are included), read the text on it with an
offline OCR (rapidocr), find the label to act on, click it. Every action is verified by looking again. Coordinates are window pixels
(the window is normally 1536x864). Needs the OCR package: pip install rapidocr_onnxruntime."""
import ctypes
import time
from ctypes import wintypes

import numpy as np
from PIL import ImageGrab

from bwmcp.control import screenshot

user32 = ctypes.windll.user32
_ocr = None


def _engine():
    global _ocr
    if _ocr is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError:
            raise RuntimeError("the UI driver needs OCR: pip install rapidocr_onnxruntime") from None
        _ocr = RapidOCR()
    return _ocr


def window_rect():
    hwnd, _ = screenshot.find_window()
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return hwnd, (r.left, r.top, r.right, r.bottom)


def focus():
    hwnd, _ = window_rect()
    user32.ShowWindow(hwnd, 9)
    user32.keybd_event(0x12, 0, 0, 0)
    user32.SetForegroundWindow(hwnd)
    user32.keybd_event(0x12, 0, 2, 0)
    time.sleep(0.3)


def grab():
    """PIL image of Bitwig's window as it is on screen (popups included)."""
    _, box = window_rect()
    return ImageGrab.grab(bbox=box)


def read_text(image=None, region=None, min_score=0.5):
    """OCR -> [{'text', 'x', 'y', 'w', 'h', 'cx', 'cy', 'score'}] in window pixels, optionally only inside region = (x0, y0, x1, y1)."""
    im = image if image is not None else grab()
    res, _ = _engine()(np.asarray(im.convert("RGB")))
    out = []
    for box, text, score in res or []:
        xs, ys = [p[0] for p in box], [p[1] for p in box]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        if float(score) < min_score:
            continue
        if region and not (region[0] <= (x0 + x1) / 2 <= region[2] and region[1] <= (y0 + y1) / 2 <= region[3]):
            continue
        out.append({"text": text.strip(), "x": int(x0), "y": int(y0), "w": int(x1 - x0), "h": int(y1 - y0), "cx": int((x0 + x1) / 2),
                    "cy": int((y0 + y1) / 2), "score": round(float(score), 2)})
    return sorted(out, key=lambda t: (t["cy"] // 8, t["cx"]))


def find(label: str, region=None, exact=False, items=None):
    """First OCR item whose text contains (or equals) label, case-insensitive; None if not on screen."""
    want = label.strip().lower()
    for it in items if items is not None else read_text(region=region):
        t = it["text"].lower()
        if (t == want) if exact else (want in t):
            return it
    return None


def click(x, y, double=False, right=False, refocus=True):
    """Click at window pixel (x, y); the user's pointer is put back afterwards."""
    _, (l, t, _r, _b) = window_rect()
    if refocus:
        focus()
    old = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(old))
    user32.SetCursorPos(l + int(x), t + int(y))
    time.sleep(0.15)
    down, up = (0x0008, 0x0010) if right else (0x0002, 0x0004)
    for _ in range(2 if double else 1):
        user32.mouse_event(down, 0, 0, 0, 0)
        time.sleep(0.07)
        user32.mouse_event(up, 0, 0, 0, 0)
        time.sleep(0.07)
    time.sleep(0.2)
    user32.SetCursorPos(old.x, old.y)


def alt_click(x, y):
    """Alt+click (Bitwig's 'Rename' gesture on tracks and devices)."""
    focus()                                  # focus first: focusing taps Alt itself, which would release the Alt held for the click
    user32.keybd_event(0x12, 0, 0, 0)
    try:
        click(x, y, refocus=False)
    finally:
        user32.keybd_event(0x12, 0, 2, 0)


def region_changed(before, after, box, threshold=3.0) -> bool:
    """Did the pixels inside box = (x0, y0, x1, y1) change between two grabs? (used to see that a text field went into edit mode)"""
    a = np.asarray(before.crop(box).convert("L"), dtype=float)
    b = np.asarray(after.crop(box).convert("L"), dtype=float)
    return float(np.abs(a - b).mean()) > threshold


def became_darker(before, after, box, drop=15.0) -> bool:
    """True when the mean brightness inside box fell by at least `drop` (Bitwig draws an edit field as a dark box)."""
    a = float(np.asarray(before.crop(box).convert("L"), dtype=float).mean())
    b = float(np.asarray(after.crop(box).convert("L"), dtype=float).mean())
    return a - b >= drop


def caret_blinking(box, seconds=1.3, threshold=0.15) -> bool:
    """True when something inside box = (x0, y0, x1, y1) flickers: a text field in edit mode shows a blinking caret, a field that is NOT in edit mode does not.
    Use before typing: letters sent to a non-edit-mode Bitwig are keyboard shortcuts (space = play, M = mute, E = editor ...)."""
    t0 = time.time()
    frames = []
    while time.time() - t0 < seconds:
        frames.append(np.asarray(grab().crop(box).convert("L"), dtype=float))
        time.sleep(0.12)
    return any(float(np.abs(a - b).mean()) > threshold for a in frames for b in frames)


def type_text_safe(text: str, box):
    """type_text, but only after caret_blinking(box) proved the field is in edit mode; raises (and types nothing) otherwise."""
    if not caret_blinking(box):
        raise RuntimeError("the text field is not in edit mode (no blinking caret): not typing, letters would be Bitwig shortcuts")
    type_text(text)


def click_text(label: str, region=None, exact=False, wait=0.8, double=False):
    it = find(label, region, exact)
    if not it:
        raise RuntimeError(f"'{label}' is not on screen")
    click(it["cx"], it["cy"], double=double)
    time.sleep(wait)
    return it


def key(vk: int):
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.04)
    user32.keybd_event(vk, 0, 2, 0)
    time.sleep(0.05)


def type_text(text: str):
    """Type printable characters into whatever has keyboard focus (letters, digits, space and common punctuation)."""
    for ch in text:
        res = user32.VkKeyScanW(ord(ch))
        vk, shift = res & 0xFF, (res >> 8) & 1
        if res == -1:
            raise ValueError(f"cannot type {ch!r}")
        if shift:
            user32.keybd_event(0x10, 0, 0, 0)
        key(vk)
        if shift:
            user32.keybd_event(0x10, 0, 2, 0)


ESC, ENTER, DELETE, BACKSPACE = 0x1B, 0x0D, 0x2E, 0x08
