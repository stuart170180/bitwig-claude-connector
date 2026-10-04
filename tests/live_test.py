"""Live regression test: calls every tool through a real MCP client against the running Bitwig.
Creates its own tracks/bookmarks/snapshots and removes them afterwards. Bitwig must be open with the
Bitwig MCP controller enabled. Run: python tests/live_test.py"""
import asyncio
import json
import sys
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = Path(__file__).resolve().parents[1] / "server.py"
results = []


async def call(s, name, args=None, expect_error=False):
    t0 = time.time()
    res = await s.call_tool(name, args or {})
    text = next((c.text for c in res.content if c.type == "text"), "")
    ok = res.is_error == expect_error
    results.append((ok, name, round(time.time() - t0, 1), text[:160].replace("\n", " ") if not ok else ""))
    print(("PASS" if ok else "FAIL"), f"{name:24s}", f"{time.time() - t0:5.1f}s", "" if ok else text[:300])
    try:
        return json.loads(text) if text.strip().startswith(("{", "[")) else text
    except json.JSONDecodeError:
        return text


async def main():
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            names = {t.name for t in (await s.list_tools()).tools}
            tested = set()

            async def c(name, args=None, **kw):
                tested.add(name)
                return await call(s, name, args, **kw)

            await c("health_check")
            sess = await c("get_session", {"with_clips": True})
            orig_tempo = sess["tempo"]
            n0 = len(sess["tracks"])
            await c("get_transport")

            # tracks
            t = await c("create_track", {"kind": "instrument", "name": "T Drums", "instrument": "Legend 909 Normal Kit"})
            d = t["index"]
            t = await c("create_track", {"kind": "instrument", "name": "T Keys", "color": "#2fb380"})
            k = t["index"]
            await c("get_track", {"track_index": k})
            await c("set_track", {"track_index": k, "volume_db": -6, "pan": -0.3, "color": "#ff8800"})
            await c("mix", {"tracks": [{"track_index": d, "volume_db": -4}, {"track_index": k, "mute": False}]})
            await c("select_track", {"track_index": k})
            await c("set_track", {"track_index": 99}, expect_error=True)

            # generation
            await c("write_drums", {"track_index": d, "slot": 0, "style": "techno", "bars": 2})
            await c("write_chords", {"track_index": k, "slot": 0, "progression": "minor_epic", "key": "A", "scale": "minor", "rhythm": "pulse"})
            await c("write_bass", {"track_index": k, "slot": 1, "progression": "pop", "key": "C", "style": "walking"})
            await c("write_melody", {"track_index": k, "slot": 2, "chords": ["Am", "F", "C", "G"], "key": "C", "seed": 1})
            await c("write_notes", {"track_index": k, "slot": 3, "notes": [{"pitch": 60, "start": 0, "duration": 1, "velocity": 90}]})
            await c("write_euclidean", {"track_index": d, "slot": 1, "layers": [{"pitch": 36, "pulses": 4, "steps": 16}, {"pitch": 42, "pulses": 5, "steps": 12}]})
            await c("write_euclidean", {"track_index": d, "slot": 2, "layers": [{"pitch": 36, "pulses": 9, "steps": 4}]}, expect_error=True)

            # clip editing / expert
            notes = await c("get_clip_notes", {"track_index": k, "slot": 0})
            assert notes["count"] > 0
            await c("edit_clip", {"track_index": k, "slot": 0, "operation": "humanize", "seed": 1})
            await c("edit_clip", {"track_index": k, "slot": 3, "operation": "double"})
            await c("note_expressions", {"track_index": k, "slot": 0, "select": {"top": True}, "set": {"chance": 0.7}, "ramp": {"velocity": [50, 110]}})
            await c("transform_notes", {"track_index": k, "slot": 0, "operation": "voicing", "mode": "drop2"})
            await c("transform_notes", {"track_index": k, "slot": 0, "operation": "transpose", "semitones": -2})
            await c("transform_notes", {"track_index": k, "slot": 0, "operation": "harmonize", "intervals": [7], "select": {"bottom": True}})
            await c("transform_notes", {"track_index": k, "slot": 0, "operation": "bogus"}, expect_error=True)
            await c("clip_settings", {"track_index": k, "slot": 0, "loop_length": 8, "accent": 0.6})
            await c("delete_clip", {"track_index": k, "slot": 3})
            await c("detect_chords", {"track_index": k, "slot": 0})
            await c("make_variation", {"track_index": d, "slot": 0, "to_slot": 4, "kind": "fill"})
            await c("make_variation", {"track_index": d, "slot": 0, "to_slot": 5, "kind": "nope"}, expect_error=True)
            await c("transpose_project", {"semitones": 2, "track_indices": [k]})
            await c("project_report", {"max_clips": 4})
            await c("suggest_samples", {"category": "vocal", "limit": 2})

            # launcher / transport
            await c("set_scene_name", {"scene": 7, "name": "T Scene"})
            await c("launch", {"track_index": d, "slot": 0})
            await c("transport", {"action": "play"})
            await c("get_levels", {"seconds": 1.5})
            await c("master_meters", {"seconds": 1})
            await c("stop_clips", {})
            await c("transport", {"action": "stop"})
            await c("set_tempo", {"bpm": 127})
            await c("set_position", {"beats": 0})
            await c("set_metronome", {"enabled": False})
            await c("set_transport", {"loop_enabled": False, "launch_quantization": "1"})
            await c("set_groove", {"shuffle_amount": 0.5})
            await c("cue_markers", {"action": "list"})

            # devices
            await c("list_devices", {"track_index": d})
            await c("get_device", {"track_index": d, "device_index": 0})
            await c("set_param", {"track_index": d, "device_index": 0, "index": 0, "value": 0.5})
            await c("set_device_enabled", {"enabled": True, "track_index": d, "device_index": 0})

            # deep device access (nested chains, every parameter, mid/side EQ)
            ms = await c("mid_side_eq", {"track_index": k, "mid_bass_cut_db": -2, "side_gain_db": -1})
            assert any(b["type"].startswith("Low-cut") for b in ms["side_eq"]), "side low-cut not set"
            tree = await c("device_tree", {"track_index": k})
            assert tree["devices"][-1]["chains"]["Side"][0]["name"] == "EQ+", "Side slot has no EQ+"
            ms_i = ms["mid_side_split_index"]
            await c("deep_params", {"track_index": k, "device_index": ms_i, "slot": "Mid", "filter": "Band 3"})
            await c("eq_set", {"track_index": k, "device_index": ms_i, "slot": "Mid",
                               "bands": [{"band": 3, "type": "Bell", "freq_hz": 250, "gain_db": -1.5}]})
            await c("deep_set", {"track_index": k, "device_index": ms_i, "values": {"Side Gain": 0.5}})
            await c("device_insert", {"track_index": k, "device": "EQ+", "slot": "Side", "device_index": ms_i})
            await c("device_delete", {"track_index": k, "device_index": ms_i, "slot": "Side", "slot_index": 1})

            await c("return_to_arrangement", {})
            await c("get_arranger_clip_notes", {})
            await c("list_bitwig_actions", {"filter": "group", "limit": 5})
            await c("get_groups", {})
            await c("perform_status", {})
            await c("list_references", {})
            await c("inspect_midi_file", {"path": r"C:/Program Files/Cycling '74/Max 9/examples/legacy-examples/recycler-folder/drumLoop.mid"})
            await c("run_bitwig_action", {"action_id": "File | Close"}, expect_error=True)  # deny-list must refuse
            await c("device_catalog", {"query": "poly"})
            await c("device_insert", {"track_index": k, "device": "Note Grid", "by_uuid": True})
            await c("preset_inspect", {"preset": "Note Grid"}, expect_error=True)  # factory device file is scrambled
            await c("mix_audit", {"track_indices": [k], "include_master": False})
            await c("recipe", {"action": "save", "name": "t_recipe", "track_index": k})
            await c("recipe", {"action": "list"})
            await c("recipe", {"action": "delete", "name": "t_recipe"})
            await c("ab_test", {"track_index": k, "device_index": 0, "values": {"Mid Gain": 0.5}}, expect_error=True)  # not playing

            # presets / samples / bookmarks
            await c("search_presets", {"query": "pad", "limit": 3})
            await c("load_preset", {"name": "EQ+", "track_index": k})
            sm = await c("search_samples", {"category": "kick", "limit": 2})
            await c("load_sample", {"sample": sm["samples"][0]["path"], "new_track_name": "T Sample"})
            await c("bookmark", {"action": "add", "item": "Jupiter Pad", "label": "T Bookmark", "tags": ["test"]})
            await c("bookmark", {"action": "list", "tag": "test"})
            await c("bookmark", {"action": "load", "item": "T Bookmark", "track_index": k})
            await c("bookmark", {"action": "remove", "item": "T Bookmark"})
            await c("sample_folders", {})
            await c("preview_sample", {"stop": True})

            # snapshots / naming / analysis
            await c("snapshot", {"action": "save", "name": "t_snap"})
            await c("snapshot", {"action": "diff", "name": "t_snap"})
            await c("snapshot", {"action": "recall", "name": "t_snap"})
            await c("snapshot", {"action": "delete", "name": "t_snap"})
            await c("auto_name_tracks", {"track_indices": [d, k], "dry_run": True})
            await c("analyze_master", {"source": sm["samples"][0]["path"], "seconds": 0, "show_image": True})
            await c("mastering_chain", {"action": "list"})
            loops = await c("search_samples", {"category": "drum loop", "kind": "loop", "limit": 3})
            wavs = [x["path"] for x in loops["samples"] if x["path"].lower().endswith(".wav")]
            await c("check_tuning", {"source": wavs[0], "seconds": 6, "start": 0, "show_image": True})
            await c("check_tuning", {"source": "live", "seconds": 0}, expect_error=True)
            await c("record_arrangement", {"scenes": [99]}, expect_error=True)
            await c("compare_reference", {"reference": wavs[0], "mix": wavs[-1], "seconds": 3, "ref_start": 0})

            # MIDI file round trip, grouping (needs no audio)
            mid = r"C:/Program Files/Cycling '74/Max 9/examples/legacy-examples/recycler-folder/drumLoop.mid"
            tmp = str(Path(__file__).resolve().parent / "_t.mid")
            imp = await c("import_midi_file", {"path": mid, "track_index": d, "slot": 7})
            assert imp["notes_in_bitwig"] > 0, "imported clip is empty"
            await c("export_clip_midi", {"track_index": d, "slot": 7, "path": tmp})
            Path(tmp).unlink(missing_ok=True)
            await c("select_tracks", {"track_indices": [d, k]})
            # group_tracks/ungroup_track only work while Bitwig's Arranger timeline (track headers) is on screen, so
            # they are not part of the automatic run; try them by hand from the Arrange view.
            # extras: project state, UI layout, notes, last-clicked, transport extras, window picture, project file report, recorder, units
            await c("project_state")
            await c("ui_layout", {"mixer": {"meters": True}})
            await c("ui_layout", {"mixer": {"meters": False}})
            await c("project_notes", {"action": "get"})
            await c("last_clicked")
            await c("transport_extras")
            await c("look_at_bitwig", {"max_width": 800})
            await c("project_file_report")
            await c("record_master", {"action": "status"})
            await c("sidechain_genres")
            await c("edit_action", {"action": "zoom_to_fit"})
            await c("grid_templates")
            await c("chord_library")
            await c("suggest_voicing", {"genre": "trance"})
            await c("chord_voicings", {"chord": "Dm9", "styles": ["drop2", "neo_soul"]})
            await c("grid_inspect", {"base": "fx"})
            await c("grid_add_module", {"base": "fx", "module": "Low-pass", "between": ["Audio In", "Audio Out"], "params": {"CUTOFF": 60}, "name": "live_test_grid"})
            await c("engine_recover", {"wait_seconds": 5})
            # not run here (they change or play things): undo_redo, device_units set, sidechain_setup, record_master capture

            # not run here (they play audio or change playback): masking_report/fix, perform_*, add_reference/compare_to_library

            # cleanup: delete created tracks (highest index first) and restore tempo
            sess = await c("get_session")
            for tr in sorted(sess["tracks"], key=lambda x: -x["index"]):
                if tr["index"] >= n0:
                    await c("delete_track", {"track_index": tr["index"]})
            await c("set_scene_name", {"scene": 7, "name": ""})
            await c("set_tempo", {"bpm": orig_tempo})
            await asyncio.sleep(1.5)  # let Bitwig finish removing tracks before counting
            final = await c("get_session")
            assert len(final["tracks"]) == n0, f"cleanup left tracks behind: {len(final['tracks'])} vs {n0}"

            untested = sorted(names - tested - {"sketch_song", "auto_master", "refresh_preset_index", "save_project",
                                                "open_device_browser", "delete_track", "undo", "redo"})
            print("\nnot exercised:", untested)
    fails = [r for r in results if not r[0]]
    print(f"\n{len(results) - len(fails)}/{len(results)} passed")
    for f in fails:
        print("FAIL", f[1], f[3])
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
