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
        n, o = _norm(name), _norm(it["text"])
        if len(n) >= 3 and n in o and len(o) <= len(n) + 3:        # OCR often glues a stray icon character onto the name
            s = max(s, 0.92)
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
    di = ui.find("Device Input", items=items)
    if sc:
        dropdown = (sc["cx"] - 68, sc["cy"])
    elif di:                                                        # a wide device (Sampler) can push the 'Sidechain FX' label off screen: use the chooser itself
        dropdown = (di["cx"], di["cy"])
    else:
        raise RuntimeError("no sidechain selector on screen: select the track and make the device panel visible (device must have a sidechain input). "
                           f"Saw: {[i['text'] for i in items][:25]}")
    popup = None
    for _attempt in range(2):                                       # the first click can only select the device
        ui.click(*dropdown)
        time.sleep(0.9)
        popup = ui.read_text(region=(DEVICE_PANEL[0], 0, 1536, 830))     # the menu opens upwards when the device panel is low on the screen
        if ui.find("TRACKS", items=popup, exact=True):
            break
    else:
        _close_popups()
        raise RuntimeError(f"the source menu did not open. Saw: {[i['text'] for i in popup][:20]}")
    entry = _find_name(popup, source_track, region=(dropdown[0] - 90, 0, dropdown[0] + 150, 830))
    if not entry:
        names = [i["text"] for i in popup if i["cx"] < dropdown[0] + 150]
        _close_popups()
        raise ValueError(f"'{source_track}' is not in the source list (the track itself is excluded). Menu showed: {names}")
    ui.click(entry["cx"], entry["cy"])
    time.sleep(0.9)
    sub = ui.read_text(region=(DEVICE_PANEL[0], 0, 1536, 830))
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


def _clip_segments(image, row_y):
    """x ranges of the clips on the arranger row at row_y: runs of columns that are clearly lighter than the empty background."""
    import numpy as np

    band = np.asarray(image.crop((692, row_y - 14, 1284, row_y + 14)).convert("L"), dtype=float)
    bg = float(np.median(band))
    lit = (np.abs(band - bg) > 18).mean(axis=0) > 0.5
    segs, start = [], None
    for k, v in enumerate(list(lit) + [False]):
        if v and start is None:
            start = k
        elif not v and start is not None:
            if k - start >= 8:
                segs.append((692 + start, 692 + k))
            start = None
    return segs


@tool()
def select_arranger_clip(track_index: int, clip: int = 0, limit: int = 200) -> dict:
    """Select an arranger clip on a track by clicking it in the Arrange view, then read its notes. This is the missing link for clips that
    record_arrangement recorded (the API can only follow Bitwig's own selection). clip = which clip on that track, counted from the left (0 = the
    first). Bitwig must show the Arrange view with the track's clips on screen (scroll or zoom first, e.g. edit_action 'zoom_to_fit'). Returns the
    clip info and notes, or exists=false when no clip is found."""
    bw.call("app_panel", layout="ARRANGE")
    time.sleep(0.7)
    names = {t["index"]: t["name"] for t in bw.call("get_session")["tracks"]}
    if track_index not in names:
        raise ValueError(f"no track {track_index}")
    # Track rows are evenly spaced (44 px at default height, first row at y=122); OCR is unreliable on the selected (light) row.
    row_y = 122 + 44 * track_index
    if row_y > 480:
        raise RuntimeError(f"track {track_index} is below the visible track list; scroll Bitwig's arranger or collapse tracks first")
    segs = _clip_segments(ui.grab(), row_y)
    if clip >= len(segs):
        return {"exists": False, "clips_found_on_screen": len(segs), "hint": "no such clip on that track in the visible part of the arranger"}
    x0, x1 = segs[clip]
    ui.click((x0 + x1) // 2, row_y + 4)
    time.sleep(1.0)
    from bwmcp.control import arrclipsdev

    info = arrclipsdev.arrclip_info(bw)
    if not info.get("exists"):
        return {"exists": False, "clicked": {"x": (x0 + x1) // 2, "y": row_y + 4}, "hint": "the click did not select a clip"}
    return {"clip": clip, "clips_on_track": len(segs), "info": info, **arrclipsdev.arrclip_notes(bw, limit=limit)}


BROWSER_SEARCH = (1340, 150, 1520, 172)


@tool()
def insert_plugin(name: str, track_index: int = -1) -> dict:
    """Insert a plug-in or device that the controller API cannot reach by name (a VST3/CLAP/VST2 plug-in such as 'BW Remote') through Bitwig's own browser:
    selects the track (-1 = the master chain: its 'PROJECT' column), clears the browser search box, types the name ONLY after a blinking caret proves the
    box is in edit mode, double-clicks the exact result, and checks the device list. Bitwig must show the Arrange view with the device browser open
    ('Everything' tab). Returns the track's devices afterwards."""
    before = [d["name"] for d in deep.tree(track_index)]
    ui.focus()
    if track_index < 0:
        ui.click(178, 705)                                     # the PROJECT column of the device panel = master chain
    else:
        bw.call("select_track", track_index=track_index)
        time.sleep(1.2)
        if bw.call("list_devices")["track"] != bw.call("get_session")["tracks"][track_index]["name"]:
            raise RuntimeError("Bitwig has not selected that track yet")
    time.sleep(0.8)
    ui.click(1513, 160)                                        # the X clears old search text (the field keeps it between searches)
    time.sleep(0.6)
    ui.click(1420, 160)
    time.sleep(0.4)
    ui.type_text_safe(name, BROWSER_SEARCH)
    time.sleep(2.5)
    items = [it for it in ui.read_text(region=(1320, 250, 1536, 420)) if it["text"].lower().replace("四", "").strip().endswith(name.lower())]
    hit = items[0] if items else None                          # the OCR adds icon glyphs and changes case: match on the end of the text
    if not hit:
        ui.click(1513, 160)
        raise RuntimeError(f"'{name}' did not show up in the browser (is the plug-in scanned? Settings > Locations)")
    ui.click(hit["cx"], hit["cy"], double=True)
    time.sleep(5)
    ui.click(1513, 160)                                        # leave the search box empty for the next search
    after = [d["name"] for d in deep.tree(track_index)]
    return {"track_index": track_index, "devices_before": before, "devices_after": after, "inserted": len(after) > len(before)}


def _browser_pick(name):
    """Search the device browser for `name` (typing only with a blinking caret) and double-click the result whose text ends with it. Returns True when clicked."""
    ui.click(1513, 160)
    time.sleep(0.6)
    ui.click(1420, 160)
    time.sleep(0.4)
    ui.type_text_safe(name, BROWSER_SEARCH)
    time.sleep(2.5)
    items = [it for it in ui.read_text(region=(1320, 250, 1536, 420)) if it["text"].lower().replace("四", "").strip().endswith(name.lower())]
    ok = bool(items)
    if ok:
        ui.click(items[0]["cx"], items[0]["cy"], double=True)
        time.sleep(5)
    ui.click(1513, 160)
    return ok


@tool()
def insert_on_fx_track(fx_track: str, device: str) -> dict:
    """Insert a device on an FX (send) track, which the API cannot reach: clicks the track's name in the track list, then uses the device browser like insert_plugin
    (typing only after a blinking caret proves the search box is in edit mode) and checks the device panel on screen. fx_track = its current name ('FX 1', 'Reverb');
    device = the browser entry ('Reverb', 'Delay+', 'EQ+'). Bitwig must show the Arrange view with the FX track visible and the device browser open."""
    bw.call("app_panel", layout="ARRANGE")
    time.sleep(0.8)
    ui.focus()
    it = _track_row(ui.read_text(region=TRACK_LIST), fx_track)
    if not it:
        raise ValueError(f"no track called '{fx_track}' in the track list")
    ui.click(it["cx"], it["cy"])                              # one click on the name selects the track (a double click or Alt+click would rename it)
    time.sleep(1.0)
    if not _browser_pick(device):
        raise RuntimeError(f"'{device}' did not show up in the browser")
    seen = [t["text"] for t in ui.read_text(region=DEVICE_PANEL)]
    return {"fx_track": fx_track, "device": device, "panel_text": seen[:12], "inserted": any(device.lower().rstrip("+") in t.lower() for t in seen)}


@tool()
def true_peak_limiter(ceiling_db: float = -1.2, input_gain_db: float | None = None, release_ms: float | None = None, insert: bool = True) -> dict:
    """The master's TRUE-peak limiter (BW True Peak VST3, vst/): a lookahead brick-wall limiter whose detector sees the 4x oversampled signal, so the level between
    samples never passes the ceiling. Bitwig's Peak Limiter only watches sample peaks (measured on a trance drop: sample peak -0.28, true peak +0.48 dBTP; with
    this plug-in after it: sample -1.0, true -0.99 at the same loudness). Finds it on the master or, with insert=True, inserts it at the end of the chain through the
    browser, then sets ceiling (dBTP; -1.2 leaves the 0.2 dB margin the measurement needs for a -1 dBTP delivery target), input gain (0..24 dB) and release (10..1000 ms).
    Put BW Remote AFTER it to measure the final output. Returns the device position and the values read back."""
    idx = next((d["index"] for d in deep.tree(-1) if "true peak" in d["name"].lower()), None)
    if idx is None:
        if not insert:
            raise ValueError("no BW True Peak on the master (insert=True adds it)")
        insert_plugin("BW True Peak", -1)
        idx = next((d["index"] for d in deep.tree(-1) if "true peak" in d["name"].lower()), None)
        if idx is None:
            raise RuntimeError("BW True Peak did not appear on the master")
    deep.goto(-1, idx)
    time.sleep(0.5)
    ids = {p["name"]: p["id"] for p in deep.params(None, 10, 0)["params"]}
    values = {ids["Ceiling (dBTP)"]: (max(-12.0, min(0.0, ceiling_db)) + 12.0) / 12.0}
    if input_gain_db is not None:
        values[ids["Input Gain (dB)"]] = max(0.0, min(24.0, input_gain_db)) / 24.0
    if release_ms is not None:                                  # release is a skewed range 10..1000 ms (skew 0.4): normalized = ((ms-10)/990) ** 0.4
        values[ids["Release (ms)"]] = (max(10.0, min(1000.0, release_ms)) - 10.0) / 990.0
        values[ids["Release (ms)"]] = values[ids["Release (ms)"]] ** 0.4
    deep.set_values(values)
    time.sleep(1.5)                                             # the host reports new values a moment late
    back = {p["name"]: p["value"] for p in deep.params(None, 10, 0)["params"]}
    rel_norm = back.get("Release (ms)", 0.0)
    return {"device_index": idx, "ceiling_dbtp": round(back["Ceiling (dBTP)"] * 12.0 - 12.0, 2), "input_gain_db": round(back["Input Gain (dB)"] * 24.0, 2),
            "release_ms": round(10.0 + 990.0 * (rel_norm ** (1 / 0.4)), 1) if rel_norm > 0 else 10.0, "chain": [d["name"] for d in deep.tree(-1)]}
