"""Standard MIDI File read/write (pure Python) + Bitwig clip import/export helpers.
Times are in BEATS (quarter notes). Note start/duration in beats are tempo independent (ticks / ticks_per_beat);
the tempo map is reported separately."""
import math
import os
import struct

PPQ = 480


def _vlq(data, i):
    v = 0
    while True:
        b = data[i]
        i += 1
        v = (v << 7) | (b & 0x7F)
        if not b & 0x80:
            return v, i


def _enc_vlq(v):
    out = [v & 0x7F]
    v >>= 7
    while v:
        out.append((v & 0x7F) | 0x80)
        v >>= 7
    return bytes(reversed(out))


def read_midi(path):
    """-> {"format","ticks_per_beat","tempos":[{beat,bpm}],"time_signatures":[{beat,num,den}],
    "tracks":[{"name","index","notes":[{pitch,start,duration,velocity,channel(1-16),drum}]}], "length_beats"}"""
    data = open(path, "rb").read()
    if data[:4] != b"MThd":
        raise ValueError("not a MIDI file (no MThd)")
    hlen = struct.unpack(">I", data[4:8])[0]
    fmt, ntrk, div = struct.unpack(">HHH", data[8:14])
    if div & 0x8000:
        raise ValueError("SMPTE time division not supported")
    tpb = div
    pos = 8 + hlen
    tempos, sigs, tracks = [], [], []
    end_tick = 0
    while pos + 8 <= len(data):
        cid, clen = data[pos:pos + 4], struct.unpack(">I", data[pos + 4:pos + 8])[0]
        body = data[pos + 8:pos + 8 + clen]
        pos += 8 + clen
        if cid != b"MTrk":
            continue
        i, tick, status, name = 0, 0, 0, ""
        active = {}
        notes = []
        try:
            while i < len(body):
                dt, i = _vlq(body, i)
                tick += dt
                b = body[i]
                if b == 0xFF:
                    typ = body[i + 1]
                    ln, j = _vlq(body, i + 2)
                    payload = body[j:j + ln]
                    i = j + ln
                    if typ == 0x51 and ln == 3:
                        tempos.append((tick, 60e6 / int.from_bytes(payload, "big")))
                    elif typ == 0x58 and ln >= 2:
                        sigs.append((tick, payload[0], 2 ** payload[1]))
                    elif typ == 0x03 and not name:
                        name = payload.decode("latin-1", "replace")
                    elif typ == 0x2F:
                        break
                    continue
                if b in (0xF0, 0xF7):
                    ln, j = _vlq(body, i + 1)
                    i = j + ln
                    continue
                if b & 0x80:
                    status = b
                    i += 1
                kind, ch = status & 0xF0, status & 0x0F
                if kind in (0xC0, 0xD0):
                    i += 1
                    continue
                d1, d2 = body[i], body[i + 1]
                i += 2
                if kind == 0x90 and d2 > 0:
                    active.setdefault((ch, d1), []).append((tick, d2))
                elif kind == 0x80 or (kind == 0x90 and d2 == 0):
                    q = active.get((ch, d1))
                    if q:
                        st, vel = q.pop(0)
                        notes.append((st, tick - st, d1, vel, ch))
        except IndexError:
            pass  # truncated track: keep what we have
        for (ch, p), q in active.items():
            for st, vel in q:
                notes.append((st, max(1, tick - st), p, vel, ch))
        end_tick = max(end_tick, tick)
        notes.sort()
        tracks.append({"name": name, "index": len(tracks), "notes": [
            {"pitch": p, "start": st / tpb, "duration": d / tpb, "velocity": v, "channel": ch + 1,
             "drum": ch == 9} for st, d, p, v, ch in notes]})
    tempos.sort()
    return {"format": fmt, "ticks_per_beat": tpb,
            "tempos": [{"beat": t / tpb, "bpm": round(b, 3)} for t, b in tempos] or [{"beat": 0.0, "bpm": 120.0}],
            "time_signatures": [{"beat": t / tpb, "num": n, "den": d} for t, n, d in sigs] or
                               [{"beat": 0.0, "num": 4, "den": 4}],
            "tracks": tracks, "length_beats": end_tick / tpb}


def write_midi(path, notes_by_track, tempo=120.0, time_signature=(4, 4), names=None, ppq=PPQ):
    """notes_by_track: list of note lists (or dict name->list). Notes {pitch,start,duration,velocity[,channel 1-16]}.
    Writes format 1: a conductor track (tempo, time signature) + one track per list."""
    if isinstance(notes_by_track, dict):
        names = list(notes_by_track)
        notes_by_track = list(notes_by_track.values())
    num, den = time_signature
    trks = []
    mt = bytearray()
    mt += b"\x00\xFF\x51\x03" + int(round(60e6 / tempo)).to_bytes(3, "big")
    mt += b"\x00\xFF\x58\x04" + bytes([num, int(math.log2(den)), 24, 8])
    mt += b"\x00\xFF\x2F\x00"
    trks.append(bytes(mt))
    for ti, notes in enumerate(notes_by_track):
        ev = []
        for n in notes:
            ch = (int(n.get("channel", 1)) - 1) & 15
            s = int(round(n["start"] * ppq))
            e = max(s + 1, int(round((n["start"] + n["duration"]) * ppq)))
            vel = max(1, min(127, int(n.get("velocity", 100))))
            ev.append((s, 1, 0x90 | ch, int(n["pitch"]) & 127, vel))
            ev.append((e, 0, 0x80 | ch, int(n["pitch"]) & 127, 0))  # offs sort before ons at the same tick
        ev.sort()
        t = bytearray()
        nm = (names[ti] if names and ti < len(names) else f"Track {ti + 1}").encode("latin-1", "replace")
        t += b"\x00\xFF\x03" + _enc_vlq(len(nm)) + nm
        last = 0
        for tick, _, st, a, b in ev:
            t += _enc_vlq(tick - last) + bytes([st, a, b])
            last = tick
        t += b"\x00\xFF\x2F\x00"
        trks.append(bytes(t))
    out = b"MThd" + struct.pack(">IHHH", 6, 1, len(trks), ppq)
    for t in trks:
        out += b"MTrk" + struct.pack(">I", len(t)) + t
    with open(path, "wb") as f:
        f.write(out)
    return path


# ---------------- Bitwig helpers (need `server` importable; call inside bwlock.hold) ----------------
def _select(mid, track):
    ts = [t for t in mid["tracks"] if t["notes"]]
    if track == "all":
        return sorted([n for t in ts for n in t["notes"]], key=lambda n: n["start"])
    if isinstance(track, str) and track.startswith("ch"):
        ch = int(track[2:])
        return sorted([n for t in ts for n in t["notes"] if n["channel"] == ch], key=lambda n: n["start"])
    return ts[track]["notes"]


def import_midi(path, track_index, slot, track=0, name=None, beats_per_bar=None):
    """Write a .mid track into a launcher clip. track: index among non-empty tracks, 'all', or 'ch10' etc."""
    import server
    mid = read_midi(path)
    notes = _select(mid, track)
    if not notes:
        raise ValueError("no notes in selection")
    bpb = beats_per_bar or mid["time_signatures"][0]["num"] * 4 / mid["time_signatures"][0]["den"]
    end = max(n["start"] + n["duration"] for n in notes)
    length = max(1, math.ceil(end / bpb - 1e-6)) * bpb
    core = [{k: n[k] for k in ("pitch", "start", "duration", "velocity")} for n in notes]
    nm = name or os.path.splitext(os.path.basename(path))[0]
    r = server.write_notes(track_index, slot, core, length, nm)
    r.update({"midi_tempo": mid["tempos"][0]["bpm"], "tempo_changes": len(mid["tempos"]) - 1})
    return r


def read_clip_settled(track_index, slot, expect=None, tries=8, delay=1.5):
    """Bitwig applies write_clip asynchronously: a read right after a write can return 0 notes (observed live).
    Poll until the note count is non-zero, equals `expect` (if given) and is unchanged between two reads."""
    import time

    import server
    last = -1
    for _ in range(tries):
        time.sleep(delay)
        try:
            clip = server.get_clip_notes(track_index, slot)
        except Exception:
            continue
        c = clip["count"]
        if c and c == last and (expect is None or c == expect):
            return clip
        last = c
    return clip


def export_clip_midi(track_index, slot, path):
    import server
    clip = read_clip_settled(track_index, slot)
    tr = server.get_transport()
    bpm = tr.get("tempo") or tr.get("bpm") or 120.0
    notes = [{k: n[k] for k in ("pitch", "start", "duration", "velocity")} for n in clip["notes"]]
    write_midi(path, [notes], tempo=bpm, names=[f"clip {track_index}/{slot}"])
    return {"path": path, "notes": len(notes), "length_beats": clip["length_beats"], "tempo": bpm}
