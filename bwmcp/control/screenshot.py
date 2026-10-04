"""Picture of Bitwig's window, taken with Windows PrintWindow. Read-only: no focus change, nothing is sent to Bitwig.

Bitwig draws its own window, so Windows UI Automation sees no controls (checked); a picture is the only way to read UI-only
things: FX track names and faders, sidechain source dropdowns, gain-reduction and level meters, device displays."""
import ctypes
import io
from ctypes import wintypes

import numpy as np
from PIL import Image as PILImage

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
try:
    user32.SetProcessDPIAware()          # real pixels, not scaled ones
except Exception:
    pass


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


def find_window(prefix: str = "Bitwig Studio"):
    """Largest visible top-level window whose title starts with `prefix`: (handle, title)."""
    found = []
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                if buf.value.startswith(prefix):
                    r = wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(r))
                    found.append(((r.right - r.left) * (r.bottom - r.top), hwnd, buf.value))
        return True

    user32.EnumWindows(proc(cb), 0)
    if not found:
        raise RuntimeError("Bitwig's window was not found (is Bitwig open?)")
    _, hwnd, title = max(found)
    return hwnd, title


def capture(max_width: int = 1600):
    """(PNG bytes, window title, (width, height)). Raises if the window is minimized."""
    hwnd, title = find_window()
    if user32.IsIconic(hwnd):
        raise RuntimeError("Bitwig's window is minimized; restore it first")
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    wdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(wdc)
    bmp = gdi32.CreateCompatibleBitmap(wdc, w, h)
    old = gdi32.SelectObject(mdc, bmp)
    try:
        if not user32.PrintWindow(hwnd, mdc, 2):          # 2 = PW_RENDERFULLCONTENT (needed for GPU-drawn windows)
            raise RuntimeError("PrintWindow failed")
        hdr = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(hdr), 0)
    finally:
        gdi32.SelectObject(mdc, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mdc)
        user32.ReleaseDC(hwnd, wdc)
    px = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4)[:, :, [2, 1, 0]]
    img = PILImage.fromarray(px)
    if img.getbbox() is None or px.max() == 0:
        raise RuntimeError("the picture came back blank (window hidden or on a locked screen)")
    if w > max_width:
        img = img.resize((max_width, int(h * max_width / w)), PILImage.LANCZOS)
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue(), title, (w, h)
