"""Device preset library tools: named starting points (reverb, compressor, saturator, de-esser, gate, limiter, tool) applied in real units."""
import time

from bwmcp.core.bridge import bw, deep, tool
from bwmcp.devices import presetlib
from bwmcp.devices import units as devunits

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
