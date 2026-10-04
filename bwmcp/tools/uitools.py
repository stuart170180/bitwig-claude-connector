"""Tools that drive Bitwig's user interface (mouse + OCR) for what the controller API cannot do: choosing a device's sidechain source, renaming
FX tracks, and reading text off the screen. Each action is verified by reading the screen again. Bitwig must be visible (not minimized)."""
import difflib
import time

from bwmcp.control import uidriver as ui
from bwmcp.core.bridge import bw, deep, tool

DEVICE_PANEL = (166, 585, 1310, 830)
TRACK_LIST = (166, 96, 366, 560)


def _similar(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio()


def _find_name(items, name, region=None, reject_suffix=True):
    best, score = None, 0.0
    for it in items:
        if region and not (region[0] <= it["cx"] <= region[2] and region[1] <= it["cy"] <= region[3]):
            continue
        if reject_suffix and it["text"].rstrip().endswith((")", "(PRE)", "(POST)")):
            continue
        s = _similar(it["text"], name)
        if s > score:
            best, score = it, s
    return best if best is not None and score >= 0.8 else None


def _track_row(items, name):
    """The OCR item of a track-list entry: the best fuzzy match, or, for a long name Bitwig wraps over two lines, the line that is the start
    of the name."""
    it = _find_name(items, name, reject_suffix=False)
    if it:
        return it
    n = _norm(name)
    cands = [i for i in items if len(_norm(i["text"])) >= 4 and n.startswith(_norm(i["text"])) and not i["text"].strip().endswith("dB")]
    return max(cands, key=lambda i: len(_norm(i["text"])), default=None)


def _norm(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def _shows(items, name: str) -> bool:
    """True when some line on screen contains `name` (OCR may drop or add spaces, so compare letters and digits only)."""
    n = _norm(name)
    return any(n and n in _norm(i["text"]) for i in items)


def _close_popups():
    for _ in range(3):
        ui.key(ui.ESC)
        time.sleep(0.2)


@tool()
def read_window_text(region: list[int] | None = None, contains: str | None = None) -> dict:
    """Read the text currently on Bitwig's screen with OCR (cheaper than a picture): every label with its pixel position. region = [x0, y0, x1, y1]
    in window pixels to read only part of the screen (the device panel is about [166, 585, 1310, 830]); contains filters the lines. Use it to
    check values the API cannot report, such as which sidechain source is chosen or an FX track's name."""
    items = ui.read_text(region=tuple(region) if region else None)
    if contains:
        items = [i for i in items if contains.lower() in i["text"].lower()]
    return {"lines": [{"text": i["text"], "x": i["cx"], "y": i["cy"]} for i in items]}


@tool()
def sidechain_source(track_index: int, source_track: str, device: str = "Compressor+", device_index: int | None = None, tap: str = "pre") -> dict:
    """Choose which track a device listens to for its sidechain (the one thing the API cannot set), by clicking Bitwig's own selector.
    track_index = the track the compressor (or gate etc.) is on, device = its name or give device_index, source_track = the trigger track's exact
    name (e.g. 'Kick'), tap = pre (before its fader, so fader moves do not change the ducking) or post. Works for devices with a 'Device Input'
    selector in the device panel (Compressor+, Gate, ...). Bitwig must be on screen; takes about 20 seconds (OCR). Verified by reading the screen."""
    if tap not in ("pre", "post"):
        raise ValueError("tap must be pre or post")
    tree = deep.tree(track_index)
    if device_index is None:
        device_index = next((d["index"] for d in tree if d["name"] == device), None)
        if device_index is None:
            raise ValueError(f"no {device} on track {track_index}")
    bw.call("app_panel", layout="ARRANGE")
    time.sleep(0.6)
    bw.call("select_track", track_index=track_index)
    time.sleep(0.6)
    deep.goto(track_index, device_index)
    time.sleep(0.6)
    items = ui.read_text(region=DEVICE_PANEL)
    if not ui.find("Sidechain FX", items=items):
        bw.call("app_panel", what="devices")                       # the bottom panel may be showing the clip editor
        time.sleep(1.0)
        items = ui.read_text(region=DEVICE_PANEL)
    sc = ui.find("Sidechain FX", items=items)
    if not sc:
        raise RuntimeError("no sidechain selector on screen: select the track and make the device panel visible (device must have a sidechain input). "
                           f"Saw: {[i['text'] for i in items][:25]}")
    dropdown = (sc["cx"] - 68, sc["cy"])
    popup = None
    for _attempt in range(2):                                       # the first click can only select the device
        ui.click(*dropdown)
        time.sleep(0.9)
        popup = ui.read_text(region=(DEVICE_PANEL[0], 590, 900, 830))
        if ui.find("TRACKS", items=popup, exact=True):
            break
    else:
        _close_popups()
        raise RuntimeError(f"the source menu did not open. Saw: {[i['text'] for i in popup][:20]}")
    entry = _find_name(popup, source_track, region=(dropdown[0] - 60, 640, dropdown[0] + 150, 830))
    if not entry:
        names = [i["text"] for i in popup if i["cx"] < dropdown[0] + 150]
        _close_popups()
        raise ValueError(f"'{source_track}' is not in the source list (the track itself is excluded). Menu showed: {names}")
    ui.click(entry["cx"], entry["cy"])
    time.sleep(0.9)
    sub = ui.read_text(region=(DEVICE_PANEL[0], 590, 1000, 830))
    want = f"({tap.upper()})"
    pick = next((i for i in sub if i["text"].upper().rstrip().endswith(want)), None)
    if not pick:
        _close_popups()
        raise RuntimeError(f"no {want} entry appeared. Saw: {[i['text'] for i in sub][:20]}")
    ui.click(pick["cx"], pick["cy"])
    time.sleep(1.0)
    after = ui.read_text(region=DEVICE_PANEL)
    ok = _shows(after, source_track) and not ui.find("Device Input", items=after, exact=True)
    return {"track_index": track_index, "device": tree[device_index]["name"], "source": source_track, "tap": tap, "verified": ok,
            "screen": [i["text"] for i in after][:12]}


@tool()
def rename_fx_track(current_name: str, new_name: str) -> dict:
    """Rename an FX (send) track, which the API cannot do: double-clicks its name in the track list, types the new name and checks the screen.
    current_name = what it is called now (e.g. 'FX 1'). Bitwig must show the Arrange view with the FX track visible."""
    bw.call("app_panel", layout="ARRANGE")
    time.sleep(0.8)
    items = ui.read_text(region=TRACK_LIST)
    it = _track_row(items, current_name)
    if not it:
        raise ValueError(f"no track called '{current_name}' in the track list. Saw: {[i['text'] for i in items][:20]}")
    box = (it["x"] - 4, it["cy"] - 12, it["x"] + it["w"] + 40, it["cy"] + 12)       # tight box around the name: the edit field is dark
    before = ui.grab()
    ui.alt_click(it["cx"], it["cy"])                              # Alt+click = Rename in Bitwig
    time.sleep(0.8)
    if not ui.became_darker(before, ui.grab(), box):
        _close_popups()
        raise RuntimeError("the name field did not enter edit mode, so nothing was typed (typing without it would trigger Bitwig shortcuts)")
    user32 = ui.user32
    user32.keybd_event(0x11, 0, 0, 0)
    ui.key(0x41)                                                  # Ctrl+A: select the old name
    user32.keybd_event(0x11, 0, 2, 0)
    ui.type_text(new_name)
    ui.key(ui.ENTER)
    time.sleep(1.0)
    ok = False
    for _ in range(4):                                            # the name field can take a moment to settle after Enter
        time.sleep(0.6)
        ok = _shows(ui.read_text(region=TRACK_LIST), new_name)
        if ok:
            break
    return {"renamed": current_name, "to": new_name, "verified": ok}


@tool()
def delete_fx_track(name: str) -> dict:
    """Delete an FX (send) track by name, which the API cannot do: right-clicks it, checks that Bitwig's inspector says 'FX TRACK' with exactly
    that name (so nothing else can be deleted by mistake), then presses DELETE in the context menu and checks the track is gone. Undo restores it."""
    bw.call("app_panel", layout="ARRANGE")
    time.sleep(0.8)
    items = ui.read_text(region=TRACK_LIST)
    it = _track_row(items, name)
    if not it:
        raise ValueError(f"no track called '{name}' in the track list. Saw: {[i['text'] for i in items][:20]}")
    ui.click(it["cx"], it["cy"], right=True)
    time.sleep(1.0)
    head = ui.read_text(region=(0, 80, 165, 125))
    if not (_shows(head, "FX TRACK") and (_shows(head, name) or _norm(name).startswith(_norm(it["text"])))):
        _close_popups()
        raise RuntimeError(f"the inspector does not show 'FX TRACK' with '{name}' (it shows {[i['text'] for i in head]}), so nothing was deleted")
    menu = ui.read_text(region=(200, 380, 520, 700))
    btn = ui.find("DELETE", items=menu, exact=True)
    if not btn:
        _close_popups()
        raise RuntimeError(f"no DELETE button in the context menu. Saw: {[i['text'] for i in menu]}")
    ui.click(btn["cx"], btn["cy"])
    time.sleep(1.2)
    gone = not _shows(ui.read_text(region=TRACK_LIST), name)
    return {"deleted": name, "verified": gone}


@tool()
def add_layer(track_index: int, device_index: int) -> dict:
    """Add a layer (a parallel chain) to a layer device such as FX Layer or Instrument Layer, which the API cannot do: shows the device on screen and
    double-clicks its empty layer area (Bitwig's 'Add layer' gesture). Checks the layer count afterwards. Then fill the layers with
    device_insert(..., layer=N)."""
    def layer_count():
        deep.goto(track_index, device_index)
        time.sleep(0.5)
        return len(deep.params(None, 1, 0)["layers"])

    before = layer_count()
    bw.call("app_panel", layout="ARRANGE")
    time.sleep(0.6)
    items = ui.read_text(region=DEVICE_PANEL)
    if not any(i["text"].lower().startswith("layer") for i in items):
        bw.call("app_panel", what="devices")
        time.sleep(1.0)
        items = ui.read_text(region=DEVICE_PANEL)
    layers = sorted((i for i in items if i["text"].lower().startswith("layer") and i["cx"] < 480), key=lambda i: i["cy"])
    if not layers:
        raise RuntimeError(f"no layer list on screen (is the device panel showing the layer device?). Saw: {[i['text'] for i in items][:20]}")
    last = layers[-1]
    ui.click(last["cx"] + 50, last["cy"] + 28 * (before - len(layers) + 1) + 30, double=True)
    time.sleep(1.2)
    after = layer_count()
    return {"track_index": track_index, "device_index": device_index, "layers_before": before, "layers_after": after, "added": after > before}
