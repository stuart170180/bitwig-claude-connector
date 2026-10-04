"""Devices: parameters, nested chains, EQ, mid/side, recipes, A/B tests, device catalogue, preset patching, Bitwig actions, automation by performance."""
import json
import os
import time

from bwmcp.analysis import capture, mastering
from bwmcp.control import actionsdev, performdev
from bwmcp.core import paths
from bwmcp.core.bridge import SETTLE, bw, deep, tool
from bwmcp.devices import compdev, deepdev, presetpatch, presets, recipes


# --- Devices ---
@tool()
def list_devices(track_index: int | None = None) -> dict:
    """List devices on a track (selects it first if track_index given; otherwise the selected track)."""
    if track_index is not None:
        bw.call("select_track", track_index=track_index)
        time.sleep(SETTLE)
    return bw.call("list_devices")


@tool()
def get_device(track_index: int | None = None, device_index: int | None = None) -> dict:
    """Show a device's remote-control pages and the 8 parameters on the current page.
    Optionally selects the track/device first."""
    if track_index is not None:
        bw.call("select_track", track_index=track_index)
        time.sleep(SETTLE)
    if device_index is not None:
        bw.call("select_device", device_index=device_index)
        time.sleep(SETTLE)
    return bw.call("get_device")


@tool()
def set_param(value: float, name: str | None = None, index: int | None = None,
              track_index: int | None = None, device_index: int | None = None) -> dict:
    """Set a device Remote Control by name (case-insensitive substring like 'cutoff', searched across
    all pages) or by index 0-7 on the current page. value is normalized 0..1. Returns the new value."""
    dev = get_device(track_index, device_index)
    if not dev["device"]:
        raise RuntimeError("no device selected on this track")
    if name is not None:
        target, start = name.lower(), dev["page_index"]
        order = [start] + [p for p in range(len(dev["pages"])) if p != start]
        index = None
        for page in order:
            if page != dev["page_index"]:
                bw.call("select_remote_page", page=page)
                time.sleep(SETTLE)
                dev = bw.call("get_device")
            match = next((p for p in dev["params"] if target in p["name"].lower()), None)
            if match:
                index = match["index"]
                break
        if index is None:
            raise RuntimeError(f"no remote control matching {name!r} on {dev['device']}")
    if index is None:
        raise ValueError("give a parameter name or index")
    bw.call("set_remote_param", index=index, value=value)
    time.sleep(SETTLE)
    dev = bw.call("get_device")
    return {"device": dev["device"], "page": dev["page"],
            "param": next(p for p in dev["params"] if p["index"] == index)}


@tool()
def set_device_enabled(enabled: bool, track_index: int | None = None, device_index: int | None = None) -> dict:
    """Enable or bypass a device."""
    get_device(track_index, device_index)
    bw.call("set_device_enabled", enabled=enabled)
    time.sleep(SETTLE)
    d = bw.call("get_device")
    return {"device": d["device"], "enabled": d["enabled"]}


@tool()
def open_device_browser(track_index: int | None = None) -> str:
    """Open Bitwig's browser to insert a device at the end of a track's chain (you pick it in Bitwig)."""
    if track_index is not None:
        bw.call("select_track", track_index=track_index)
        time.sleep(SETTLE)
    return bw.call("insert_device_browser")


@tool()
def device_tree(track_index: int = -1) -> dict:
    """Every device on a track (-1 = master) including what sits inside nested chains such as the Mid and Side
    slots of Mid-Side Split. Slow-ish (it selects each device in turn)."""
    return {"track_index": track_index, "devices": deep.tree(track_index)}


@tool()
def deep_params(track_index: int, device_index: int, slot: str | None = None, slot_index: int = 0,
                filter: str | None = None, limit: int = 60) -> dict:
    """All parameters of one device, not just its 8 remote controls: id, name and normalized 0..1 value.
    track_index -1 = master. device_index = top-level position. slot = enter a nested slot of that device
    ('Mid' / 'Side' on Mid-Side Split) and slot_index = which device inside it. filter = name substring."""
    deep.goto(track_index, device_index, slot, slot_index)
    r = deep.params(filter, limit)
    return {"device": r["device"], "nested": r["nested"], "slots": r["slots"], "layers": r["layers"],
            "param_count": r["param_count"], "params": r["params"]}


@tool()
def deep_set(track_index: int, device_index: int, values: dict, slot: str | None = None,
             slot_index: int = 0) -> dict:
    """Set any parameters on a device, nested or not. values: {parameter id or name: normalized 0..1}, ids/names
    from deep_params. Returns what each parameter is now. For EQ+ use eq_set instead (real units)."""
    deep.goto(track_index, device_index, slot, slot_index)
    return deep.set_values(values)


@tool()
def eq_set(track_index: int, device_index: int, bands: list[dict] | None = None, slot: str | None = None,
           slot_index: int = 0) -> list:
    """Configure Bitwig's EQ+ in real units, anywhere (top level, master, or inside a Mid-Side Split slot).
    bands: [{"band": 1-8, "type": "Bell|Low-shelf|High-shelf|Notch|Low-cut 4P|High-cut 2P|Off|...", "freq_hz": 80,
    "gain_db": -3, "q": 1.0, "enabled": true}]; only given fields change. A fresh EQ+ has every band type Off, so
    set type for each band you use. Low-cut/High-cut have no gain. Returns all 8 bands as they now stand
    (omit bands to just read them)."""
    deep.goto(track_index, device_index, slot, slot_index)
    for b in bands or []:
        b = dict(b)
        band = b.pop("band")
        deep.eq_band(band, **b)
    return deep.eq_state()


@tool()
def device_insert(track_index: int, device: str, slot: str | None = None, device_index: int | None = None,
                  where: str = "end", by_uuid: bool = False) -> dict:
    """Insert a device (name like 'EQ+' or a file path) on a track (-1 = master). Top level: where = end, start or
    before (needs device_index). Inside a nested chain: slot = 'Mid'/'Side' and device_index = the top-level
    Mid-Side Split; the device goes to the end of that slot. by_uuid=True inserts a Bitwig device by name from the
    built-in catalogue (see device_catalog), no preset file needed. Returns the tree afterwards."""
    deep.insert(track_index, device, slot, where, device_index, by_uuid)
    return {"devices": deep.tree(track_index)}


@tool()
def device_delete(track_index: int, device_index: int, slot: str | None = None, slot_index: int = 0) -> dict:
    """Remove a device from any track (-1 = master), including from inside a nested slot (slot + slot_index).
    Undo in Bitwig brings it back. Returns the tree afterwards."""
    deep.delete(track_index, device_index, slot, slot_index)
    return {"devices": deep.tree(track_index)}


@tool()
def mid_side_eq(track_index: int = -1, side_lowcut_hz: float = 120, side_air_db: float = 2.0,
                side_air_hz: float = 8000, mid_bass_cut_db: float = 0, mid_bass_hz: float = 80,
                mid_presence_db: float = 0, mid_presence_hz: float = 3000, mid_gain_db: float = 0,
                side_gain_db: float = 0) -> dict:
    """Mid/side EQ on a track (-1 = master). Builds a Mid-Side Split with an EQ+ in each of its Mid and Side
    slots (re-uses ones already there; on the master it goes before the Peak Limiter) and sets: Side = low-cut at
    side_lowcut_hz (mono-ises the bass; 0 = off) and a high shelf of side_air_db at side_air_hz (widens the top);
    Mid = bell of mid_bass_cut_db at mid_bass_hz and bell of mid_presence_db at mid_presence_hz (0 dB = band off);
    mid_gain_db / side_gain_db trim the two halves (+-24 dB). Returns both EQs."""
    if track_index == -1:
        bw.call("select_master")
    else:
        bw.call("select_track", track_index=track_index)
    time.sleep(deepdev.STEP)
    devs = bw.call("list_devices")["devices"]
    ms = next((d["index"] for d in devs if d["name"] == deepdev.MID_SIDE), None)
    if ms is None:
        lim = next((d["index"] for d in devs if d["name"] == "Peak Limiter"), None)
        deep.insert(track_index, deepdev.MID_SIDE, None, "before" if lim is not None else "end", lim)
        devs = bw.call("list_devices")["devices"]
        ms = next(d["index"] for d in devs if d["name"] == deepdev.MID_SIDE)
    for slot in ("Mid", "Side"):
        try:
            info = deep.goto(track_index, ms, slot=slot)
            has_eq = info["device"] == "EQ+"
        except ValueError:
            has_eq = False
        if not has_eq:
            deep.insert(track_index, "EQ+", slot, "end", ms)
    # side EQ
    deep.goto(track_index, ms, slot="Side")
    side = [{"band": b, "type": "Off"} for b in range(1, 9)]
    if side_lowcut_hz:
        side[0] = {"band": 1, "type": "Low-cut 4P", "freq_hz": side_lowcut_hz, "enabled": True}
    if side_air_db:
        side[6] = {"band": 7, "type": "High-shelf", "freq_hz": side_air_hz, "gain_db": side_air_db, "q": 0.7,
                   "enabled": True}
    for b in side:
        b = dict(b)
        deep.eq_band(b.pop("band"), **b)
    side_state = deep.eq_state()
    deep.goto(track_index, ms, slot="Mid")
    mid = [{"band": b, "type": "Off"} for b in range(1, 9)]
    if mid_bass_cut_db:
        mid[2] = {"band": 3, "type": "Bell", "freq_hz": mid_bass_hz, "gain_db": mid_bass_cut_db, "q": 1.0,
                  "enabled": True}
    if mid_presence_db:
        mid[4] = {"band": 5, "type": "Bell", "freq_hz": mid_presence_hz, "gain_db": mid_presence_db, "q": 0.8,
                  "enabled": True}
    for b in mid:
        b = dict(b)
        deep.eq_band(b.pop("band"), **b)
    mid_state = deep.eq_state()
    deep.goto(track_index, ms)
    deep.set_values({"CONTENTS/MID_GAIN": 0.5 + mid_gain_db / 48, "CONTENTS/SIDE_GAIN": 0.5 + side_gain_db / 48})
    return {"mid_side_split_index": ms,
            "side_eq": [b for b in side_state if b["type"] != "Off"],
            "mid_eq": [b for b in mid_state if b["type"] != "Off"],
            "mid_gain_db": mid_gain_db, "side_gain_db": side_gain_db}


AB_KEYS = [("loudness", "integrated_lufs"), ("loudness", "short_term_max_lufs"), ("peaks", "true_peak_dbtp"),
           ("dynamics", "crest_factor_db"), ("dynamics", "plr_db"), ("stereo", "width_pct"),
           ("stereo", "correlation"), ("stereo", "side_vs_mid_db")]


@tool()
def recipe(action: str, name: str | None = None, track_index: int | None = None, note: str = "",
           replace: bool = False) -> dict:
    """Save and recall whole device chains. action: save (capture track_index's Bitwig devices and every parameter
    under `name`; -1 = master; third-party plugins are skipped), apply (build recipe `name` on track_index,
    appended after existing devices, or replace=True to clear the track's devices first), list, delete.
    Recipes live in the repo's recipes/ folder as JSON."""
    if action == "list":
        return {"recipes": recipes.list_all()}
    if not name:
        raise ValueError("name is required")
    if action == "delete":
        recipes.delete(name)
        return {"deleted": name}
    if track_index is None:
        raise ValueError("track_index is required")
    if action == "save":
        return recipes.save(deep, track_index, name, note)
    if action == "apply":
        return recipes.apply(deep, name, track_index, replace)
    raise ValueError("action must be save, apply, list or delete")


@tool()
def ab_test(track_index: int, device_index: int, values: dict, seconds: float = 6, slot: str | None = None,
            slot_index: int = 0, keep: bool = False, target: str = "streaming") -> dict:
    """A/B a change by measurement: captures the playing master (play first), applies `values` ({parameter id or
    name: normalized 0..1}, see deep_params) to a device, captures again, and returns both sets of numbers (LUFS,
    true peak, crest, width, correlation, side/mid) with the difference. keep=False restores the original values
    afterwards; keep=True leaves the change in place. Needs live capture (WASAPI) and Bitwig playing."""
    if not bw.call("get_session")["playing"]:
        raise ValueError("Bitwig isn't playing - start playback (or launch a scene) first")
    deep.goto(track_index, device_index, slot, slot_index)
    info = deep.params(None, 500)
    before_vals = {}
    for key in values:
        hit = [p for p in info["params"] if p["id"] == key or p["name"].lower() == str(key).lower()]
        if len(hit) != 1:
            raise ValueError(f"{key!r} doesn't match exactly one parameter on {info['device']}")
        before_vals[hit[0]["id"]] = hit[0]["value"]

    def measure():
        x, sr, _ = capture.capture_live(seconds)
        m = mastering.analyze(x, sr, target)
        return {f"{a}.{b}": m[a][b] for a, b in AB_KEYS}

    a = measure()
    deep.goto(track_index, device_index, slot, slot_index)
    changed = deep.set_values(values)
    time.sleep(0.5)
    b = measure()
    if not keep:
        deep.goto(track_index, device_index, slot, slot_index)
        deep.set_values(before_vals)
    return {"device": info["device"], "kept": keep, "changed": changed, "A_before": a, "B_after": b,
            "difference": {k: round(b[k] - a[k], 2) for k in a}}


@tool()
def device_catalog(query: str = "", limit: int = 40) -> dict:
    """Search Bitwig's built-in devices (152 known, such as 'Polysynth', 'Poly Grid', 'FX Layer', 'Multiband FX-2') by
    name. device_insert(..., by_uuid=True) inserts any of them directly, including ones that have no preset file."""
    ids = json.load(open(paths.DATA / "bitwig_device_ids.json", encoding="utf-8"))
    q = query.lower()
    rows = sorted((n, u) for u, n in ids.items() if n != "?" and q in n.lower())
    return {"count": len(rows), "devices": [{"name": n, "uuid": u} for n, u in rows[:limit]]}


@tool()
def preset_inspect(preset: str) -> dict:
    """Look inside a Bitwig preset file (a path, or a name from search_presets): device name, how many modules and
    modulators it references, and every plain numeric value stored in it (name, occurrence, value). Works on
    version-0002 presets (device-settings defaults and presets you saved); the factory device, module and modulator
    files are scrambled and are refused."""
    return presetpatch.inspect(preset if os.path.isfile(preset) else presets.resolve(preset, "preset"))


@tool()
def preset_patch_and_load(preset: str, values: dict, track_index: int | None = None) -> dict:
    """Change numeric values inside a copy of a preset, then load the copy onto a track (omit track_index to only write
    the copy; -1 = master). values: {name: number} or {name: {"value": n, "occurrence": k}} using names from
    preset_inspect, in the preset's own units (PITCH_TRANSPOSE 7 = seven semitones). Same-length edits only: this
    cannot add modules, cables or modulators. The original preset is never touched; the copy goes in patched_presets/."""
    src = preset if os.path.isfile(preset) else presets.resolve(preset, "preset")
    dst, report = presetpatch.patch(src, values)
    out = {"patched_copy": dst, "changes": report}
    if track_index is not None:
        if track_index == -1:
            bw.call("select_master")
        else:
            bw.call("select_track", track_index=track_index)
        time.sleep(0.7)
        bw.call("insert_file", path=dst)
        time.sleep(1.2)
        out["devices"] = bw.call("list_devices")["devices"]
    return out


@tool()
def list_bitwig_actions(filter: str | None = None, limit: int = 50) -> dict:
    """Search Bitwig's ~780 built-in actions (category, id, name, 'blocked' if the safety deny-list refuses it)."""
    return actionsdev.action_list(bw, filter, limit)


@tool()
def run_bitwig_action(action_id: str) -> dict:
    """Run a Bitwig action by id on the current selection or focus. Dangerous ones (quit, close or switch project,
    delete everything, generic Delete) are refused. Results are not always visible to the script: check get_session."""
    return actionsdev.action_run(bw, action_id)


def _perform_move(m: dict) -> tuple[dict, dict | None]:
    p, kind = m["param"], m["param"]
    a, b = m["from"], m["to"]
    sb, bars, cv = m.get("start_bar", 0), m.get("bars", 1), m.get("curve", "linear")
    t = m.get("track_index")
    if kind == "volume":
        return performdev.volume_ramp(t, a, b, sb, bars, cv), None
    if kind == "pan":
        return performdev.pan_ramp(t, a, b, sb, bars, cv), None
    if kind == "send":
        return performdev.send_ramp(t, m.get("send", 0), a, b, sb, bars, cv), None
    if kind == "remote":
        if m.get("device_index") is None:
            raise ValueError("a remote move needs device_index")
        return performdev.remote_ramp(m.get("remote_index", 0), a, b, sb, bars, cv), {"track": t, "device": m["device_index"]}
    raise ValueError(f"param must be volume, pan, send or remote, not {p!r}")


@tool()
def perform_plan(moves: list[dict], total_bars: float | None = None, record: bool = True,
                 scenes: list[dict] | None = None) -> dict:
    """Write real automation by performing it: the script moves parameters in time while Bitwig records the arranger
    with automation write on, then the lanes replay on their own. Runs in REAL TIME and is audible. moves: [{"param":
    "volume"|"pan"|"send"|"remote", "track_index": n, "from": 0-1, "to": 0-1, "start_bar": 0, "bars": 2,
    "curve": linear|exp|log|ease|ease_in|ease_out|hold, "send": 0, "device_index": d, "remote_index": 0-7}]; values are
    Bitwig's normalized 0..1. Device automation goes through the 8 remote controls (page 0): direct parameters move
    but are not recordable. All remote moves in one plan must target the same device. Recording overwrites existing
    lane content. scenes: optional [{"scene": n, "start": beat}] launches during the take."""
    built = [_perform_move(m) for m in moves]
    selects = {(s["track"], s["device"]) for _, s in built if s}
    if len(selects) > 1:
        raise ValueError("remote moves in one plan must target the same track and device")
    select = {"track": next(iter(selects))[0], "device": next(iter(selects))[1]} if selects else None
    plan = [b for b, _ in built]
    end_beat = max(x["start_beat"] + x["length_beats"] for x in plan)
    total = (total_bars * 4) if total_bars else end_beat + 1
    perf = performdev.Perform(bw)
    if record:
        perf.record(plan, total, scenes=scenes, select=select)
    else:
        perf.run(plan, select=select)
    tempo = bw.call("get_session")["tempo"]
    st = perf.wait(timeout=total / tempo * 60 + 30)
    return {"recorded": record, "moves": len(plan), "beats": total, "status": st}


@tool()
def perform_ramp(track_index: int, param: str, from_value: float, to_value: float, start_bar: float = 0, bars: float = 2,
                 curve: str = "linear", send: int = 0, device_index: int | None = None, remote_index: int = 0,
                 record: bool = True) -> dict:
    """One automated move (see perform_plan): param = volume, pan, send (send index) or remote (device_index +
    remote_index 0-7). Example: a 4-bar filter rise on a synth = param 'remote', device_index 0, remote_index 0 (the first
    knob on the device's current page), from 0.2 to 0.9. Real time and audible; overwrites existing lane content."""
    return perform_plan([{"param": param, "track_index": track_index, "from": from_value, "to": to_value,
                          "start_bar": start_bar, "bars": bars, "curve": curve, "send": send,
                          "device_index": device_index, "remote_index": remote_index}], record=record)


@tool()
def perform_status() -> dict:
    """State of a running perform_plan / perform_ramp."""
    return performdev.Perform(bw).status()


@tool()
def perform_abort() -> dict:
    """Stop a running automation performance (turns record and write off)."""
    return performdev.Perform(bw).abort()


@tool()
def compressor_read(track_index: int, device_index: int | None = None) -> dict:
    """Read a Compressor+ in real units (attack ms, release ms, ratio, threshold dB, knee, make-up, ...). device_index
    defaults to the first Compressor+ on the track. Bitwig's API does not expose gain reduction, so there is no
    live GR meter; this shows the settings."""
    if device_index is None:
        device_index = next((d["index"] for d in deep.tree(track_index) if d["name"] == "Compressor+"), None)
        if device_index is None:
            raise ValueError("no Compressor+ on that track")
    return {"track_index": track_index, "device_index": device_index, "values": compdev.read(bw, deep, track_index, device_index)}


@tool()
def compressor_set(track_index: int, device_index: int, attack_ms: float | None = None, release_ms: float | None = None,
                   ratio: float | None = None, threshold_db: float | None = None, makeup_db: float | None = None,
                   input_db: float | None = None, knee_pct: float | None = None, mix_pct: float | None = None) -> dict:
    """Set a Compressor+ in real units (ratio as the N in N:1). Finds each value by reading Bitwig's own display text, so
    the result is what Bitwig shows; returns wanted vs got for each."""
    vals = {k: v for k, v in dict(attack_ms=attack_ms, release_ms=release_ms, ratio=ratio, threshold_db=threshold_db, makeup_db=makeup_db,
                                  input_db=input_db, knee_pct=knee_pct, mix_pct=mix_pct).items() if v is not None}
    return compdev.set_units(bw, deep, track_index, device_index, **vals)
