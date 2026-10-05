"""Device preset library tools: named starting points (reverb, compressor, saturator, de-esser, gate, limiter, tool) applied in real units."""
import time

from bwmcp.core.bridge import bw, deep, tool
from bwmcp.devices import presetlib
from bwmcp.devices import units as devunits
from bwmcp.tools import uitools

COMP_KEYS = {"ratio": "RATIO", "attack_ms": "ATTACK", "release_ms": "RELEASE", "threshold_db": "THRESHOLD", "makeup_db": "MAKEUP",
             "knee_pct": "SMOOTH", "mix_pct": "MIX", "input_db": "INPUT"}


@tool()
def device_presets(device: str | None = None) -> dict:
    """The device preset library: for each device (Reverb, Delay+, Compressor+, Saturator, De-Esser, Gate, Peak Limiter, Pitch Shifter, Tool) the preset names with a
    one-line description and their values (time values written as notes or beats follow the project tempo). Your own saved presets are included."""
    lib = presetlib.all_presets()
    if device:
        if device not in lib:
            raise ValueError(f"unknown device '{device}'; known: {sorted(lib)}")
        lib = {device: lib[device]}
    return {d: {n: {"about": p.get("about", ""), "values": p["values"]} for n, p in ps.items()} for d, ps in lib.items()}


@tool()
def apply_device_preset(track_index: int, device: str, preset: str, as_send: bool = False, device_index: int | None = None) -> dict:
    """Put a library preset on a track: inserts the device if the track has none (or use device_index to target one) and sets every value in real
    units, reading what Bitwig shows back. Tempo-based values (reverb sizes, pre-delay) are computed from the project tempo.
    as_send=True sets the reverb MIX to 100 % wet (for a device used on a send); otherwise the preset's insert mix is used. track_index -1 = master."""
    bpm = float(bw.call("get_session")["tempo"])
    values = presetlib.resolve(device, preset, bpm, as_send)
    if device == "Compressor+":
        values = {COMP_KEYS.get(k, k.upper()): v for k, v in values.items()}
    if device_index is None:
        device_index = next((d["index"] for d in deep.tree(track_index) if d["name"] == device), None)
        if device_index is None:
            deep.insert(track_index, device, None, "end", None, True)
            time.sleep(1.0)
            device_index = next(d["index"] for d in deep.tree(track_index) if d["name"] == device)
    res = devunits.set_values(bw, deep, track_index, device_index, values)
    return {"device": device, "preset": preset, "tempo": bpm, "device_index": device_index, "set": res["set"],
            "now": devunits.read(bw, deep, track_index, device_index)["values"]}


@tool()
def save_device_preset(track_index: int, device_index: int, name: str, about: str = "") -> dict:
    """Save a device's current numeric settings (as Bitwig displays them) as your own preset in the library, under the device's name."""
    cur = devunits.read(bw, deep, track_index, device_index)
    values = {k: devunits.number(v) for k, v in cur["values"].items() if devunits.number(v) is not None}
    presetlib.save_user_preset(cur["device"], name, values, about)
    return {"saved": f"{cur['device']} / {name}", "values": values}


def _apply_values(track_index, device_index, device, preset, bpm, nest=None, as_send=False):
    values = presetlib.resolve(device, preset, bpm, as_send)
    if device == "Compressor+":
        values = {COMP_KEYS.get(k, k.upper()): v for k, v in values.items()}
    return values


@tool()
def layer_chain(track_index: int, layers: list[list[str]], layer_device: str = "FX Layer", device_index: int | None = None) -> dict:
    """Build parallel chains: an FX Layer (or Instrument Layer) whose layers each hold their own devices. layers = one list per layer,
    e.g. [[], ["Compressor+:parallel_smash", "Saturator:warm"]] = a dry layer plus a compressed and saturated one. An entry is a device name,
    or 'Device:preset' to also apply a library preset (see device_presets). The layer device is added if the track has none; missing layers are
    added by clicking Bitwig's screen (the API cannot make layers), so Bitwig must be visible. Returns the resulting tree."""
    bpm = float(bw.call("get_session")["tempo"])
    if device_index is None:
        device_index = next((d["index"] for d in deep.tree(track_index) if d["name"] == layer_device), None)
        if device_index is None:
            deep.insert(track_index, layer_device, None, "end", None, True)
            time.sleep(1.2)
            device_index = next(d["index"] for d in deep.tree(track_index) if d["name"] == layer_device)
    have = len(deep.params(None, 1, 0)["layers"]) if deep.goto(track_index, device_index) else 0
    while have < len(layers):
        have = uitools.add_layer(track_index, device_index)["layers_after"]
    applied = []
    for li, entries in enumerate(layers):
        for k, entry in enumerate(entries):
            name, _, preset = entry.partition(":")
            deep.insert(track_index, name, None, "end", device_index, True, li)
            time.sleep(1.0)
            if preset:
                values = _apply_values(track_index, device_index, name, preset, bpm)
                res = devunits.set_values(bw, deep, track_index, device_index, values, nest={"layer": li, "slot_index": k})
                applied.append({"layer": li, "device": name, "preset": preset, "set": {p: v.get("shown") for p, v in res["set"].items()}})
    return {"track_index": track_index, "device_index": device_index, "tree": deep.tree(track_index), "presets_applied": applied}


@tool()
def parallel_compression(track_index: int, preset: str = "parallel_smash", level_db: float = -6.0) -> dict:
    """Parallel compression on a track: an FX Layer with a dry layer (left empty, so the original signal passes) and a layer with a hard-squashed
    Compressor+ (library preset, default parallel_smash) at 100 % wet, whose level is set with its make-up gain (level_db, relative blend). Needs
    Bitwig visible (a layer is added by clicking)."""
    r = layer_chain(track_index, [[], [f"Compressor+:{preset}"]])
    comp_layer = 1
    values = {"MIX": 100.0, "MAKEUP": level_db}
    res = devunits.set_values(bw, deep, track_index, r["device_index"], values, nest={"layer": comp_layer, "slot_index": 0})
    r["parallel_level"] = {k: v.get("shown") for k, v in res["set"].items()}
    return r


@tool()
def spire_presets(query: str = "", bank: str | None = None, limit: int = 30) -> list:
    """Search the Spire preset banks (%APPDATA%\\RevealSound\\Banks, .spf2 files: thousands, many trance soundsets). All words of the query must appear in the bank / folder /
    preset name, e.g. 'trance supersaw', 'acid', 'pluck', 'lead', 'sub bass', bank='Trance Euphoria'. Returns name, bank, folder and path for spire_load."""
    from bwmcp.devices import spire
    return [{k: r[k] for k in ("name", "bank", "sub", "path")} for r in spire.search(query, bank, limit)]


@tool()
def spire_load(track_index: int, preset: str, device_index: int | None = None, bank: str | None = None) -> dict:
    """Load a Spire preset (.spf2) into the Spire-1.5 plug-in on a track WITHOUT opening Spire's window: the file is JSON whose parameter names and 0..1 values match
    the ones Bitwig exposes, so every one of the ~500 values is written through deep_set. preset = a file path or part of a name (first match; narrow with bank).
    device_index defaults to the first Spire on the track. Returns what was set and a read-back check. Insert the plug-in first (insert_plugin 'Spire-1.5')."""
    from bwmcp.devices import spire
    path = preset if preset.lower().endswith(".spf2") else None
    if path is None:
        hits = spire.search(preset, bank, 5)
        if not hits:
            raise ValueError(f"no Spire preset matching '{preset}'")
        path = hits[0]["path"]
    if device_index is None:
        bw.call("select_track", track_index=track_index)
        time.sleep(1.0)
        devs = deep.tree(track_index)
        device_index = next((d["index"] for d in devs if "spire" in d["name"].lower()), None)
        if device_index is None:
            raise ValueError("no Spire on that track")
    return spire.apply(bw, deep, track_index, device_index, path)
