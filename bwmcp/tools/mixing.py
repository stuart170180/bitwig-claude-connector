"""Mixing and mastering: levels, gain staging, mastering chain, analysis, references, masking, mix audit, sidechain, live monitor."""
import json
import os
import sys
import time

import numpy as np
from mcp.server.mcpserver import Image

from bwmcp.analysis import audit, capture, masking, mastering, reflib
from bwmcp.core import paths
from bwmcp.core.bridge import SETTLE, bw, deep, tool
from bwmcp.core.util import _is_drum_track, _num, _parse_db, _read_clip, _set_volume_db, mastering_len
from bwmcp.devices import compdev, genres, presets
from bwmcp.library import samples
from bwmcp.music import music, naming
from bwmcp.tools import uitools
from bwmcp.tools.tracks import create_track


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


# --- Mastering & analysis ---
CHAINS = {  # device order on the master bus
    "streaming": ["EQ+", "Compressor+", "Tool", "Peak Limiter"],
    "club": ["EQ+", "Compressor+", "Saturator", "Tool", "Peak Limiter"],
    "gentle": ["EQ+", "Tool", "Peak Limiter"],
}


CHAIN_ROLES = {"eq": "EQ+", "compressor": "Compressor+", "width": "Tool", "limiter": "Peak Limiter",
               "saturator": "Saturator"}


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
    source='live' records what's playing right now: through Bitwig's own master recorder (any audio driver,
    exact timing; play your song first), falling back to Windows loopback if that is unavailable. source=<wav path> analyzes an
    exported bounce or recording (start/seconds pick a section; seconds=0 = whole file)."""
    if source == "live":
        if seconds <= 0:
            raise ValueError("seconds must be > 0 for live capture")
        try:
            x, sr, src = capture.capture_live(seconds)
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
        x, sr, src = capture.capture_live(seconds)
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


@tool()
def compare_reference(reference: str, mix: str = "live", seconds: float = 20.0, ref_start: float = 30.0,
                      mix_start: float = 0.0, target: str = "streaming", show_image: bool = True) -> list:
    """Compare your track against a reference song: loudness, true peak, dynamics (PLR/LRA), stereo width,
    correlation, energy per band, mid/side per band - with matching suggestions and an overlay chart
    (level-matched tonal balance, side content, band energy, key numbers).
    reference: a WAV path (or sample name). mix: 'live' (capture what's playing; needs WASAPI) or a WAV
    path of your bounce. ref_start/mix_start pick comparable sections (e.g. both choruses)."""
    from bwmcp.analysis import reference as refmod
    rpath = reference if os.path.exists(reference) else samples.resolve(reference)
    xb, srb, srcb = mastering.load_file(rpath, ref_start if mastering_len(rpath) > ref_start + 1 else 0, seconds)
    if mix == "live":
        xa, sra, srca = capture.capture_live(seconds)
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
    from bwmcp.music import pitch
    if source == "live":
        if seconds <= 0:
            raise ValueError("seconds must be > 0 for live capture")
        x, sr, src = capture.capture_live(seconds)
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
            subprocess.Popen([sys.executable, "-m", "bwmcp.monitor.live_monitor", "--port", str(MONITOR_PORT), "--target", target],
                             cwd=str(paths.ROOT), creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
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


@tool()
def mix_audit(track_indices: list[int] | None = None, fix: bool = False, include_master: bool = True) -> dict:
    """Walk the project (all tracks, or track_indices) and report every device with its real state (EQ+ bands in
    Hz/dB/Q), flagging problems: EQ+ bands that have a gain but type Off (they do nothing), EQ+ that is entirely
    flat or Off, bypassed devices, several compressors stacked on one track, duplicate devices. fix=True applies
    the safe repairs only: gives gain-but-Off EQ bands a sensible type (shelf at the ends, bell between) and
    re-enables bypassed devices. Nothing is ever deleted. Takes about a second per device."""
    return audit.run(deep, track_indices, fix, include_master)


@tool()
def add_reference(path: str, label: str, start: float = 0.0, seconds: float = 120.0, note: str = "") -> dict:
    """Analyse a reference track (WAV or AIFF; convert MP3/FLAC first) and store it in the reference library under a
    label: loudness, true peak, crest, loudness range, width, mid/side bands and a 1/3-octave tonal balance."""
    return reflib.add_reference(path, label, start, seconds, note)


@tool()
def list_references() -> list:
    """The stored reference tracks with their headline numbers."""
    return reflib.list_references()


@tool()
def remove_reference(label: str) -> dict:
    """Delete a stored reference."""
    return {"removed": reflib.remove_reference(label)}


@tool()
def reference_target(labels: list[str] | None = None) -> dict:
    """Averaged tonal balance and headline numbers of several references (default: all stored): a target to mix toward."""
    return reflib.target_curve(labels)


@tool()
def compare_to_library(label: str, source: str = "live", seconds: float = 20.0, start: float = 0.0) -> dict:
    """Compare a mix to a stored reference (or several: comma-separated labels, averaged). source = 'live' (what is
    playing, needs WASAPI capture) or a WAV/AIFF path. Returns loudness, crest, width and per-band tonal differences
    (mix minus reference) with plain advice. Use full songs as references: single loops give extreme differences."""
    return reflib.compare_to_reference(label, source, seconds, start)


@tool()
def masking_report(track_indices: list[int] | None = None, seconds: float = 5.0) -> dict:
    """Find frequency clashes between tracks: solos each track in turn while the song plays (audible!), captures it, and
    scores where two tracks both carry energy in the same band. Returns ranked findings and the EQ cut it would make.
    Playback must be running. Use a capture of at least one loop length. About 'seconds' + 0.4 s per track."""
    rep = masking.report(track_indices, seconds)
    rep.pop("_spectra", None)
    return {"summary": masking.format_report(rep), **{k: v for k, v in rep.items() if k != "spectra"}}


@tool()
def masking_fix(track_indices: list[int] | None = None, seconds: float = 5.0, max_fixes: int = 2,
                min_score: float = 0.5) -> dict:
    """Run masking_report, then apply the proposed EQ cuts for the worst clashes (inserting EQ+ where needed, one band
    each) and re-measure. Returns what was cut and the clash score before and after; the 'after' number can be noisy
    if the capture doesn't cover a full loop."""
    rep = masking.report(track_indices, seconds)
    res = masking.apply(rep, max_fixes, min_score)
    if res.get("after_report"):
        res["after_report"].pop("_spectra", None)
        res["after_report"].pop("spectra", None)
    return res


@tool()
def sidechain_setup(source_tracks: list[int], target_tracks: list[int], bus_name: str = "SC Kick",
                    genre: str = "house", depth: str = "medium", send_level: float = 0.79,
                    use_send_index: int | None = None, ui: bool = True) -> dict:
    """Complete sidechain: one FX bus track that carries only the trigger signal, fed from source_tracks (e.g. the kick) through
    their sends, and a Compressor+ with ducking settings for the genre on every target track (bass, pads, strings ...).
    genre: house, deep_house, techno, trance, progressive, big_room, dubstep, dnb, hiphop, trap, pop, edm_pop, disco_funk, reggaeton, rock,
    lofi, ambient (see sidechain_genres). The release follows the project tempo, so it works at any bpm. depth: light, medium or heavy.
    ui=True also does what the API cannot, by driving Bitwig's screen (see sidechain_source and rename_fx_track): the FX track is renamed
    to bus_name and each compressor's sidechain source is set to it (pre-fader tap). Bitwig must be on screen for that; any step that fails is
    reported under `ui` and left in `todo`. use_send_index reuses an existing FX track instead of creating one."""
    tempo = bw.call("get_session")["tempo"]
    cfg = genres.settings(genre, depth, tempo)
    overlap = set(source_tracks) & set(target_tracks)
    if overlap:
        raise ValueError(f"tracks {sorted(overlap)} are both source and target")
    before = len(bw.call("get_track", track_index=source_tracks[0])["sends"])
    if use_send_index is None:
        create_track("effect")
        time.sleep(SETTLE)
        idx = before
        if len(bw.call("get_track", track_index=source_tracks[0])["sends"]) <= before:
            raise RuntimeError("the FX bus track did not appear as a new send")
    else:
        idx = use_send_index
    sess_tracks = bw.call("get_session")["tracks"]
    for s in source_tracks:
        bw.call("set_send", track_index=s, send_index=idx, value=send_level)
    out = {"bus": f"FX {idx + 1}", "send_index": idx, "genre": genre, "depth": depth, "tempo": tempo, "settings": cfg,
           "sources": [sess_tracks[i]["name"] for i in source_tracks], "targets": []}
    for t in target_tracks:
        deep.insert(t, "Compressor+", None, "end", None, True)
        time.sleep(SETTLE)
        di = len(deep.tree(t)) - 1
        got = compdev.set_units(bw, deep, t, di, **cfg)
        out["targets"].append({"track": sess_tracks[t]["name"], "device_index": di, "set": {k: v["got"] for k, v in got.items()}})
    todo = []
    if ui:
        out["ui"] = {}
        bus = out["bus"]
        try:
            r = uitools.rename_fx_track(f"FX {idx + 1}", bus_name)
            out["ui"]["rename"] = r
            if r["verified"]:
                bus = bus_name
                out["bus"] = bus_name
        except Exception as e:
            out["ui"]["rename"] = f"failed: {e}"
        for x, t in zip(out["targets"], target_tracks):
            r = None
            for name in dict.fromkeys([bus, bus_name, f"FX {idx + 1}"]):           # try the new name first, then the default one
                try:
                    r = uitools.sidechain_source(t, name, device_index=x["device_index"], tap="pre")
                    break
                except ValueError as e:                                                # not in the menu under that name
                    err = str(e)
                except Exception as e:
                    err = str(e)
                    break
            if r is None:
                out["ui"][x["track"]] = f"failed: {err}"
                todo.append(f"{x['track']}: Compressor+ > sidechain source > '{bus}'")
                continue
            out["ui"][x["track"]] = {"verified": r["verified"], "source": r["source"], "tap": r["tap"]}
            if not r["verified"]:
                todo.append(f"{x['track']}: check the Compressor+ sidechain source shows '{r['source']}'")
    else:
        todo = [f"{x['track']}: Compressor+ > sidechain source > 'FX {idx + 1}'" for x in out["targets"]]
    todo.append("pull the bus fader down so the trigger does not double in the mix (the tap is pre-fader, so ducking is unaffected)")
    out["todo"] = todo
    return out


@tool()
def sidechain_genres() -> list:
    """The genre presets sidechain_setup uses: attack, release as a fraction of a beat, ratio, threshold, knee and a note
    on how that genre uses ducking."""
    return genres.describe()
