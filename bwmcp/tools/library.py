"""Samples and bookmarks."""
import os
import time

from bwmcp.core.bridge import bw, tool
from bwmcp.core.util import _read_clip, _resolve_sound
from bwmcp.devices import presets
from bwmcp.library import bookmarks, samples
from bwmcp.music import music, naming
from bwmcp.tools.presets import _auto_name_one, load_preset
from bwmcp.tools.tracks import create_track


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
