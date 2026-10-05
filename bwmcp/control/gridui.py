"""Small helpers for the Grid editor window: pick a palette category and drag a module into an empty cell."""
import ctypes
import time
from ctypes import wintypes

from bwmcp.control import uidriver as u

user32 = ctypes.windll.user32
CATEGORIES = {"I/O": (201, 120), "Oscillator": (201, 144), "Filter": (201, 168), "Level": (201, 192), "Display": (272, 120), "Random": (272, 144),
              "Shaper": (272, 168), "Pitch": (272, 192), "Phase": (343, 120), "LFO": (343, 144), "Delay/FX": (343, 168), "Math": (343, 192),
              "Data": (414, 120), "Envelope": (414, 144), "Mix": (414, 168), "Logic": (414, 192)}   # window pixels (1536x864) of the editor's category list


def drag(x0, y0, x1, y1):
    """Left-button drag from (x0, y0) to (x1, y1) in window pixels; the user's pointer is restored."""
    _, (left, top, _r, _b) = u.window_rect()
    u.focus()
    old = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(old))
    user32.SetCursorPos(left + x0, top + y0)
    time.sleep(0.2)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.2)
    for i in range(1, 11):
        user32.SetCursorPos(left + int(x0 + (x1 - x0) * i / 10), top + int(y0 + (y1 - y0) * i / 10))
        time.sleep(0.05)
    time.sleep(0.3)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(0.5)
    user32.SetCursorPos(old.x, old.y)


def category(name):
    x, y = CATEGORIES[name]
    u.click(x, y)
    time.sleep(0.8)


def place_module(label, x, y):
    """With a category open in the palette, drag the module whose label OCRs as `label` to the grid cell at (x, y). Returns False if it is not in the palette."""
    it = u.find(label, region=(455, 110, 1310, 205), exact=True)
    if not it:
        return False
    drag(it["cx"], it["cy"] - 40, x, y)
    return True
