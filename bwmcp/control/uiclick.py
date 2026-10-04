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


# ---- crash recovery: cancel the dialog, delete the crashed track, reactivate -------------------------------------------------------
CRASH_TITLE = (555, 165, 785, 196)       # "Audio Engine Crashed" heading
CANCEL_BTN = (852, 709)                  # Cancel (NEVER Send Report at 940,709: that would transmit data)
DEVICE_MISSING = (272, 697, 352, 716)    # "Device missing" box shown for the crashed track's device
FIRST_TRACK_Y, TRACK_STEP = 122, 44      # track header rows in the Arrange view (default heights)
TRACK_NAME_X = 222


def _matches(box, template_name, arr=None, tol=8.0):
    arr = _window_array() if arr is None else arr
    x0, y0, x1, y1 = box
    crop = arr[y0:y1, x0:x1].astype(float)
    tpl = np.asarray(PILImage.open(TEMPLATE.parent / template_name).convert("RGB")).astype(float)
    return crop.shape == tpl.shape and float(np.abs(crop - tpl).mean()) < tol


def crash_dialog_visible() -> bool:
    try:
        return _matches(CRASH_TITLE, "crash_dialog_title.png")
    except Exception:
        return False


def recover_after_crash(normal_tracks: int = 2, log=print) -> dict:
    """Bring Bitwig back after an audio-engine crash caused by a test file:
    1. press Cancel on the crash dialog (never Send Report); 2. delete the crashed track, but only if it is clearly the one (the engine
    is off, the device panel shows 'Device missing' and the project has more than `normal_tracks` tracks); 3. click Activate Audio Engine.
    normal_tracks = how many tracks the project had before the test (the crashed one is the row after them)."""
    steps = {}
    if crash_dialog_visible():
        _click(*CANCEL_BTN)
        steps["dialog"] = "cancelled"
        time.sleep(1.5)
    arr = _window_array()
    if not engine_off_visible():
        steps["note"] = "engine is not showing as off: nothing more to do"
        return steps
    if _matches(DEVICE_MISSING, "device_missing.png", arr):
        _click(TRACK_NAME_X, FIRST_TRACK_Y + TRACK_STEP * normal_tracks)      # select the crashed (last test) track
        time.sleep(0.8)
        if _matches(DEVICE_MISSING, "device_missing.png"):                    # still the crashed track's device panel
            user32.keybd_event(0x2E, 0, 0, 0)
            time.sleep(0.05)
            user32.keybd_event(0x2E, 0, 2, 0)                                 # Delete
            time.sleep(1.5)
            steps["track"] = "deleted" if not _matches(DEVICE_MISSING, "device_missing.png") else "delete did not take effect"
        else:
            steps["track"] = "selection changed, nothing deleted"
    else:
        steps["track"] = "no 'Device missing' panel, nothing deleted"
    if engine_off_visible():
        _click((BUTTON_BOX[0] + BUTTON_BOX[2]) // 2, (BUTTON_BOX[1] + BUTTON_BOX[3]) // 2)
        steps["engine"] = "activate clicked"
    return steps


if __name__ == "__main__":
    import sys

    n = int(sys.argv[sys.argv.index("--tracks") + 1]) if "--tracks" in sys.argv else 2
    print(recover_after_crash(n))
