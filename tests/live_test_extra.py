"""Second live test: the tools tests/live_test.py leaves out because they play audio, change the song, or need a real project.
Run it on the Trance Test Template (24 tracks, 140 bpm): python tests/live_test_extra.py
It changes the open project and does NOT save it; reopen the template afterwards to discard the changes. UI-driven tools (insert_plugin,
sidechain_*, FX-track rename / delete, select_arranger_clip, parallel_compression) are left out on purpose: they click on the screen."""
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server  # noqa: E402
from bwmcp.core import appbridge  # noqa: E402

bw = server.bw
results = []
KICK, BASS, CHORDS, PLUCK, LEAD, PAD, ATMOS = 1, 13, 16, 17, 18, 19, 21


def step(name, fn, expect_error=False):
    t0 = time.time()
    try:
        out = fn()
        ok = not expect_error
        msg = "" if ok else "expected an error"
    except Exception as e:  # noqa: BLE001
        out, ok, msg = None, expect_error, str(e)[:160]
    results.append((ok, name))
    print(("PASS" if ok else "FAIL"), f"{name:34s} {time.time() - t0:5.1f}s", "" if ok else msg, flush=True)
    return out


def settle(track):
    for _ in range(10):
        bw.call("select_track", track_index=track)
        time.sleep(1.0)
        if bw.call("list_devices")["track"] == bw.call("get_session")["tracks"][track]["name"]:
            return
    raise RuntimeError("track not selected")


def main():
    sess = bw.call("get_session")
    if sess["tempo"] != 140 or len(sess["tracks"]) < 24 or bw.call("proj_state")["project"] != "Trance Test Template":
        sys.exit("open the Trance Test Template first (140 bpm, 24 tracks)")
    n0 = len(sess["tracks"])

    # --- reading -------------------------------------------------------------------------------------------------
    step("vst_status", lambda: server.vst_status())
    step("manual_search", lambda: server.manual_search("compressor", limit=3))
    step("manual_section", lambda: server.manual_section(page=5, pages=1, max_chars=2000))
    step("device_manual", lambda: server.device_manual("Compressor+", max_chars=1500))
    ref = Path(tempfile.mkdtemp()) / "t_ref.wav"                          # a short synthetic reference so the library tools have something to hold
    t = np.arange(44100 * 6) / 44100
    sf.write(str(ref), (0.3 * np.sin(2 * np.pi * 110 * t) + 0.1 * np.sin(2 * np.pi * 2200 * t)).astype("float32"), 44100)
    step("add_reference", lambda: server.add_reference(str(ref), "zz_live_test", seconds=5, note="live test"))
    step("reference_target", lambda: server.reference_target(["zz_live_test"]))
    step("spire_presets", lambda: server.spire_presets("lead", limit=3))
    settle(BASS)
    step("compressor_read", lambda: server.compressor_read(BASS))
    step("device_units", lambda: server.device_units(BASS, 1))
    was_running = appbridge.read_latest() is not None             # never close an app the user has open
    step("live_monitor start/reading", lambda: [server.live_monitor("start"), time.sleep(1), server.live_monitor("reading")])
    if not was_running:
        step("live_monitor stop", lambda: server.live_monitor("stop"))

    # --- looks, mixing, devices --------------------------------------------------------------------------------
    step("color_tracks", lambda: server.color_tracks(scheme="roles"))
    step("color_clips", lambda: server.color_clips(KICK, "#ff8800", slots=[0]))
    step("set_send", lambda: server.set_send(KICK, 0, 0.3))
    step("compressor_set", lambda: server.compressor_set(BASS, 1, ratio=4.0, attack_ms=10))
    step("compressor_mode", lambda: server.compressor_mode(BASS, 1, character="Vanilla"))
    step("master_control", lambda: server.master_control(width_pct=100, ceiling_db=-1.0))
    step("true_peak_limiter (insert)", lambda: server.true_peak_limiter(ceiling_db=-1.2, insert=True))
    tp = next((d["index"] for d in server.deep.tree(-1) if "true peak" in d["name"].lower()), None)
    step("device_delete (master true peak)", lambda: server.device_delete(-1, tp))
    step("pitch_shift", lambda: server.pitch_shift(LEAD, semitones=0, cents=0))
    step("spire_load", lambda: server.spire_load(LEAD, "Lead_SuperSaw"))
    step("insert_plugin_by_id", lambda: server.insert_plugin_by_id("BW Remote", track_index=ATMOS))
    settle(ATMOS)
    probe = next((i for i, d in enumerate(bw.call("list_devices")["devices"]) if d["name"] == "BW Remote"), None)
    step("device_delete (the probe)", lambda: server.device_delete(ATMOS, probe))

    # --- groups, scenes, chords ---------------------------------------------------------------------------------
    a = server.create_track("audio", name="T A")["index"]
    b = server.create_track("audio", name="T B")["index"]
    step("group_tracks", lambda: server.group_tracks([a, b], name="T Group"))
    grp = next((t["index"] for t in bw.call("get_session")["tracks"] if t["name"] == "T Group"), None)
    step("ungroup_track", lambda: server.ungroup_track(grp) if grp is not None else (_ for _ in ()).throw(RuntimeError("group not found")))
    k = server.create_track("instrument", name="T Chords")["index"]
    step("write_voiced_chords", lambda: server.write_voiced_chords(k, 0, chords=["Am7", "Dm7", "G7", "Cmaj7"], key="C", scale="major", style="drop2"))
    step("launch + scene_from_playing", lambda: [server.launch(k, 0), time.sleep(1.5), server.scene_from_playing_clips(), server.stop_clips()])
    step("reset_track_states", lambda: server.reset_track_states())

    # --- audio-playing tools (short) ---------------------------------------------------------------------------------
    def play_drop():
        """Loop the drop (the song ends at bar 105 and silence follows) and make sure the transport really runs: play() on a running transport can stop it."""
        server.set_transport(loop_enabled=True, loop_start=256, loop_length=64)
        for _ in range(3):
            bw.call("stop")
            time.sleep(0.5)
            bw.call("set_position", beats=256)
            time.sleep(0.5)
            bw.call("play")
            time.sleep(2.0)
            if bw.call("get_session")["playing"]:
                return
        raise RuntimeError("could not start playback")
    play_drop()
    step("gain_stage (dry)", lambda: server.gain_stage(target_peak=0.7, track_indices=[KICK], seconds=2, passes=1))
    play_drop()
    step("masking_report", lambda: server.masking_report(track_indices=[KICK, BASS], seconds=3))
    server.reset_track_states()
    play_drop()
    def tuning():                                                          # a correct refusal ("no pitched content") counts: it depends on what plays in the 5 s window
        try:
            return server.fix_tuning(PLUCK, seconds=5, apply=False)
        except Exception as e:  # noqa: BLE001
            if "no pitched content" in str(e):
                return {"note": "refused: no steady pitched content in the window"}
            raise
    step("fix_tuning (no apply)", tuning)
    bw.call("stop")
    step("masking_live", lambda: server.masking_live(track_indices=[KICK, BASS, PAD], seconds=6, start_beats=256))

    # --- undo ---------------------------------------------------------------------------------------
    step("remove_reference", lambda: server.remove_reference("zz_live_test"))
    step("undo_redo", lambda: server.undo_redo("undo", 1))
    step("undo_redo redo", lambda: server.undo_redo("redo", 1))

    # --- clean up what this run created (the rest changes the unsaved song only) ------------------------------------------
    for tr in sorted(bw.call("get_session")["tracks"], key=lambda t: -t["index"]):
        if tr["index"] >= n0:
            server.delete_track(tr["index"])
            time.sleep(1.5)
    server.reset_track_states()
    bw.call("stop")
    left = len(bw.call("get_session")["tracks"]) - n0
    fails = [n for ok, n in results if not ok]
    print(f"\n{len(results) - len(fails)}/{len(results)} passed; tracks left behind: {left}")
    for n in fails:
        print("FAIL", n)
    return 1 if fails or left else 0


if __name__ == "__main__":
    sys.exit(main())
