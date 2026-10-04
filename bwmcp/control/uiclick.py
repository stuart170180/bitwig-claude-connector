"""Click Bitwig's 'Activate Audio Engine' button after the engine has crashed. While the engine is down the controller script is
disconnected, so this is the only way to bring it back without the user. It acts ONLY when the window shows that exact button
(picture comparison with a stored crop), so it can never hit Play or Record by mistake."""
import ctypes
import time
from ctypes import wintypes
from pathlib import Path

import numpy as np
from PIL import Image as PILImage

from bwmcp.control import screenshot

user32 = ctypes.windll.user32
TEMPLATE = Path(__file__).parent / "assets" / "engine_off_button.png"
BUTTON_BOX = (62, 32, 306, 66)            # where the template sits, in window pixels (1536x864 layout)


def _window_array():
    png, _title, _size = screenshot.capture(max_width=100000)
    import io
    return np.asarray(PILImage.open(io.BytesIO(png)).convert("RGB"))


def engine_off_visible() -> bool:
    """True when Bitwig's window shows the 'Activate Audio Engine' button."""
    try:
        arr = _window_array()
    except Exception:
        return False
    x0, y0, x1, y1 = BUTTON_BOX
    crop = arr[y0:y1, x0:x1].astype(float)
    tpl = np.asarray(PILImage.open(TEMPLATE).convert("RGB")).astype(float)
    if crop.shape != tpl.shape:
        return False
    return float(np.abs(crop - tpl).mean()) < 6.0


def _click(x, y):
    hwnd, _ = screenshot.find_window()
    user32.ShowWindow(hwnd, 9)                                   # restore if minimized
    user32.keybd_event(0x12, 0, 0, 0)                            # Alt tap lets us take the foreground
    user32.SetForegroundWindow(hwnd)
    user32.keybd_event(0x12, 0, 2, 0)
    time.sleep(0.4)
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    old = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(old))
    user32.SetCursorPos(r.left + x, r.top + y)
    time.sleep(0.15)
    user32.mouse_event(0x0002, 0, 0, 0, 0)                       # left down
    time.sleep(0.08)
    user32.mouse_event(0x0004, 0, 0, 0, 0)                       # left up
    time.sleep(0.15)
    user32.SetCursorPos(old.x, old.y)                            # put the user's pointer back


def reactivate_engine() -> bool:
    """Click 'Activate Audio Engine' if (and only if) it is showing. Returns whether a click was made."""
    if not engine_off_visible():
        return False
    x0, y0, x1, y1 = BUTTON_BOX
    _click((x0 + x1) // 2, (y0 + y1) // 2)
    return True
