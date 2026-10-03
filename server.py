"""MCP server that drives Bitwig Studio via the BitwigMCP controller script (OSC over UDP)."""
import functools
import itertools
import os
import json
import re
import socket
import sys
import threading
import time

import numpy as np
from mcp.server.mcpserver import Image, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

import bookmarks
import expert
import mastering
import music
import naming
import presets
import samples

HOST, PORT = "127.0.0.1", 8765
REPLY_PORTS = range(8766, 8772)  # must match REPLY_PORTS in BitwigMCP.control.js
mcp = MCPServer("bitwig")


def tool():
    """Register an MCP tool whose errors reach Claude with their message. The SDK hides the text of any
    exception that isn't a ToolError, which would turn useful errors into 'Error executing tool X'."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except ToolError:
                raise
            except Exception as e:
                raise ToolError(str(e) if isinstance(e, (RuntimeError, ValueError)) else f"{type(e).__name__}: {e}") from e
        mcp.tool()(wrapper)
        return wrapper
    return deco


def _osc_str(s: bytes) -> bytes:
    s += b"\0"
    return s + b"\0" * (-len(s) % 4)


def osc_encode(address: str, arg: str) -> bytes:
    return _osc_str(address.encode()) + _osc_str(b",s") + _osc_str(arg.encode("utf-8"))


def osc_decode_string_arg(packet: bytes) -> str:
    """Return the first string argument of an OSC message."""
    def read_str(i):
        end = packet.index(b"\0", i)
        return packet[i:end], end + 1 + (-(end + 1) % 4)
    _, i = read_str(0)        # address
    tags, i = read_str(i)     # type tags
    if not tags.startswith(b",s"):
        raise ValueError(f"unexpected OSC type tags {tags!r}")
    val, _ = read_str(i)
    return val.decode("utf-8")


class Bridge:
    def __init__(self):
        self.sock = None
        self.port = None
        self.lock = threading.Lock()
        self.ids = itertools.count(1)

    def _open(self):
        # Each client (Claude session, script) takes the first free reply port so several can run at once.
        for port in REPLY_PORTS:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.bind((HOST, port))
            except OSError:
                sock.close()
                continue
            sock.settimeout(5)
            self.sock, self.port = sock, port
            return
        raise RuntimeError(f"all Bitwig reply ports {REPLY_PORTS.start}-{REPLY_PORTS.stop - 1} are in use; "
                           "close other Claude sessions using Bitwig")

    def call(self, cmd, **args):
        with self.lock:
            if self.sock is None:
                self._open()
            rid = next(self.ids)
            payload = json.dumps({"id": rid, "cmd": cmd, "args": args, "reply_port": self.port})
            if len(payload) > 60000:
                raise RuntimeError("request too large; split it into smaller calls")
            self.sock.sendto(osc_encode("/mcp", payload), (HOST, PORT))
            try:
                while True:
                    reply = json.loads(osc_decode_string_arg(self.sock.recv(65535)))
                    if reply.get("id") == rid:
                        break  # ignore stale replies from timed-out calls
            except (OSError, ValueError) as e:
                raise RuntimeError(
                    "No reply from Bitwig. Is Bitwig open with the 'Claude > Bitwig MCP' "
                    f"controller enabled (Settings > Controllers)? ({e})"
                )
        if not reply.get("ok"):
            raise RuntimeError(reply.get("error"))
        return reply.get("result")

    def batch(self, commands):
        """Run [(cmd, args), ...] in one round trip; raises if any failed."""
        results = self.call("batch", commands=[{"cmd": c, "args": a} for c, a in commands])
        errors = [r["error"] for r in results if not r["ok"]]
        if errors:
            raise RuntimeError("; ".join(errors))
        return [r["result"] for r in results]


bw = Bridge()
SETTLE = 0.25  # seconds for Bitwig to apply a change before reading it back


def _hex_to_rgb(color: str):
    c = color.lstrip("#")
    if len(c) != 6:
        raise ValueError("color must be a hex string like #ff8800")
    return [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def _parse_db(display: str) -> float:
    if "inf" in display.lower():
        return -200.0
    m = re.search(r"-?\d+(\.\d+)?", display)
    return float(m.group()) if m else 0.0


def _set_volume_db(track_index: int, db: float):
    """Bitwig's fader curve isn't exposed, so binary-search the normalized value against the dB readout."""
    lo, hi = 0.0, 1.0
    for _ in range(14):
        mid = (lo + hi) / 2
        bw.call("set_track_volume", track_index=track_index, value=mid)
        time.sleep(0.06)
        cur = _parse_db(bw.call("get_track", track_index=track_index)["volume_display"])
        if abs(cur - db) < 0.1:
            return
        lo, hi = (mid, hi) if cur < db else (lo, mid)


WRITE_CHUNK = 300  # notes per message, keeps requests well under the UDP limit


def _write(track_index, slot, notes, length_beats, name=None):
    core = [{k: n[k] for k in ("pitch", "start", "duration", "velocity") if k in n} for n in notes]
    for i in range(0, max(1, len(core)), WRITE_CHUNK):
        bw.call("write_clip", track_index=track_index, slot=slot, notes=core[i:i + WRITE_CHUNK],
                length_beats=length_beats, name=name, replace=(i == 0))
        time.sleep(0.9)  # each write is scheduled inside Bitwig
    # setStep only carries velocity/duration; re-apply any per-note expressions on top.
    expressive = [{k: v for k, v in n.items() if k in expert.EXPR_KEYS or k in ("start", "pitch")}
                  for n in notes if expert.has_expression(n)]
    for i in range(0, len(expressive), 200):
        bw.call("set_note_props", notes=expressive[i:i + 200])
    clips = bw.call("get_track", track_index=track_index)["clips"]
    ok = any(c["slot"] == slot for c in clips)
    return {"track_index": track_index, "slot": slot, "notes": len(notes),
            "length_beats": length_beats, "verified": ok}


def _chords_arg(chords, progression):
    if chords:
        return chords
    if progression:
        if progression not in music.PROGRESSIONS:
            raise ValueError(f"unknown progression; options: {', '.join(music.PROGRESSIONS)}")
        return music.PROGRESSIONS[progression]
    raise ValueError("give chords (e.g. ['i','VI','III','VII'] or ['Am','F','C','G']) or a progression name")


# --- Session / transport ---
@tool()
def get_session(with_clips: bool = False) -> dict:
    """Overview: tempo, transport, selected track, tracks (index, name, colour, mute/solo/arm,
    volume, pan, sends) and scenes. with_clips=True also lists filled clip-launcher slots."""
    return bw.call("get_session", with_clips=with_clips)


@tool()
def get_track(track_index: int) -> dict:
    """Detailed info for one track including sends and launcher clips."""
    return bw.call("get_track", track_index=track_index)


@tool()
def health_check() -> dict:
    """Check the Bitwig connection, script version and any API features missing in this Bitwig version."""
    return bw.call("capabilities")


@tool()
def transport(action: str) -> str:
    """Control playback. action: play, stop, record, undo, redo."""
    if action not in ("play", "stop", "record", "undo", "redo"):
        raise ValueError("action must be play, stop, record, undo or redo")
    return bw.call(action)


@tool()
def set_tempo(bpm: float) -> dict:
    """Set project tempo in BPM (verified by reading back)."""
    bw.call("set_tempo", bpm=bpm)
    time.sleep(SETTLE)
    return {"tempo": bw.call("get_session")["tempo"]}


@tool()
def set_position(beats: float) -> str:
    """Move the play head to a position in beats (4 beats = 1 bar in 4/4)."""
    return bw.call("set_position", beats=beats)


@tool()
def set_metronome(enabled: bool) -> str:
    """Turn the metronome on or off."""
    return bw.call("set_metronome", enabled=enabled)


# --- Tracks & mixing ---
@tool()
def create_track(kind: str = "instrument", position: int = -1, name: str | None = None,
                 color: str | None = None, instrument: str | None = None) -> dict:
    """Create a track (kind: instrument, audio or effect; position -1 = end), optionally naming and
    colouring it. instrument: a preset/device name to load (e.g. 'Polysynth', 'Legend 808 Normal Kit',
    'Rhodes'; see search_presets). Returns the new track's info. Effect (FX) tracks appear as sends."""
    if kind not in ("instrument", "audio", "effect"):
        raise ValueError("kind must be instrument, audio or effect")
    before = bw.call("get_session")["tracks"]
    bw.call(f"create_{kind}_track", position=position)
    time.sleep(0.4)
    after = bw.call("get_session")["tracks"]
    if kind == "effect":
        return {"created": "effect track", "sends_now": bw.call("get_track", track_index=0)["sends"] if after else []}
    if len(after) <= len(before):
        raise RuntimeError("Bitwig did not create the track")
    idx = len(before) if position < 0 else position
    if instrument:
        load_preset(instrument, track_index=idx)
    if name or color:
        return set_track(idx, name=name, color=color)
    return bw.call("get_track", track_index=idx)


@tool()
def delete_track(track_index: int) -> str:
    """Delete a track."""
    return bw.call("delete_track", track_index=track_index)


@tool()
def set_track(track_index: int, name: str | None = None, volume: float | None = None,
              volume_db: float | None = None, pan: float | None = None, mute: bool | None = None,
              solo: bool | None = None, arm: bool | None = None, color: str | None = None) -> dict:
    """Change track properties; only given fields change. Returns the track state read back from Bitwig.
    volume_db sets the fader to an exact dB (e.g. -6); volume is the raw normalized 0..1 alternative.
    pan: -1 (left) .. 1 (right). color: hex like '#ff8800'."""
    cmds = []
    if name is not None:
        cmds.append(("set_track_name", {"name": name}))
    if volume is not None:
        cmds.append(("set_track_volume", {"value": volume}))
    if pan is not None:
        cmds.append(("set_track_pan", {"value": (pan + 1) / 2}))
    for key, val in (("mute", mute), ("solo", solo), ("arm", arm)):
        if val is not None:
            cmds.append((f"set_track_{key}", {"value": val}))
    if color is not None:
        r, g, b = _hex_to_rgb(color)
        cmds.append(("set_track_color", {"r": r, "g": g, "b": b}))
    if cmds:
        bw.batch([(c, {"track_index": track_index, **a}) for c, a in cmds])
    if volume_db is not None:
        _set_volume_db(track_index, volume_db)
    time.sleep(SETTLE)
    return bw.call("get_track", track_index=track_index)


@tool()
def set_send(track_index: int, send_index: int, value: float) -> dict:
    """Set a track's send level to an FX track, normalized 0..1."""
    bw.call("set_send", track_index=track_index, send_index=send_index, value=value)
    time.sleep(SETTLE)
    return {"sends": bw.call("get_track", track_index=track_index)["sends"]}


@tool()
def mix(tracks: list[dict]) -> list[dict]:
    """Set many tracks at once. Each item: {"track_index": int, plus any of name, volume, volume_db,
    pan, mute, solo, arm, color}. Returns each track's resulting state."""
    return [set_track(**t) for t in tracks]


@tool()
def select_track(track_index: int) -> str:
    """Select a track (device tools act on the selected track)."""
    return bw.call("select_track", track_index=track_index)


# --- Clip launcher ---
@tool()
def launch(track_index: int | None = None, slot: int | None = None, scene: int | None = None) -> str:
    """Launch a clip (track_index + slot) or a whole scene (scene)."""
    if scene is not None:
        return bw.call("launch_scene", scene=scene)
    return bw.call("launch_clip", track_index=track_index, slot=slot)


@tool()
def stop_clips(track_index: int | None = None) -> str:
    """Stop clips on one track, or all clips if track_index is omitted."""
    if track_index is None:
        return bw.call("stop_all_clips")
    return bw.call("stop_track_clips", track_index=track_index)


@tool()
def set_scene_name(scene: int, name: str) -> str:
    """Rename a scene."""
    return bw.call("set_scene_name", scene=scene, name=name)


@tool()
def delete_clip(track_index: int, slot: int) -> str:
    """Delete the clip in a launcher slot."""
    return bw.call("delete_clip", track_index=track_index, slot=slot)


@tool()
def write_notes(track_index: int, slot: int, notes: list[dict], length_beats: float = 4,
                name: str | None = None) -> dict:
    """Write MIDI notes into a launcher slot (clip created if empty; existing notes replaced).
    notes: [{"pitch": 60, "start": 0.0, "duration": 0.5, "velocity": 100}], times in beats,
    resolution 1/32 note."""
    return _write(track_index, slot, notes, length_beats, name)


@tool()
def write_drums(track_index: int, slot: int, style: str = "house", bars: int = 2, fill: bool = True,
                swing: float = 0.0, humanize: float = 0.3, seed: int | None = None) -> dict:
    """Generate a drum loop (GM mapping, matches Bitwig's Drum Machine: kick=36/C1, snare=38,
    clap=39, closed hat=42, open hat=46). styles: house, techno, hiphop, trap, dnb, breakbeat, rock,
    funk, reggaeton, garage. fill adds a roll in the last bar; swing 0..1; humanize 0..1."""
    notes = music.drum_pattern(style, bars, fill, swing, humanize, seed)
    return _write(track_index, slot, notes, bars * 4, f"{style} drums")


@tool()
def write_bass(track_index: int, slot: int, chords: list[str] | None = None, progression: str | None = None,
               key: str = "A", scale: str = "minor", style: str = "root", bars_per_chord: float = 1,
               octave: int = 1, seed: int | None = None) -> dict:
    """Generate a bassline following chords. chords: roman numerals relative to key/scale
    (['i','VI','III','VII'], 'ii7', 'bVII') or names (['Am','F','C','G']); or a preset progression
    (pop, sad, jazz, minor_epic, house, andalusian, dark). styles: root, eighths, offbeat, octave,
    walking, syncopated."""
    ch = _chords_arg(chords, progression)
    notes = music.bassline(ch, key, scale, style, bars_per_chord, octave, seed)
    return _write(track_index, slot, notes, len(ch) * 4 * bars_per_chord, f"bass {style}")


@tool()
def write_chords(track_index: int, slot: int, chords: list[str] | None = None, progression: str | None = None,
                 key: str = "C", scale: str = "major", rhythm: str = "sustained", bars_per_chord: float = 1,
                 octave: int = 4) -> dict:
    """Generate a voice-led chord progression. Chords as in write_bass. rhythms: sustained, stabs,
    pulse, arp_up, arp_updown, strum. scales: major, minor, dorian, phrygian, lydian, mixolydian,
    harmonic_minor, pentatonic_major, pentatonic_minor, blues."""
    ch = _chords_arg(chords, progression)
    notes = music.chord_progression(ch, key, scale, rhythm, bars_per_chord, octave)
    return _write(track_index, slot, notes, len(ch) * 4 * bars_per_chord, f"chords {rhythm}")


@tool()
def write_melody(track_index: int, slot: int, chords: list[str] | None = None, progression: str | None = None,
                 key: str = "C", scale: str = "major", bars_per_chord: float = 1, octave: int = 5,
                 density: float = 0.5, seed: int | None = None) -> dict:
    """Generate a chord-aware melody (chord tones on beats, stepwise motion between).
    density 0..1 controls how busy it is; change seed for a different take."""
    ch = _chords_arg(chords, progression)
    notes = music.melody(ch, key, scale, bars_per_chord, octave, density, seed)
    return _write(track_index, slot, notes, len(ch) * 4 * bars_per_chord, "melody")


@tool()
def sketch_song(key: str = "A", scale: str = "minor", tempo: float | None = None,
                drum_style: str = "house", progression: str | list[str] = "minor_epic",
                sections: list[dict] | None = None, seed: int | None = None,
                load_instruments: bool = True) -> dict:
    """Build a whole song sketch in the clip launcher: one scene per section, one track per part.
    Creates (or reuses by name) instrument tracks Drums, Bass, Chords, Lead, loads a genre-appropriate
    factory sound on each new track (drum kit, bass, pad/keys, lead), names scenes and writes every clip.
    sections: [{"name": "Intro", "parts": ["drums", "chords"], "variation": "build"|"alt"}];
    default is Intro / Verse / Build / Drop / Breakdown / Drop 2 / Outro. Launch scenes in order to play."""
    chords = progression if isinstance(progression, list) else _chords_arg(None, progression)
    sections = sections or [
        {"name": "Intro", "parts": ["drums", "chords"]},
        {"name": "Verse", "parts": ["drums", "bass", "chords"]},
        {"name": "Build", "parts": ["drums", "bass", "chords", "lead"], "variation": "build"},
        {"name": "Drop", "parts": ["drums", "bass", "chords", "lead"]},
        {"name": "Breakdown", "parts": ["chords", "lead"]},
        {"name": "Drop 2", "parts": ["drums", "bass", "chords", "lead"], "variation": "alt"},
        {"name": "Outro", "parts": ["drums", "chords"]},
    ]
    if tempo:
        bw.call("set_tempo", bpm=tempo)

    parts = {"drums": ("Drums", "#e4572e"), "bass": ("Bass", "#4c6ef5"),
             "chords": ("Chords", "#2fb380"), "lead": ("Lead", "#f2b134")}
    needed = [p for p in parts if any(p in s.get("parts", []) for s in sections)]
    existing = {t["name"]: t["index"] for t in bw.call("get_session")["tracks"]}
    idx, loaded = {}, {}
    for p in needed:
        name, color = parts[p]
        if name in existing:
            idx[p] = existing[name]
        else:
            idx[p] = create_track("instrument", name=name, color=color)["index"]
            if load_instruments:
                sound = presets.default_sound(p, drum_style)
                load_preset(sound, track_index=idx[p])
                loaded[name] = sound

    four_floor = drum_style in ("house", "techno", "garage")
    results = []
    for si, sec in enumerate(sections):
        bw.call("set_scene_name", scene=si, name=sec["name"])
        var = sec.get("variation")
        s = None if seed is None else seed + si
        calm = sec["name"].lower() in ("intro", "breakdown", "outro")
        for p in sec.get("parts", []):
            t = idx[p]
            if p == "drums":
                r = write_drums(t, si, drum_style, bars=len(chords), fill=var == "build", seed=s)
            elif p == "bass":
                style = "syncopated" if var == "alt" else "offbeat" if four_floor else "eighths"
                r = write_bass(t, si, chords, key=key, scale=scale, style=style, seed=s)
            elif p == "chords":
                rhythm = "sustained" if calm else "arp_up" if var == "build" else "stabs"
                r = write_chords(t, si, chords, key=key, scale=scale, rhythm=rhythm)
            elif p == "lead":
                r = write_melody(t, si, chords, key=key, scale=scale, density=0.7 if var == "build" else 0.5,
                                 seed=(seed or 0) + (7 if var == "alt" else 0))
            else:
                raise ValueError(f"unknown part {p!r}; use drums, bass, chords, lead")
            results.append({"section": sec["name"], "part": p, **r})
    return {"tracks": {p: idx[p] for p in needed}, "scenes": [s["name"] for s in sections],
            "instruments_loaded": loaded,
            "clips_written": len(results), "unverified": [r for r in results if not r["verified"]],
            "next": "Launch scene 0, 1, 2... in order (launch(scene=0))."}


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


# --- Presets & instruments ---
@tool()
def search_presets(query: str, kind: str | None = None, limit: int = 20) -> list[dict]:
    """Search the factory/user preset library and built-in devices by name or pack
    (e.g. 'pad', '808 kit', 'rhodes', 'EQ+', 'Analog Waves bass'). kind: 'preset' or 'device'."""
    return [{"name": p["name"], "type": p["type"], "pack": p["pack"]} for p in presets.search(query, kind, limit)]


@tool()
def load_preset(name: str, track_index: int | None = None, where: str = "end") -> dict:
    """Load a preset or built-in device (Polysynth, Drum Machine, EQ+, Compressor, Reverb...) onto a
    track by name or file path. where: 'end' (after existing devices) or 'start'. Verified by
    listing the track's devices afterwards."""
    path = presets.resolve(name)
    if track_index is not None:
        bw.call("select_track", track_index=track_index)
        time.sleep(SETTLE)
    before = len(bw.call("list_devices")["devices"])
    bw.call("insert_file", path=path, where=where)
    for _ in range(12):  # sample-based presets can take a moment
        time.sleep(0.25)
        devs = bw.call("list_devices")
        if len(devs["devices"]) > before:
            time.sleep(0.3)  # let the preset name arrive before naming the track
            idx = track_index if track_index is not None else bw.call("get_session")["selected_track"]["index"]
            renamed = _auto_name_one(idx, path)
            return {"loaded": os.path.basename(path), "track": renamed or devs["track"],
                    "devices": bw.call("list_devices")["devices"], "auto_named": bool(renamed)}
    raise RuntimeError(f"Bitwig did not load {path}")


@tool()
def refresh_preset_index() -> dict:
    """Rescan the disk for presets (after installing packages or saving new presets)."""
    return {"indexed": len(presets.index(refresh=True))}


# --- Clip editing ---
def _read_clip(track_index: int, slot: int):
    bw.call("focus_clip", track_index=track_index, slot=slot)
    time.sleep(0.6)
    notes, offset = [], 0
    while True:
        r = bw.call("get_notes", offset=offset, limit=120)
        notes += r["notes"]
        offset += len(r["notes"])
        if not r["notes"] or offset >= r["total"]:
            return notes, r["loop_length"]


@tool()
def get_clip_notes(track_index: int, slot: int) -> dict:
    """Read every note in a launcher clip (pitch, start, duration, velocity; beats, 1/32 resolution),
    plus its loop length and estimated key."""
    notes, length = _read_clip(track_index, slot)
    return {"length_beats": length, "count": len(notes), "key_estimate": music.detect_key(notes), "notes": notes}


@tool()
def edit_clip(track_index: int, slot: int, operation: str, grid: float = 0.25, strength: float = 1.0,
              swing: float = 0.0, semitones: int = 0, key: str | None = None, scale: str = "major",
              amount: float = 1.0, offset: int = 0, compress: float = 0.0, timing: float = 0.01,
              velocity: int = 10, factor: float = 2.0, times: int = 2, seed: int | None = None) -> dict:
    """Edit an existing clip's notes in place. operations:
    quantize (grid beats e.g. 0.25 = 1/16, strength 0..1, swing 0..1), humanize (timing beats, velocity),
    transpose (semitones), scale_correct (key, scale), reverse, stretch (factor: 2 = half speed,
    0.5 = double speed), legato, velocity (amount x, offset +, compress 0..1 toward mean),
    repeat (times: loop the clip content N times), double (= repeat 2). Returns before/after counts."""
    notes, length = _read_clip(track_index, slot)
    if not notes:
        raise RuntimeError("clip is empty or could not be read")
    new_len = length
    if operation == "quantize":
        out = music.quantize(notes, grid, strength, swing)
    elif operation == "humanize":
        out = music.humanize(notes, timing, velocity, seed)
    elif operation == "transpose":
        out = music.transpose(notes, semitones)
    elif operation == "scale_correct":
        if not key:
            key, scale = music.detect_key(notes)[0]["key"], music.detect_key(notes)[0]["scale"]
        out = music.scale_correct(notes, key, scale)
    elif operation == "reverse":
        out = music.reverse(notes, length)
    elif operation == "stretch":
        out, new_len = music.stretch(notes, factor), length * factor
    elif operation == "legato":
        out = music.legato(notes, length)
    elif operation == "velocity":
        out = music.scale_velocity(notes, amount, offset, compress)
    elif operation in ("repeat", "double"):
        n = 2 if operation == "double" else times
        out, new_len = music.repeat(notes, length, n), length * n
    else:
        raise ValueError("unknown operation")
    res = _write(track_index, slot, out, new_len)
    return {"operation": operation, "notes_before": len(notes), "notes_after": len(out),
            "length_beats": new_len, "verified": res["verified"],
            **({"key": key, "scale": scale} if operation == "scale_correct" else {})}


# --- Metering & gain staging ---
@tool()
def get_levels(seconds: float = 4.0) -> dict:
    """Measure peak levels on every track and the master while Bitwig plays (start playback or
    launch clips first). Meters are Bitwig's 0..1 meter scale; ~1.0 means clipping."""
    bw.call("reset_meters")
    time.sleep(seconds)
    m = bw.call("get_meters")
    warn = []
    if not m["playing"]:
        warn.append("transport not playing - levels may be zero unless clips are launched")
    for t in m["tracks"]:
        if t["hold"] >= 0.98:
            warn.append(f"{t['name']} is clipping")
    if m["master"]["hold"] >= 0.98:
        warn.append("MASTER is clipping")
    return {"tracks": [{"index": t["index"], "name": t["name"], "peak": round(t["hold"], 3),
                        "fader": t["volume_display"], "muted": t["muted"]} for t in m["tracks"]],
            "master": {"peak": round(m["master"]["hold"], 3), "fader": m["master"]["volume_display"]},
            "warnings": warn}


@tool()
def gain_stage(target_peak: float = 0.7, track_indices: list[int] | None = None, seconds: float = 3.0,
               passes: int = 3, max_change_db: float = 12.0) -> dict:
    """Auto-balance track faders so each track's peak meter lands near target_peak (0..1), leaving
    master headroom. Needs audio playing (launch a scene first). Iterates `passes` times, measuring
    and nudging faders; silent or muted tracks are skipped. Returns before/after levels."""
    before = get_levels(seconds)
    tracks = {t["index"]: t for t in before["tracks"]}
    targets = [i for i in (track_indices or tracks) if i in tracks and not tracks[i]["muted"]]
    # Bitwig's meter is roughly linear in dB (~0.023 meter units per dB measured); refine the slope
    # per track from each move so later passes land on target.
    slope = {i: 0.023 for i in targets}
    last = {}
    current = before
    for _ in range(passes):
        levels = {t["index"]: t for t in current["tracks"]}
        changed = False
        for i in targets:
            peak = levels[i]["peak"]
            if peak < 0.01:
                continue
            if i in last:
                prev_peak, moved_db = last[i]
                if abs(moved_db) > 0.5 and abs(peak - prev_peak) > 0.005:
                    slope[i] = max(0.005, min(0.06, (peak - prev_peak) / moved_db))
            delta = (target_peak - peak) / slope[i]
            delta = max(-max_change_db, min(max_change_db, delta))
            if abs(target_peak - peak) < 0.01:
                continue
            cur_db = _parse_db(bw.call("get_track", track_index=i)["volume_display"])
            new_db = max(-60, min(6, cur_db + delta))
            _set_volume_db(i, new_db)
            last[i] = (peak, new_db - cur_db)
            changed = True
        current = get_levels(seconds)
        if not changed:
            break
    return {"before": before, "after": current}


# --- Transport, groove & markers ---
@tool()
def get_transport() -> dict:
    """Full transport state: tempo, time signature, arranger loop, punch in/out, arranger record,
    automation write mode, launch quantization, groove settings and cue markers."""
    return bw.call("get_transport")


@tool()
def set_transport(loop_enabled: bool | None = None, loop_start: float | None = None,
                  loop_length: float | None = None, time_signature: str | None = None,
                  punch_in: bool | None = None, punch_out: bool | None = None,
                  launch_quantization: str | None = None, arranger_record: bool | None = None,
                  automation_write: bool | None = None, automation_mode: str | None = None) -> dict:
    """Change transport settings; only given fields change. Loop positions in beats.
    time_signature like '3/4' or '7/8'. launch_quantization: none, 8, 4, 2, 1, 1/2, 1/4, 1/8, 1/16.
    automation_mode: latch, touch, write. Returns the resulting transport state."""
    cmds = []
    if any(v is not None for v in (loop_enabled, loop_start, loop_length)):
        cmds.append(("set_loop", {"enabled": loop_enabled, "start": loop_start, "length": loop_length}))
    if time_signature:
        num, den = (int(x) for x in time_signature.split("/"))
        cmds.append(("set_time_signature", {"numerator": num, "denominator": den}))
    if punch_in is not None or punch_out is not None:
        cmds.append(("set_punch", {"punch_in": punch_in, "punch_out": punch_out}))
    if launch_quantization:
        cmds.append(("set_launch_quantization", {"value": launch_quantization}))
    if arranger_record is not None:
        cmds.append(("set_arranger_record", {"enabled": arranger_record}))
    if automation_write is not None or automation_mode:
        cmds.append(("set_automation", {"write": automation_write, "mode": automation_mode}))
    if cmds:
        bw.batch(cmds)
    time.sleep(SETTLE)
    t = bw.call("get_transport")
    t.pop("groove", None)
    return t


@tool()
def set_groove(enabled: bool | None = None, shuffle_amount: float | None = None,
               shuffle_rate: str | None = None, accent_amount: float | None = None) -> dict:
    """Bitwig's global groove. shuffle_amount and accent_amount 0..1 (0.5 shuffle = none, higher =
    swing). shuffle_rate '1/8' or '1/16'. Returns the groove state."""
    args = {}
    if enabled is not None:
        args["enabled"] = 1.0 if enabled else 0.0
    if shuffle_amount is not None:
        args["shuffle_amount"] = shuffle_amount
    if shuffle_rate is not None:
        args["shuffle_rate"] = 0.0 if shuffle_rate == "1/8" else 1.0
    if accent_amount is not None:
        args["accent_amount"] = accent_amount
    bw.call("set_groove", **args)
    time.sleep(SETTLE)
    return bw.call("get_transport")["groove"]


@tool()
def cue_markers(action: str = "list", index: int | None = None) -> dict | str:
    """Arranger cue markers. action: list, add (at play head), jump (to marker index)."""
    if action == "add":
        bw.call("add_cue_marker")
        time.sleep(SETTLE)
    elif action == "jump":
        return bw.call("launch_cue_marker", index=index)
    return {"cue_markers": bw.call("get_transport")["cue_markers"]}


@tool()
def save_project() -> str:
    """Save the current Bitwig project (same as Ctrl+S)."""
    return bw.call("save_project")


# --- Mixer snapshots ---
SNAP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snapshots")


def _mixer_state():
    s = bw.call("get_session")
    return {"tempo": s["tempo"], "tracks": [
        {k: t[k] for k in ("index", "name", "volume", "volume_display", "pan", "mute", "solo", "sends")}
        for t in s["tracks"]]}


def _snap_path(name):
    safe = re.sub(r"[^\w\- ]", "_", name).strip()
    if not safe:
        raise ValueError("snapshot name required")
    return os.path.join(SNAP_DIR, safe + ".json")


@tool()
def snapshot(action: str, name: str | None = None, other: str | None = None,
             include_tempo: bool = False) -> dict:
    """Mixer snapshots (volume, pan, mute, solo, sends per track; matched by track name).
    action: save (name), recall (name; include_tempo to restore tempo), list, delete (name),
    diff (name vs current mix, or vs `other` snapshot). Use for A/B mix comparisons and as a safety net
    before big changes (save 'before', then recall it to undo everything)."""
    os.makedirs(SNAP_DIR, exist_ok=True)
    if action == "list":
        return {"snapshots": sorted(f[:-5] for f in os.listdir(SNAP_DIR) if f.endswith(".json"))}
    path = _snap_path(name or "")
    if action == "save":
        state = _mixer_state()
        state["saved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=1)
        return {"saved": name, "tracks": len(state["tracks"])}
    if not os.path.exists(path):
        raise ValueError(f"no snapshot named {name!r}")
    with open(path, encoding="utf-8") as f:
        snap = json.load(f)
    if action == "delete":
        os.remove(path)
        return {"deleted": name}
    live = {t["name"]: t for t in bw.call("get_session")["tracks"]}
    if action == "recall":
        cmds, missing = [], []
        for t in snap["tracks"]:
            cur = live.get(t["name"])
            if not cur:
                missing.append(t["name"])
                continue
            i = cur["index"]
            cmds += [("set_track_volume", {"track_index": i, "value": t["volume"]}),
                     ("set_track_pan", {"track_index": i, "value": t["pan"]}),
                     ("set_track_mute", {"track_index": i, "value": t["mute"]}),
                     ("set_track_solo", {"track_index": i, "value": t["solo"]})]
            cmds += [("set_send", {"track_index": i, "send_index": s["index"], "value": s["value"]})
                     for s in t["sends"]]
        if include_tempo:
            cmds.append(("set_tempo", {"bpm": snap["tempo"]}))
        bw.batch(cmds)
        return {"recalled": name, "tracks": len(snap["tracks"]) - len(missing), "missing_tracks": missing}
    if action == "diff":
        if other:
            with open(_snap_path(other), encoding="utf-8") as f:
                ref = {t["name"]: t for t in json.load(f)["tracks"]}
        else:
            ref = live
        diffs = []
        for t in snap["tracks"]:
            r = ref.get(t["name"])
            if not r:
                diffs.append({"track": t["name"], "change": "missing"})
                continue
            d = {k: [t[k], r[k]] for k in ("volume_display", "mute", "solo") if t[k] != r[k]}
            if abs(t["pan"] - r["pan"]) > 0.005:
                d["pan"] = [round(t["pan"] * 2 - 1, 2), round(r["pan"] * 2 - 1, 2)]
            sd = [(s["name"], s["value"], rs["value"]) for s, rs in zip(t["sends"], r["sends"])
                  if abs(s["value"] - rs["value"]) > 0.005]
            if sd:
                d["sends"] = sd
            if d:
                diffs.append({"track": t["name"], **d})
        return {"compare": f"{name} -> {other or 'current'}", "differences": diffs}
    raise ValueError("action must be save, recall, list, delete or diff")


# --- Samples ---
@tool()
def search_samples(query: str = "", category: str | None = None, kind: str | None = None,
                   bpm: float | None = None, bpm_tolerance: float = 3, key: str | None = None,
                   pack: str | None = None, limit: int = 20) -> dict:
    """Search ~14k samples (Bitwig packs, Splice, extra folders). BPM/key/category are parsed from
    file names. category: kick, snare, clap, hat, cymbal, tom, perc, 808, drum loop, bass, vocal,
    guitar, piano, pad, synth, strings, brass, fx, other. kind: loop or one-shot. bpm matches
    half/double time too. key like 'Am', 'F#', 'C'."""
    hits = samples.search(query, category, kind, bpm, bpm_tolerance, key, pack, limit)
    return {"count": len(hits), "samples": [
        {"name": h["name"], "pack": h["pack"], "category": h["category"], "kind": h["kind"],
         "bpm": h["bpm"], "key": h["key"], "seconds": samples.duration(h["path"]), "path": h["path"]}
        for h in hits]}


@tool()
def load_sample(sample: str, track_index: int | None = None, slot: int = 0, mode: str = "clip",
                new_track_name: str | None = None) -> dict:
    """Load a sample (name from search_samples, a bookmark label, or a file path).
    mode 'clip': put it as an audio clip in a launcher slot (needs an audio track).
    mode 'sampler': load it into a Sampler instrument on an instrument track (play it with MIDI).
    If track_index is omitted, a new track of the right type is created."""
    path = _resolve_sound(sample, want="sample")
    if mode not in ("clip", "sampler"):
        raise ValueError("mode must be clip or sampler")
    if track_index is None:
        kind = "audio" if mode == "clip" else "instrument"
        track_index = create_track(kind, name=new_track_name or os.path.splitext(os.path.basename(path))[0][:24])["index"]
    if mode == "clip":
        bw.call("insert_file_to_slot", track_index=track_index, slot=slot, path=path)
        for _ in range(12):
            time.sleep(0.25)
            clips = bw.call("get_track", track_index=track_index)["clips"]
            if any(c["slot"] == slot for c in clips):
                renamed = _auto_name_one(track_index, path)
                return {"loaded": os.path.basename(path), "track_index": track_index, "slot": slot, "mode": mode,
                        "track_name": renamed or bw.call("get_track", track_index=track_index)["name"]}
        raise RuntimeError("Bitwig did not create the clip (is it an audio track?)")
    res = load_preset(path, track_index=track_index)
    return {"loaded": os.path.basename(path), "track_index": track_index, "mode": mode, "devices": res["devices"]}


@tool()
def preview_sample(sample: str | None = None, stop: bool = False) -> str:
    """Audition a .wav sample through Windows audio (outside Bitwig). stop=True stops playback."""
    import winsound
    if stop or not sample:
        winsound.PlaySound(None, winsound.SND_PURGE)
        return "stopped"
    path = _resolve_sound(sample, want="sample")
    if not path.lower().endswith(".wav"):
        raise ValueError("preview supports .wav files only; load it into Bitwig instead")
    winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
    return f"playing {os.path.basename(path)}"


@tool()
def sample_folders(add: str | None = None, rescan: bool = False) -> dict:
    """List the folders the sample index scans; add a folder; or rescan after adding new samples."""
    fs = samples.add_folder(add) if add else samples.folders()
    if add or rescan:
        return {"folders": fs, "indexed": len(samples.index(refresh=True))}
    return {"folders": fs}


# --- Bookmarks ---
def _resolve_sound(name: str, want: str | None = None) -> str:
    """Path, bookmark label, then sample/preset index."""
    if os.path.exists(name):
        return name
    try:
        return bookmarks.find(name)["path"]
    except ValueError:
        pass
    if want == "sample":
        return samples.resolve(name)
    return presets.resolve(name)


@tool()
def bookmark(action: str = "list", item: str | None = None, label: str | None = None,
             tags: list[str] | None = None, note: str = "", tag: str | None = None, kind: str | None = None,
             query: str | None = None, remove_tags: list[str] | None = None,
             track_index: int | None = None, slot: int = 0, mode: str = "clip") -> dict | list:
    """Your favourite sounds. action:
    add (item = preset/device/sample name or file/folder path; optional label, tags, note),
    list (filter by tag, kind preset|device|sample|folder, or query),
    tag (item = bookmark label; tags to add, remove_tags, note),
    remove (item = bookmark label),
    load (item = bookmark label; presets/devices go onto track_index, samples use slot/mode like load_sample;
    folders return their samples)."""
    if action == "list":
        return bookmarks.listing(tag, kind, query)
    if not item:
        raise ValueError("item is required")
    if action == "add":
        if os.path.exists(item):
            path = item
        else:
            hits = presets.search(item, limit=1)
            exact = hits and hits[0]["name"].lower() == item.lower()
            path = hits[0]["path"] if exact else None
            if not path:
                s = samples.search(item, limit=1)
                path = s[0]["path"] if s else (hits[0]["path"] if hits else None)
            if not path:
                raise ValueError(f"nothing found for {item!r}")
        return bookmarks.add(path, label, tags, note)
    if action == "tag":
        return bookmarks.tag(item, tags, remove_tags, note or None)
    if action == "remove":
        return {"removed": bookmarks.remove(item)}
    if action == "load":
        b = bookmarks.find(item)
        if b["kind"] in ("preset", "device"):
            return load_preset(b["path"], track_index=track_index)
        if b["kind"] == "sample":
            return load_sample(b["path"], track_index=track_index, slot=slot, mode=mode)
        return {
            "folder": b["path"],
            "samples": [{"name": s["name"], "category": s["category"], "bpm": s["bpm"], "key": s["key"]}
                        for s in samples.index() if s["path"].startswith(b["path"])][:50]}
    raise ValueError("action must be add, list, tag, remove or load")


# --- Expert note editing ---


@tool()
def note_expressions(track_index: int, slot: int, select: dict | None = None, set: dict | None = None,
                     ramp: dict | None = None, randomize: dict | None = None, seed: int | None = None) -> dict:
    """Shape Bitwig per-note expressions on selected notes (they're kept by all other edits).
    Properties: velocity (1-127), release_velocity (0-127), velocity_spread (0..1), gain (0..1, 0 = default),
    pan (-1..1), timbre (-1..1), pressure (0..1; Bitwig doesn't report it back, so unverified),
    transpose (micro-pitch in semitones, e.g. 0.5),
    chance (0..1 probability), muted (bool), repeat ({"count": 3, "curve": -1..1, "velocity_curve": -1..1,
    "velocity_end": -1..1}; count 0 = off; ratchets), recurrence ({"length": 4, "mask": 5} = play on cycles
    1 and 3 of 4; mask is a bitfield), occurrence ('ALWAYS', 'FIRST', 'NOT_FIRST', 'PREV', 'NOT_PREV',
    'PREV_CHANNEL', 'NOT_PREV_CHANNEL', 'PREV_KEY', 'NOT_PREV_KEY', 'FILL', 'NOT_FILL').
    set: fixed values; ramp: {"velocity": [40, 120]} across the selection (crescendo, pan sweep...);
    randomize: {"timbre": 0.3, "velocity": 12} adds +/- amount. select: optional note filter, e.g. {"pitch": [36, 36]} (range) or {"pitches": [36, 38]},
    {"start": [0, 8]} beats, {"velocity": [0, 80]}, {"beat": [0, 2]} (beats 1 & 3 of each bar),
    {"offbeat": true}, {"every": 2, "offset": 1}, {"chance": 0.5}, {"top": true} / {"bottom": true}
    (highest/lowest note of each chord). Keys combine with AND; omit to edit every note."""
    notes, _ = _read_clip(track_index, slot)
    chosen = expert.select(notes, select, seed)
    if not chosen:
        raise RuntimeError("no notes matched the selection")
    updates = expert.shape(chosen, set, ramp, randomize, seed)
    res = {"updated": 0, "not_found": []}
    for i in range(0, len(updates), 200):
        r = bw.call("set_note_props", notes=updates[i:i + 200])
        res["updated"] += r["updated"]
        res["not_found"] += r["not_found"]
    # Expression-only changes don't fire note events, so force a fresh read to verify.
    after = {(n["start"], n["pitch"]): n for n in _read_clip(track_index, slot)[0]}
    sample_after = [after.get((u["start"], u["pitch"])) for u in updates[:3]]
    return {"selected": len(chosen), **res, "example_after": sample_after}


@tool()
def transform_notes(track_index: int, slot: int, operation: str, select: dict | None = None,
                    semitones: int = 0, beats: float = 0.0, intervals: list[int] | None = None,
                    key: str | None = None, scale: str = "major", axis: float | None = None,
                    rate: float = 0.25, pattern: str = "up", gate: float = 0.9, amount: float = 0.03,
                    direction: str = "down", division: float = 0.25, length: float | None = None,
                    factor: float | None = None, spread: int = 2, mode: str = "drop2", inversion: int = 1,
                    accent_pattern: str = "x...", boost: int = 25, keep: float = 0.5,
                    seed: int | None = None) -> dict:
    """Advanced edits on selected notes (per-note expressions are preserved). operations:
    transpose (semitones), nudge (beats, +/-), delete, mute, unmute,
    harmonize (intervals in scale steps: [2] = 3rd above, [2, 4] = triad, [-7] = octave below; key/scale,
    detected if omitted), invert (mirror around axis pitch), arpeggiate (rate beats, pattern
    up/down/updown/random, gate), strum (amount beats, direction down/up), flam (amount = grace offset),
    chop (division beats), set_length (length beats, or factor), randomize_pitch (spread steps, in key if
    given), voicing (mode close/open/drop2/drop3/inversion/spread_octaves, inversion n), accent
    (accent_pattern of x . - per 16th, boost), thin (keep 0..1 of notes). select: optional note filter, e.g. {"pitch": [36, 36]} (range) or {"pitches": [36, 38]},
    {"start": [0, 8]} beats, {"velocity": [0, 80]}, {"beat": [0, 2]} (beats 1 & 3 of each bar),
    {"offbeat": true}, {"every": 2, "offset": 1}, {"chance": 0.5}, {"top": true} / {"bottom": true}
    (highest/lowest note of each chord). Keys combine with AND; omit to edit every note."""
    notes, length_beats = _read_clip(track_index, slot)
    if not notes:
        raise RuntimeError("clip is empty or could not be read")
    chosen = expert.select(notes, select, seed)
    if not chosen:
        raise RuntimeError("no notes matched the selection")

    # Native moves/deletes keep everything Bitwig stores on the note.
    if operation in ("transpose", "nudge"):
        moves = [{"start": n["start"], "pitch": n["pitch"], "d_pitch": semitones if operation == "transpose" else 0,
                  "d_start": beats if operation == "nudge" else 0} for n in chosen]
        # move in an order that never lands on a note that hasn't moved yet
        rev = (semitones > 0) if operation == "transpose" else (beats > 0)
        moves.sort(key=lambda m: (m["pitch"], m["start"]) if operation == "transpose" else (m["start"], m["pitch"]),
                   reverse=rev)
        bw.call("move_notes", notes=moves)
        return {"operation": operation, "notes": len(moves)}
    if operation == "delete":
        bw.call("delete_notes", notes=[{"start": n["start"], "pitch": n["pitch"]} for n in chosen])
        return {"operation": operation, "deleted": len(chosen)}
    if operation in ("mute", "unmute"):
        bw.call("set_note_props", notes=[{"start": n["start"], "pitch": n["pitch"], "muted": operation == "mute"}
                                         for n in chosen])
        return {"operation": operation, "notes": len(chosen)}

    if operation in ("harmonize", "randomize_pitch") and not key and operation == "harmonize":
        k = music.detect_key(notes)[0]
        key, scale = k["key"], k["scale"]
    ops = {
        "harmonize": lambda: expert.harmonize(notes, chosen, intervals or [2], key, scale),
        "invert": lambda: expert.invert(notes, chosen, axis),
        "arpeggiate": lambda: expert.arpeggiate(notes, chosen, rate, pattern, gate, seed),
        "strum": lambda: expert.strum(notes, chosen, amount, direction),
        "flam": lambda: expert.flam(notes, chosen, amount),
        "chop": lambda: expert.chop(notes, chosen, division, gate),
        "set_length": lambda: expert.set_length(notes, chosen, length, factor or 1.0),
        "randomize_pitch": lambda: expert.randomize_pitch(notes, chosen, spread, key, scale, seed),
        "voicing": lambda: expert.voicing(notes, chosen, mode, inversion),
        "accent": lambda: expert.accent(notes, chosen, accent_pattern, 0.25, boost),
        "thin": lambda: expert.thin(notes, chosen, keep, seed),
    }
    if operation not in ops:
        raise ValueError(f"unknown operation {operation!r}")
    out = [n for n in ops[operation]() if 0 <= n["start"] < length_beats + 1e-6]
    res = _write(track_index, slot, out, length_beats)
    return {"operation": operation, "selected": len(chosen), "notes_before": len(notes), "notes_after": len(out),
            "verified": res["verified"], **({"key": key, "scale": scale} if operation == "harmonize" else {})}


@tool()
def clip_settings(track_index: int, slot: int, loop_start: float | None = None, loop_length: float | None = None,
                  loop_enabled: bool | None = None, play_start: float | None = None, play_stop: float | None = None,
                  shuffle: bool | None = None, accent: float | None = None, launch_mode: str | None = None,
                  launch_quantization: str | None = None, name: str | None = None, color: str | None = None,
                  show_in_editor: bool = False) -> dict:
    """Read or change a launcher clip's settings: loop start/length (beats), loop on/off, play start/stop,
    groove shuffle on/off, accent (0..1), launch_mode (default, from_start, continue_or_from_start,
    continue_or_synced, synced), launch_quantization (default, none, 8, 4, 2, 1, 1/2, 1/4, 1/8, 1/16),
    name, color (hex). show_in_editor opens it in Bitwig's detail editor. Returns the settings after."""
    bw.call("focus_clip", track_index=track_index, slot=slot)
    time.sleep(0.4)
    args = {k: v for k, v in dict(loop_start=loop_start, loop_length=loop_length, loop_enabled=loop_enabled,
                                  play_start=play_start, play_stop=play_stop, shuffle=shuffle, accent=accent,
                                  launch_mode=launch_mode, launch_quantization=launch_quantization,
                                  name=name).items() if v is not None}
    if color:
        args["color"] = _hex_to_rgb(color)
    if args:
        bw.call("set_clip_settings", **args)
        time.sleep(SETTLE)
    if show_in_editor:
        bw.call("show_clip_in_editor")
    return bw.call("get_clip_settings")


@tool()
def write_euclidean(track_index: int, slot: int, layers: list[dict], steps_per_beat: int = 4, bars: int = 1) -> dict:
    """Polyrhythmic Euclidean patterns. layers: [{"pitch": 36, "pulses": 4, "steps": 16, "rotation": 0,
    "velocity": 110, "accent_first": true, "chance": 1.0}, ...]. Each layer spreads `pulses` hits as evenly
    as possible over `steps` (each step = 1/steps_per_beat beats), looping to fill `bars`. Different step
    counts per layer create polymeters (e.g. 3 over 16 against 4 over 16, or 5/12)."""
    length = bars * 4
    notes = []
    step_len = 1 / steps_per_beat
    for L in layers:
        if not (1 <= L.get("steps", 0) <= 64) or not (0 <= L.get("pulses", -1) <= L["steps"]):
            raise ValueError(f"layer {L}: need 1 <= steps <= 64 and 0 <= pulses <= steps")
    layers = [L for L in layers if L["pulses"] > 0]
    for L in layers:
        pat = expert.euclid(L["pulses"], L["steps"], L.get("rotation", 0))
        total = int(length / step_len)
        for i in range(total):
            if pat[i % len(pat)]:
                first = (i % len(pat)) == next(j for j, b in enumerate(pat) if b)
                v = L.get("velocity", 100) + (15 if first and L.get("accent_first", True) else 0)
                n = {"pitch": L["pitch"], "start": i * step_len, "duration": step_len * 0.9, "velocity": min(127, v)}
                if L.get("chance", 1) < 1:
                    n["chance"] = L["chance"]
                notes.append(n)
    return _write(track_index, slot, notes, length, "euclidean")


# --- Mastering & analysis ---
CHAINS = {  # device order on the master bus
    "streaming": ["EQ+", "Compressor+", "Tool", "Peak Limiter"],
    "club": ["EQ+", "Compressor+", "Saturator", "Tool", "Peak Limiter"],
    "gentle": ["EQ+", "Tool", "Peak Limiter"],
}
CHAIN_ROLES = {"eq": "EQ+", "compressor": "Compressor+", "width": "Tool", "limiter": "Peak Limiter",
               "saturator": "Saturator"}


def _num(display: str):
    if display is None:
        return None
    d = display.replace("−", "-")
    if "inf" in d.lower():
        return -200.0 if "-" in d else 200.0
    if d.strip().lower() in ("off", "on"):
        return 1.0 if d.strip().lower() == "on" else 0.0
    m = re.search(r"-?\d+(\.\d+)?", d)
    if not m:
        return None
    v = float(m.group())
    if re.search(r"\d\s*k(hz)?\b", d.lower()):
        v *= 1000
    return v


def _master_device(name: str) -> int:
    bw.call("select_master")
    time.sleep(SETTLE)
    devs = bw.call("list_devices")["devices"]
    hit = next((d for d in devs if d["name"].lower() == name.lower()), None)
    if not hit:
        raise RuntimeError(f"no {name} on the master (build a chain with mastering_chain first)")
    return hit["index"]


def _set_param_display(device_index: int, param: str, target: float, tol: float = 0.05) -> str:
    """Select a remote control by name and binary-search its normalized value until the displayed value
    reads `target` (dB, %, s...). Assumes the control increases with its normalized value."""
    bw.call("select_device", device_index=device_index)
    time.sleep(SETTLE)
    dev = bw.call("get_device")
    order = [dev["page_index"]] + [p for p in range(len(dev["pages"])) if p != dev["page_index"]]
    idx = None
    for page in order:
        if page != dev["page_index"]:
            bw.call("select_remote_page", page=page)
            time.sleep(SETTLE)
            dev = bw.call("get_device")
        hit = next((p for p in dev["params"] if p["name"].lower() == param.lower()), None) or \
            next((p for p in dev["params"] if param.lower() in p["name"].lower()), None)
        if hit:
            idx = hit["index"]
            break
    if idx is None:
        raise RuntimeError(f"no control named {param!r} on {dev['device']}")
    lo, hi = 0.0, 1.0
    shown = None
    for _ in range(16):
        mid = (lo + hi) / 2
        bw.call("set_remote_param", index=idx, value=mid)
        time.sleep(0.05)
        shown = next(p for p in bw.call("get_device")["params"] if p["index"] == idx)["display"]
        v = _num(shown)
        if v is None or abs(v - target) <= tol:
            break
        lo, hi = (mid, hi) if v < target else (lo, mid)
    return shown


def _analysis_reply(x, sr, src, target, show_image):
    m = mastering.analyze(x, sr, target)
    m["source"] = src
    out = [json.dumps(m, indent=1)]
    if show_image:
        out.append(Image(data=mastering.render(x, sr, m, f"Master analysis - {src}"), format="png"))
    return out


@tool()
def analyze_master(seconds: float = 10.0, source: str = "live", target: str = "streaming", start: float = 0.0,
                   show_image: bool = True) -> list:
    """Mastering analysis shown directly in the chat (data + a dashboard image): integrated / short-term /
    momentary LUFS, loudness range, true peak, sample peak, clipping, crest factor, PLR, L/R balance,
    MID/SIDE levels and width, phase correlation (overall and worst 400 ms), mono-compatibility loss,
    per-band mid/side (sub, bass, low-mid, high-mid, air), DC offset, and advice vs a target
    (streaming, spotify, youtube, apple, soundcloud, club, cd, broadcast).
    source='live' records what's playing right now through Windows loopback (play your song first;
    needs Bitwig on a WASAPI/'Windows Audio' driver, not exclusive ASIO). source=<wav path> analyzes an
    exported bounce or recording (start/seconds pick a section; seconds=0 = whole file)."""
    if source == "live":
        if seconds <= 0:
            raise ValueError("seconds must be > 0 for live capture")
        try:
            x, sr, src = mastering.capture_loopback(seconds)
        except RuntimeError as e:
            meters = master_meters(min(seconds, 3))
            return [json.dumps({"live_capture": "unavailable", "why": str(e),
                                "fallback_bitwig_meters": meters}, indent=1)]
    else:
        path = source if os.path.exists(source) else samples.resolve(source)
        x, sr, src = mastering.load_file(path, start, seconds or None)
    return _analysis_reply(x, sr, src, target, show_image)


@tool()
def master_meters(seconds: float = 3.0) -> dict:
    """Bitwig's own master meters over a few seconds (works with any audio driver): left/right peak and
    RMS on Bitwig's 0..1 meter scale plus L/R balance. For LUFS, mid/side and spectrum use analyze_master."""
    bw.call("reset_master_meters")
    rms_l, rms_r = [], []
    t0 = time.time()
    while time.time() - t0 < seconds:
        m = bw.call("get_master_meters")
        rms_l.append(m["left"]["rms"])
        rms_r.append(m["right"]["rms"])
        time.sleep(0.1)
    m = bw.call("get_master_meters")
    avg_l, avg_r = sum(rms_l) / len(rms_l), sum(rms_r) / len(rms_r)
    playing = bw.call("get_session")["playing"]
    return {"playing": playing, "peak_hold": {"left": round(m["hold_left"], 3), "right": round(m["hold_right"], 3)},
            "avg_rms": {"left": round(avg_l, 3), "right": round(avg_r, 3)},
            "balance": "centred" if abs(avg_l - avg_r) < 0.01 else ("left-heavy" if avg_l > avg_r else "right-heavy"),
            "clipping": m["hold_left"] >= 0.98 or m["hold_right"] >= 0.98}


@tool()
def mastering_chain(action: str = "list", style: str = "streaming", target: str = "streaming",
                    device_index: int | None = None) -> dict:
    """Manage the master-bus chain. action: list (devices + their main controls), build (append a chain:
    streaming = EQ+ > Compressor+ > Tool > Peak Limiter; club adds Saturator; gentle = EQ+ > Tool >
    Peak Limiter; the limiter ceiling is set for `target`), remove (device_index), bypass / enable
    (device_index). Existing master devices are left alone on build."""
    bw.call("select_master")
    time.sleep(SETTLE)
    if action == "build":
        if style not in CHAINS:
            raise ValueError(f"style must be one of {', '.join(CHAINS)}")
        chain = CHAINS[style]
        for pos, dev in enumerate(chain):
            devs = bw.call("list_devices")["devices"]
            if any(d["name"] == dev for d in devs):
                continue
            # keep chain order: insert before the next chain device already present, else at the end
            later = next((d["index"] for name in chain[pos + 1:] for d in devs if d["name"] == name), None)
            bw.call("insert_file", path=presets.resolve(dev, "device"),
                    **({"before_device": later} if later is not None else {}))
            time.sleep(1.0)
        ceiling = mastering.TARGETS.get(target, mastering.TARGETS["streaming"])[1]
        _set_param_display(_master_device("Peak Limiter"), "Ceiling", ceiling - 0.1)  # margin for inter-sample peaks
    elif action == "remove":
        bw.call("delete_device", device_index=device_index)
        time.sleep(0.4)
    elif action in ("bypass", "enable"):
        bw.call("select_device", device_index=device_index)
        time.sleep(SETTLE)
        bw.call("set_device_enabled", enabled=action == "enable")
        time.sleep(SETTLE)
    elif action != "list":
        raise ValueError("action must be list, build, remove, bypass or enable")
    bw.call("select_master")
    time.sleep(SETTLE)
    devs = bw.call("list_devices")["devices"]
    detail = []
    for d in devs:
        bw.call("select_device", device_index=d["index"])
        time.sleep(0.2)
        g = bw.call("get_device")
        detail.append({"index": d["index"], "name": d["name"], "enabled": d["enabled"],
                       "controls": {p["name"]: p["display"] for p in g["params"]}})
    return {"master_chain": detail}


@tool()
def master_control(width_pct: float | None = None, limiter_gain_db: float | None = None,
                   ceiling_db: float | None = None, limiter_release_s: float | None = None,
                   output_gain_db: float | None = None, eq_band_gains_db: dict | None = None) -> dict:
    """Set mastering controls by real value (verified from Bitwig's display): stereo width % (Tool
    'St. Width', 100 = unchanged, 0 = mono), limiter input gain dB, limiter ceiling dBTP, limiter
    release s, output gain dB (Tool 'Gain'), and EQ+ band gains {"1": -2.0, "4": 1.5} (bands 1-8).
    Build the chain first with mastering_chain('build')."""
    done = {}
    if width_pct is not None:
        done["width"] = _set_param_display(_master_device("Tool"), "St. Width", width_pct, 0.4)
    if output_gain_db is not None:
        done["output_gain"] = _set_param_display(_master_device("Tool"), "Gain", output_gain_db)
    if limiter_gain_db is not None:
        done["limiter_gain"] = _set_param_display(_master_device("Peak Limiter"), "Gain", limiter_gain_db)
    if ceiling_db is not None:
        done["ceiling"] = _set_param_display(_master_device("Peak Limiter"), "Ceiling", ceiling_db)
    if limiter_release_s is not None:
        done["release"] = _set_param_display(_master_device("Peak Limiter"), "Release", limiter_release_s, 0.02)
    for band, g in (eq_band_gains_db or {}).items():
        done[f"eq_{band}"] = _set_param_display(_master_device("EQ+"), f"{band} Gain", g)
    return {"set": done}


@tool()
def auto_master(target: str = "streaming", seconds: float = 8.0, passes: int = 5, show_image: bool = True) -> list:
    """Live loudness/peak mastering loop: plays nothing itself - start your song first. Builds the chain if
    needed, then measures (live loopback) and adjusts the limiter input gain toward the target LUFS while
    keeping true peak under the target ceiling, repeating up to `passes` times. Returns before/after
    numbers and the final dashboard. Needs live capture (Bitwig on WASAPI)."""
    if not any(d["name"] == "Peak Limiter" for d in mastering_chain("list")["master_chain"]):
        mastering_chain("build", target=target)
    t_lufs, t_tp = mastering.TARGETS.get(target, mastering.TARGETS["streaming"])
    # Each target has its own ceiling; Peak Limiter caps sample peaks, so leave 0.3 dB for inter-sample peaks.
    _set_param_display(_master_device("Peak Limiter"), "Ceiling", t_tp - 0.3)
    history = []
    note = None
    gain = _num(next(c for c in mastering_chain("list")["master_chain"] if c["name"] == "Peak Limiter")["controls"]["Gain"]) or 0.0
    for _ in range(passes):
        x, sr, src = mastering.capture_loopback(seconds)
        m = mastering.analyze(x, sr, target)
        history.append({"limiter_gain_db": gain, "lufs": m["loudness"]["integrated_lufs"],
                        "true_peak": m["peaks"]["true_peak_dbtp"]})
        delta = m["target"]["gain_to_target_db"]
        if abs(delta) < 0.5 and m["peaks"]["true_peak_dbtp"] <= t_tp:
            break
        # Once the limiter works hard, +1 dB in gives less than +1 LU out. Measure that ratio from the
        # previous step and divide by it so later passes land on target.
        efficiency = 1.0
        if len(history) >= 2:
            dg = history[-1]["limiter_gain_db"] - history[-2]["limiter_gain_db"]
            dl = history[-1]["lufs"] - history[-2]["lufs"]
            if dg > 0.3 and dl > 0:
                efficiency = max(0.2, min(1.0, dl / dg))
        if delta > 0 and gain >= 23.9:
            note = (f"Limiter is at its +24 dB maximum and the mix is still {delta} LU short of {t_lufs} LUFS. "
                    "Raise the level going into the master (track faders / a gain stage before the limiter), "
                    "or pick a quieter target.")
            break
        gain = max(0.0, min(24.0, gain + delta / efficiency * (0.8 if len(history) == 1 else 1.0)))
        _set_param_display(_master_device("Peak Limiter"), "Gain", gain)
        if m["peaks"]["true_peak_dbtp"] > t_tp:
            _set_param_display(_master_device("Peak Limiter"), "Ceiling", t_tp - 0.3)
        time.sleep(0.5)
    out = _analysis_reply(x, sr, src, target, show_image)
    out[0] = json.dumps({"passes": history, **({"note": note} if note else {}), "final": json.loads(out[0])}, indent=1)
    return out


# --- Analysis & arrangement helpers ---
def _is_drum_track(t: dict, devices: list) -> bool:
    return any(d["name"] == "Drum Machine" for d in devices) or \
        naming.classify(t["name"])[0] in ("Drums", "Kick", "Snare", "Clap", "Hats", "Perc")


@tool()
def detect_chords(track_index: int, slot: int, resolution: float | None = None) -> dict:
    """Name the chords in a clip (with inversions, e.g. 'C/E'), plus the clip's key and Roman numerals.
    resolution: beats per chord slot (default: per bar, or per half bar when harmony moves faster)."""
    notes, length = _read_clip(track_index, slot)
    if not notes:
        raise RuntimeError("clip is empty")
    key = music.detect_key(notes)[0]
    chords = music.detect_chords(notes, length, resolution)
    for c in chords:
        c["roman"] = music.roman(c["chord"], key["key"], key["scale"])
        c["bar"] = int(c["start"] // 4) + 1
    return {"key": f"{key['key']} {key['scale']}", "confidence": key["confidence"], "chords": chords,
            "progression": " - ".join(c["chord"] or "rest" for c in chords)}


@tool()
def make_variation(track_index: int, slot: int, to_slot: int, kind: str = "mutate", amount: float = 0.3,
                   seed: int | None = None) -> dict:
    """Write a variation of a clip into another slot (for fills, transitions and evolving loops).
    kind: mutate (shift some notes in pitch/time, kept in the clip's key), sparse (drop notes, keep
    downbeats), busy (add ghost notes), fill (last beat becomes a roll), syncopate (push hits a 16th early).
    amount 0..1 = how much changes; change seed for another take."""
    import variations
    notes, length = _read_clip(track_index, slot)
    if not notes:
        raise RuntimeError("source clip is empty")
    k = music.detect_key(notes)[0] if kind == "mutate" else None
    out = variations.variation(notes, length, kind, amount, k and k["key"], k["scale"] if k else "major", seed)
    res = _write(track_index, to_slot, out, length, f"{kind} var")
    return {"from_slot": slot, "to_slot": to_slot, "kind": kind, "notes_before": len(notes),
            "notes_after": len(out), "verified": res["verified"]}


@tool()
def compare_reference(reference: str, mix: str = "live", seconds: float = 20.0, ref_start: float = 30.0,
                      mix_start: float = 0.0, target: str = "streaming", show_image: bool = True) -> list:
    """Compare your track against a reference song: loudness, true peak, dynamics (PLR/LRA), stereo width,
    correlation, energy per band, mid/side per band - with matching suggestions and an overlay chart
    (level-matched tonal balance, side content, band energy, key numbers).
    reference: a WAV path (or sample name). mix: 'live' (capture what's playing; needs WASAPI) or a WAV
    path of your bounce. ref_start/mix_start pick comparable sections (e.g. both choruses)."""
    import reference as refmod
    rpath = reference if os.path.exists(reference) else samples.resolve(reference)
    xb, srb, srcb = mastering.load_file(rpath, ref_start if mastering_len(rpath) > ref_start + 1 else 0, seconds)
    if mix == "live":
        xa, sra, srca = mastering.capture_loopback(seconds)
    else:
        mpath = mix if os.path.exists(mix) else samples.resolve(mix)
        xa, sra, srca = mastering.load_file(mpath, mix_start, seconds)
    ma, mb = mastering.analyze(xa, sra, target), mastering.analyze(xb, srb, target)
    out = [json.dumps({"mix": srca, "reference": srcb, **refmod.compare(ma, mb),
                       "mix_summary": {k: ma[k] for k in ("loudness", "peaks", "dynamics", "stereo")},
                       "reference_summary": {k: mb[k] for k in ("loudness", "peaks", "dynamics", "stereo")}}, indent=1)]
    if show_image:
        out.append(Image(data=refmod.render(xa, sra, ma, xb, srb, mb, srca.split(": ", 1)[-1][:30],
                                            srcb.split(": ", 1)[-1][:30]), format="png"))
    return out


def mastering_len(path: str) -> float:
    try:
        sr, data = mastering.wavfile.read(path, mmap=True)
        return len(data) / sr
    except Exception:
        return 0.0


@tool()
def project_report(analyze_clips: bool = True, max_clips: int = 24) -> dict:
    """One-call overview of the whole project: tempo, transport, every track (type, devices and presets,
    fader/pan/mute/solo, sends, clips) and - with analyze_clips - each MIDI clip's note count, key and
    chords, plus an overall project key estimate and a mixer summary. Restores your track selection."""
    session = bw.call("get_session", with_clips=True)
    original = session["selected_track"]["index"]
    tracks, all_notes, analyzed = [], [], 0
    for t in session["tracks"]:
        bw.call("select_track", track_index=t["index"])
        time.sleep(0.2)
        devices = bw.call("list_devices")["devices"]
        entry = {"index": t["index"], "name": t["name"], "type": t["type"], "fader": t["volume_display"],
                 "pan": t["pan_display"], "mute": t["mute"], "solo": t["solo"],
                 "devices": [d["name"] + (f" ({d['preset']})" if d.get("preset") and d["preset"] != "init" else "")
                             for d in devices],
                 "sends": {s_["name"]: s_["display"] for s_ in t["sends"] if s_["value"] > 0},
                 "clips": []}
        drum = _is_drum_track(t, devices)
        for c in t.get("clips", []):
            info = {"slot": c["slot"], "name": c["name"]}
            if analyze_clips and t["type"] != "Audio" and analyzed < max_clips:
                notes, length = _read_clip(t["index"], c["slot"])
                analyzed += 1
                info.update(notes=len(notes), length_beats=length)
                if notes and not drum:
                    k = music.detect_key(notes)[0]
                    info["key"] = f"{k['key']} {k['scale']}"
                    info["chords"] = " - ".join(x["chord"] or "rest" for x in music.detect_chords(notes, length))[:120]
                    all_notes += notes
            entry["clips"].append(info)
        entry["role"] = "drums" if drum else (naming.classify(t["name"])[0] or "").lower() or None
        tracks.append(entry)
    if original is not None and original >= 0:
        bw.call("select_track", track_index=original)
    project_key = music.detect_key(all_notes)[0] if all_notes else None
    return {"tempo": session["tempo"], "playing": session["playing"],
            "project_key": f"{project_key['key']} {project_key['scale']}" if project_key else None,
            "scenes": [s_["name"] for s_ in session["scenes"]], "track_count": len(tracks),
            "muted": [t["name"] for t in tracks if t["mute"]], "soloed": [t["name"] for t in tracks if t["solo"]],
            "clips_analyzed": analyzed, "tracks": tracks}


@tool()
def transpose_project(semitones: int, include_drums: bool = False, track_indices: list[int] | None = None) -> dict:
    """Transpose every MIDI clip in the project (or the given tracks) by semitones, keeping all per-note
    expressions. Drum tracks (Drum Machine or drum-named) are skipped unless include_drums - transposing
    drums would swap kit pieces."""
    session = bw.call("get_session", with_clips=True)
    original = session["selected_track"]["index"]
    done, skipped = [], []
    for t in session["tracks"]:
        if track_indices is not None and t["index"] not in track_indices:
            continue
        if t["type"] == "Audio" or not t.get("clips"):
            continue
        bw.call("select_track", track_index=t["index"])
        time.sleep(0.2)
        if not include_drums and _is_drum_track(t, bw.call("list_devices")["devices"]):
            skipped.append(t["name"])
            continue
        for c in t["clips"]:
            r = transform_notes(t["index"], c["slot"], "transpose", semitones=semitones)
            done.append({"track": t["name"], "slot": c["slot"], "notes": r["notes"]})
    if original is not None and original >= 0:
        bw.call("select_track", track_index=original)
    return {"semitones": semitones, "clips_transposed": len(done), "skipped_drum_tracks": skipped, "clips": done}


@tool()
def suggest_samples(category: str | None = None, query: str = "", kind: str = "loop", limit: int = 10,
                    match_key: bool = True) -> dict:
    """Samples that fit the current project: matches the project tempo (incl. half/double time) and,
    with match_key, the key detected from your MIDI clips (relative major/minor also accepted).
    category as in search_samples (drum loop, vocal, bass, synth, ...)."""
    tempo = bw.call("get_session")["tempo"]
    key = None
    if match_key:
        notes = []
        for t in bw.call("get_session", with_clips=True)["tracks"]:
            if t["type"] != "Audio" and t.get("clips") and naming.classify(t["name"])[0] not in ("Drums", "Kick", "Hats", "Snare", "Perc"):
                notes += _read_clip(t["index"], t["clips"][0]["slot"])[0]
            if len(notes) > 400:
                break
        if notes:
            k = music.detect_key(notes)[0]
            key = k["key"] + ("m" if k["scale"] == "minor" else "")
    keys = None
    if key:
        pc = music.parse_key(key.rstrip("m"))
        rel = (pc + 3) % 12 if key.endswith("m") else (pc - 3) % 12  # relative major/minor
        names = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
        alt = {"C#": "Db", "Eb": "D#", "F#": "Gb", "Ab": "G#", "Bb": "A#"}
        k1 = names[pc] + ("m" if key.endswith("m") else "")
        k2 = names[rel] + ("" if key.endswith("m") else "m")
        keys = {k.lower() for k in (k1, k2, alt.get(k1.rstrip("m"), "") + ("m" if k1.endswith("m") else ""),
                                     alt.get(k2.rstrip("m"), "") + ("m" if k2.endswith("m") else ""))}
    hits = samples.search(query, category, kind, tempo, 3, None, None, 500)
    if keys:
        keyed = [h for h in hits if h["key"] and h["key"].lower() in keys]
        unkeyed = [h for h in hits if not h["key"]]  # drums etc. have no key - still usable
        hits = keyed + unkeyed
    return {"project_tempo": tempo, "project_key": key, "count": len(hits[:limit]),
            "samples": [{"name": h["name"], "pack": h["pack"], "category": h["category"], "bpm": h["bpm"],
                         "key": h["key"], "path": h["path"]} for h in hits[:limit]]}


# --- Pitch & tuning ---
@tool()
def check_tuning(source: str = "live", seconds: float = 8.0, start: float = 0.0, mode: str = "auto",
                 threshold_cents: float = 25.0, show_image: bool = True) -> list:
    """Pitch and tuning check, shown in chat. Single-note material (vocal, lead, bass, solo instrument) gets a
    per-note report: each note's name and cents sharp/flat, vibrato width, worst offenders and advice. Chords and
    full mixes get the overall tuning offset against A=440 (and the implied A4 frequency) plus a key estimate.
    source: 'live' (what Bitwig is playing now; needs a WASAPI driver, press play first) or a WAV path / sample
    name (start/seconds pick a section; seconds=0 = whole file). mode: auto, mono, poly.
    threshold_cents: how far off counts as out of tune (25 is audible to most ears)."""
    import pitch
    if source == "live":
        if seconds <= 0:
            raise ValueError("seconds must be > 0 for live capture")
        x, sr, src = mastering.capture_loopback(seconds)
    else:
        path = source if os.path.exists(source) else samples.resolve(source)
        x, sr, src = mastering.load_file(path, start, seconds or None)
    res = pitch.analyze(x, sr, mode, threshold_cents)
    res["source"] = src
    image = pitch.render(res, f"Pitch & tuning - {src}") if show_image else None
    res.pop("_track")
    if len(res.get("notes", [])) > 60:  # keep the text reply compact; the summary already covers the rest
        res["notes_truncated_to"] = 60
        res["notes"] = res["notes"][:60]
    out = [json.dumps(res, indent=1, ensure_ascii=False)]
    if image:
        out.append(Image(data=image, format="png"))
    return out


# --- Arrangement recording ---
@tool()
def record_arrangement(action: str = "start", scenes: list | None = None, bars: int = 4,
                       wait: bool | None = None) -> dict:
    """Turn launcher scenes into a real arrangement. Bitwig's API can't place arranger clips directly, so
    this records them: it starts arranger record and launches each scene on the bar, stopping tracks that
    have no clip in that scene (so a breakdown really drops the drums). Timing runs inside Bitwig.
    action: start, status, abort.
    scenes: scene numbers in song order, repeats allowed ([0, 1, 2, 3, 3, 4, 5, 6]), or dicts
    {"scene": 3, "bars": 8}; default = every scene that contains clips, in order. bars = bars per scene
    (sketch_song clips are 4 bars). The playhead restarts at 0 and the song plays out loud in real time;
    existing arranger content on the recorded tracks is overwritten. wait: block until finished (default:
    only when it takes under ~40 s; otherwise poll with action='status')."""
    if action == "status":
        return bw.call("arranger_status")
    if action == "abort":
        bw.call("arranger_abort")
        return bw.call("arranger_status")
    if action != "start":
        raise ValueError("action must be start, status or abort")
    session = bw.call("get_session", with_clips=True)
    filled = {c["slot"] for t in session["tracks"] for c in t.get("clips", [])}
    if scenes is None:
        scenes = sorted(filled)
    if not scenes:
        raise RuntimeError("no scenes contain clips - build something first (e.g. sketch_song)")
    items = [{"scene": x, "bars": bars} if isinstance(x, int) else {"scene": int(x["scene"]), "bars": int(x.get("bars", bars))}
             for x in scenes]
    empty = [i["scene"] for i in items if i["scene"] not in filled]
    if empty:
        raise ValueError(f"scenes {sorted(set(empty))} have no clips")
    names = {s["index"]: s["name"] for s in session["scenes"]}
    plan, beat = [], 0
    for i in items:
        plan.append({"scene": i["scene"], "start": beat})
        beat += i["bars"] * 4
    seconds = beat / session["tempo"] * 60
    bw.call("arranger_start", plan=plan, total_beats=beat)
    out = {"sections": [{"scene": i["scene"], "name": names.get(i["scene"]), "bars": i["bars"], "start_bar": p["start"] // 4 + 1}
                        for i, p in zip(items, plan)],
           "total_bars": beat // 4, "duration_s": round(seconds), "tempo": session["tempo"]}
    if wait is None:
        wait = seconds <= 40
    if not wait:
        return {**out, "state": "recording", "next": "poll record_arrangement(action='status') until phase is 'done'"}
    deadline = time.time() + seconds * 1.3 + 15
    while time.time() < deadline:
        time.sleep(0.5)
        st = bw.call("arranger_status")
        if not st["running"]:
            break
    else:
        bw.call("arranger_abort")
        raise RuntimeError("recording did not finish in time and was aborted")
    st = bw.call("arranger_status")
    if st["phase"] != "done":
        raise RuntimeError(f"recording ended early: {st['phase']} {st.get('error') or ''}")
    late = [x for x in st["launched"] if x["at_position"] > x["start_beat"] + 0.05]
    return {**out, "state": "done", "launches": len(st["launched"]) + 1, "late_launches": late,
            "note": "Recorded into the arranger. Open Bitwig's Arrange view to see the clips."}


# --- Live monitor web dashboard ---
MONITOR_PORT = 8780


def _monitor_get(path: str, method: str = "GET", timeout: float = 2.0):
    import urllib.request
    req = urllib.request.Request(f"http://127.0.0.1:{MONITOR_PORT}{path}", method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


@tool()
def live_monitor(action: str = "start", target: str = "streaming", open_browser: bool = True) -> dict:
    """Real-time mastering dashboard in your web browser at http://127.0.0.1:8780 - momentary / short-term
    / integrated LUFS, distance to target, true-peak hold, LRA, PLR, L/R and mid/side meters, phase
    correlation, stereo width, vectorscope, mid/side spectrum and a 60 s loudness graph, updating ~10x/s.
    The page also has a pitch tuner, master-chain sliders, advice, a UK time and weather header, and
    closable panels (Panels menu; layout remembered in the browser). It can start at Windows login
    (python autostart.py).
    action: start (launches it in the background if not running, sets the target, opens the browser),
    reading (current numbers, so Claude can comment on what you're hearing), reset (restart integrated
    loudness / peak hold for a new pass), target (switch target), stop.
    Needs Bitwig on a WASAPI ('Windows Audio') driver."""
    import subprocess
    import webbrowser
    url = f"http://127.0.0.1:{MONITOR_PORT}"

    def running():
        try:
            return _monitor_get("/api/latest", timeout=1)
        except Exception:
            return None

    if action == "start":
        if not running():
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
            subprocess.Popen([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_monitor.py"),
                              "--port", str(MONITOR_PORT), "--target", target],
                             creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             stdin=subprocess.DEVNULL, close_fds=True)
            for _ in range(30):
                time.sleep(0.2)
                if running():
                    break
            else:
                raise RuntimeError("monitor did not start (is port 8780 in use?)")
        else:
            _monitor_get(f"/api/target/{target}", "POST")
        if open_browser:
            webbrowser.open(url)
        time.sleep(0.5)
        r = running() or {}
        return {"url": url, "status": r.get("status"), "device": r.get("device"), "target": target}
    if action == "reading":
        r = running()
        if not r:
            raise RuntimeError("live monitor is not running - use live_monitor('start')")
        r.pop("scope", None)
        sp = r.pop("spectrum", None)
        if sp:  # compact spectrum summary instead of 60 bands x 2
            r["spectrum_summary_db"] = {name: {lbl: round(float(np.mean([v for f, v in zip(sp["freqs"], sp[name]) if lo <= f < hi])), 1)
                                               for lbl, lo, hi in mastering.BANDS}
                                        for name in ("mid", "side")}
        r.pop("history", None)
        return r
    if action == "reset":
        return _monitor_get("/api/reset", "POST")
    if action == "target":
        return _monitor_get(f"/api/target/{target}", "POST")
    if action == "stop":
        if not running():
            return {"stopped": False, "note": "not running"}
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              f"Get-NetTCPConnection -LocalPort {MONITOR_PORT} -State Listen -ErrorAction SilentlyContinue | "
                              "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"], capture_output=True, text=True)
        time.sleep(0.5)
        return {"stopped": running() is None, "detail": out.stderr.strip()[:200] or None}
    raise ValueError("action must be start, reading, reset, target or stop")


# --- Auto naming ---
AUTO_NAME_ON_LOAD = True  # rename default-named tracks ("Inst 3", "Audio 2") when something is loaded


def _track_profile(t: dict, analyze_notes: bool):
    bw.call("select_track", track_index=t["index"])
    time.sleep(0.2)
    devices = bw.call("list_devices")["devices"]
    clips = bw.call("get_track", track_index=t["index"])["clips"]
    notes = None
    if analyze_notes and not any(d.get("preset") for d in devices) and clips and t["type"] != "Audio":
        notes, _ = _read_clip(t["index"], clips[0]["slot"])
    return devices, clips, notes


@tool()
def auto_name_tracks(track_indices: list[int] | None = None, style: str = "smart", only_default_names: bool = False,
                     color: bool = True, analyze_notes: bool = True, dry_run: bool = False) -> dict:
    """Rename tracks from what's on them: the loaded preset/instrument, sample or clip names, or (for bare
    MIDI tracks) the notes themselves (drums vs bass vs chords vs lead). style: smart ('Bass - Rippin'
    Bass'), role ('Bass'), source ('Rippin' Bass'). color=True also colours by role. only_default_names
    leaves tracks you've already named alone. dry_run shows the plan without renaming. Duplicate names get
    numbered. Restores your track selection afterwards."""
    session = bw.call("get_session")
    original = session["selected_track"]["index"]
    tracks = [t for t in session["tracks"] if track_indices is None or t["index"] in track_indices]
    plans = []
    for t in tracks:
        if only_default_names and not naming.is_default(t["name"]):
            plans.append({"index": t["index"], "old": t["name"], "new": None, "reason": "already named"})
            continue
        devices, clips, notes = _track_profile(t, analyze_notes)
        name, col, reason = naming.suggest(t, devices, clips, notes, style)
        plans.append({"index": t["index"], "old": t["name"], "new": name, "color": col, "reason": reason})
    for p, n in zip(plans, naming.dedupe([p["new"] for p in plans])):
        p["new"] = n
    if not dry_run:
        cmds = []
        for p in plans:
            if p["new"] and p["new"] != p["old"]:
                cmds.append(("set_track_name", {"track_index": p["index"], "name": p["new"]}))
            if color and p["new"] and p.get("color"):
                r, g, b = _hex_to_rgb(p["color"])
                cmds.append(("set_track_color", {"track_index": p["index"], "r": r, "g": g, "b": b}))
        if cmds:
            bw.batch(cmds)
            time.sleep(SETTLE)
    if original is not None and original >= 0:
        bw.call("select_track", track_index=original)
    return {"dry_run": dry_run, "renamed": sum(1 for p in plans if p["new"] and p["new"] != p["old"]),
            "tracks": plans}


def _auto_name_one(track_index: int, loaded_path: str | None = None):
    """Called after loading a sound: rename only if the track still has a default name. Bitwig itself
    renames a default track to the preset's name on load, so that counts as default too."""
    if not AUTO_NAME_ON_LOAD or track_index is None or track_index < 0:  # master/unknown: leave alone
        return None
    t = bw.call("get_track", track_index=track_index)
    stem = os.path.splitext(os.path.basename(loaded_path))[0] if loaded_path else None
    if not (naming.is_default(t["name"]) or (stem and t["name"] == stem)):
        return None
    r = auto_name_tracks([track_index], analyze_notes=False)
    return r["tracks"][0]["new"]



# --- Deep device access: nested chains, every parameter, mid/side EQ (needs controller script 6.0+) ---
import deepdev

deep = deepdev.Deep(bw)


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
                  where: str = "end") -> dict:
    """Insert a device (name like 'EQ+' or a file path) on a track (-1 = master). Top level: where = end, start or
    before (needs device_index). Inside a nested chain: slot = 'Mid'/'Side' and device_index = the top-level
    Mid-Side Split; the device goes to the end of that slot. Returns the tree afterwards."""
    deep.insert(track_index, device, slot, where, device_index)
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


import audit
import recipes

AB_KEYS = [("loudness", "integrated_lufs"), ("loudness", "short_term_max_lufs"), ("peaks", "true_peak_dbtp"),
           ("dynamics", "crest_factor_db"), ("dynamics", "plr_db"), ("stereo", "width_pct"),
           ("stereo", "correlation"), ("stereo", "side_vs_mid_db")]


@tool()
def mix_audit(track_indices: list[int] | None = None, fix: bool = False, include_master: bool = True) -> dict:
    """Walk the project (all tracks, or track_indices) and report every device with its real state (EQ+ bands in
    Hz/dB/Q), flagging problems: EQ+ bands that have a gain but type Off (they do nothing), EQ+ that is entirely
    flat or Off, bypassed devices, several compressors stacked on one track, duplicate devices. fix=True applies
    the safe repairs only: gives gain-but-Off EQ bands a sensible type (shelf at the ends, bell between) and
    re-enables bypassed devices. Nothing is ever deleted. Takes about a second per device."""
    return audit.run(deep, track_indices, fix, include_master)


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
        x, sr, _ = mastering.capture_loopback(seconds)
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

if __name__ == "__main__":
    mcp.run()
