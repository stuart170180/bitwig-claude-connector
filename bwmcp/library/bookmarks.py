"""Bookmarks: a personal, tagged list of favourite presets, devices, samples and sample folders."""
import json
import os
import time

from bwmcp.core import paths

FILE = paths.DATA / "bookmarks.json"


def _load():
    if FILE.exists():
        return json.loads(FILE.read_text(encoding="utf-8"))
    return []


def _save(items):
    FILE.write_text(json.dumps(items, indent=1), encoding="utf-8")


def kind_of(path: str) -> str:
    if os.path.isdir(path):
        return "folder"
    ext = os.path.splitext(path)[1].lower()
    return {".bwdevice": "device", ".bwpreset": "preset"}.get(ext, "sample")


def add(path: str, label: str | None = None, tags: list[str] | None = None, note: str = ""):
    items = _load()
    label = label or os.path.splitext(os.path.basename(path.rstrip("\\/")))[0]
    existing = next((b for b in items if b["path"] == path), None)
    if existing:  # re-bookmarking merges tags and updates label/note
        existing["tags"] = sorted(set(existing["tags"]) | set(tags or []))
        existing["label"] = label
        if note:
            existing["note"] = note
        _save(items)
        return existing
    if any(b["label"].lower() == label.lower() for b in items):
        label = f"{label} ({len(items) + 1})"
    b = {"label": label, "kind": kind_of(path), "path": path, "tags": sorted(set(tags or [])),
         "note": note, "added": time.strftime("%Y-%m-%d %H:%M")}
    items.append(b)
    _save(items)
    return b


def find(label: str):
    items = _load()
    low = label.lower()
    hit = next((b for b in items if b["label"].lower() == low), None) or \
        next((b for b in items if low in b["label"].lower()), None)
    if not hit:
        raise ValueError(f"no bookmark matching {label!r}")
    return hit


def remove(label: str):
    hit = find(label)
    _save([b for b in _load() if b["path"] != hit["path"]])
    return hit


def listing(tag: str | None = None, kind: str | None = None, query: str | None = None):
    out = []
    for b in _load():
        if tag and tag.lower() not in (t.lower() for t in b["tags"]):
            continue
        if kind and b["kind"] != kind:
            continue
        if query and query.lower() not in (b["label"] + " " + " ".join(b["tags"]) + " " + b["note"]).lower():
            continue
        out.append({**b, "missing": not os.path.exists(b["path"])})
    return out


def tag(label: str, add_tags: list[str] | None = None, remove_tags: list[str] | None = None, note: str | None = None):
    items = _load()
    hit = find(label)
    for b in items:
        if b["path"] == hit["path"]:
            b["tags"] = sorted((set(b["tags"]) | set(add_tags or [])) - set(remove_tags or []))
            if note is not None:
                b["note"] = note
            hit = b
    _save(items)
    return hit
