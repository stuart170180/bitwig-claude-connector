"""Mix audit: read every device on every track, flag problems, and (optionally) apply the safe fixes.
Needs the deep device access (deepdev.py, controller script 6.0+)."""
import time

import deepdev

COMP_NAMES = ("Compressor", "Compressor+", "Bus Compressor", "Peak Limiter", "Limiter", "OTT", "Dynamics")
EQ_NAME = "EQ+"
# Which tracks to skip when walking: none by default (includes groups and FX returns that are in the track bank)


def snapshot(deep, track_index):
    """Devices on one track with enough detail to judge them. EQ+ bands in real units; other devices just name/state."""
    bw = deep.bw
    if track_index == -1:
        bw.call("select_master")
    else:
        bw.call("select_track", track_index=track_index)
    time.sleep(deepdev.STEP)
    out = []
    for d in bw.call("list_devices")["devices"]:
        node = {"index": d["index"], "name": d["name"], "enabled": d["enabled"], "plugin": d["plugin"]}
        if d["name"] == EQ_NAME:
            try:
                deep.goto(track_index, d["index"])
                node["bands"] = deep.eq_state()
            except Exception as e:  # keep auditing even if one device can't be read
                node["error"] = str(e)
        out.append(node)
    return out


def judge(track_name, devices):
    """Problems found on one track's device list: [{severity, device_index, issue, fix}]. Pure function."""
    issues = []
    comps = [d for d in devices if d["name"] in COMP_NAMES and d["name"] not in ("Peak Limiter", "Limiter")]
    if len(comps) > 1:
        issues.append({"severity": "info", "device_index": comps[1]["index"],
                       "issue": f"{len(comps)} dynamics devices in a row ({', '.join(c['name'] for c in comps)}) - check they aren't fighting",
                       "fix": None})
    seen = {}
    for d in devices:
        if not d["enabled"]:
            issues.append({"severity": "warn", "device_index": d["index"],
                           "issue": f"{d['name']} is bypassed", "fix": "enable"})
        if d["name"] == EQ_NAME and "bands" in d:
            active = [b for b in d["bands"] if b["type"] != "Off" and b["on"]]
            moved = [b for b in d["bands"] if b["type"] == "Off" and (abs(b["gain_db"]) > 0.05)]
            if moved:
                issues.append({"severity": "error", "device_index": d["index"],
                               "issue": "EQ+ has bands with a gain set but type Off, so they do nothing: bands "
                                        + ", ".join(str(b["band"]) for b in moved),
                               "fix": "retype_eq"})
            elif not active:
                issues.append({"severity": "warn", "device_index": d["index"],
                               "issue": "EQ+ with every band Off - it does nothing", "fix": None})
            else:
                flat = [b for b in active if "cut" not in b["type"].lower() and abs(b["gain_db"]) < 0.05]
                if len(flat) == len(active):
                    issues.append({"severity": "warn", "device_index": d["index"],
                                   "issue": "EQ+ bands are on but all at 0 dB - it does nothing", "fix": None})
        seen[d["name"]] = seen.get(d["name"], 0) + 1
    for name, n in seen.items():
        if n > 1 and name not in ("EQ+",) and name not in COMP_NAMES:
            issues.append({"severity": "info", "device_index": None,
                           "issue": f"{n} x {name} on '{track_name}'", "fix": None})
    return issues


def retype_for(band):
    """Best guess at the intended type of a band that has a gain but type Off: shelf at the ends, bell between."""
    f = band["freq_hz"]
    if band["band"] == 1 and f < 250:
        return "Low-shelf"
    if band["band"] == 8 or (band["band"] == 7 and f > 4000):
        return "High-shelf"
    return "Bell"


def fix_eq(deep, track_index, device_index):
    """Give every band that has a gain but type Off an appropriate type. Returns the list of changes."""
    deep.goto(track_index, device_index)
    changes = []
    for b in deep.eq_state():
        if b["type"] == "Off" and abs(b["gain_db"]) > 0.05:
            t = retype_for(b)
            deep.eq_band(b["band"], type=t, enabled=True)
            changes.append({"band": b["band"], "type": t, "freq_hz": b["freq_hz"], "gain_db": b["gain_db"]})
    return changes


def run(deep, track_indices, fix=False, include_master=True):
    bw = deep.bw
    sess = bw.call("get_session")
    names = {t["index"]: t["name"] for t in sess["tracks"]}
    targets = [i for i in (track_indices if track_indices is not None else names) if i in names]
    plan = ([-1] if include_master else []) + targets
    report, fixed = [], []
    for ti in plan:
        tname = "Master" if ti == -1 else names[ti]
        devs = snapshot(deep, ti)
        issues = judge(tname, devs)
        if fix:
            for iss in issues:
                if iss["fix"] == "retype_eq":
                    fixed.append({"track": tname, "device_index": iss["device_index"],
                                  "changes": fix_eq(deep, ti, iss["device_index"])})
                elif iss["fix"] == "enable":
                    deep.goto(ti, iss["device_index"])
                    bw.call("set_device_enabled", enabled=True)
                    fixed.append({"track": tname, "device_index": iss["device_index"], "changes": "enabled"})
        report.append({"track_index": ti, "track": tname, "devices": devs, "issues": issues})
    n = sum(len(r["issues"]) for r in report)
    return {"tracks_checked": len(plan), "issues": n, "fixed": fixed, "report": report}
