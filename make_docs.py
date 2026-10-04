"""Regenerate TOOLS.md from the running connector so the tool list never drifts from the code.
Run after adding or changing tools:  python make_docs.py"""
import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).resolve().parent
GROUPS = [  # (heading, tool-name prefixes/names in that group)
    ("Session & transport", ["get_session", "get_track", "health_check", "transport", "set_tempo", "set_position",
                             "set_metronome", "get_transport", "set_transport", "set_groove", "cue_markers", "save_project"]),
    ("Tracks & mixing", ["create_track", "delete_track", "set_track", "set_send", "sidechain_setup", "sidechain_genres", "compressor_read", "compressor_set", "mix", "select_track", "snapshot",
                         "auto_name_tracks"]),
    ("Clips & scenes", ["launch", "stop_clips", "set_scene_name", "delete_clip", "clip_settings"]),
    ("Writing music", ["write_notes", "write_drums", "write_bass", "write_chords", "write_melody", "write_euclidean",
                       "sketch_song", "make_variation"]),
    ("Editing & analysing notes", ["get_clip_notes", "edit_clip", "note_expressions", "transform_notes", "detect_chords",
                                   "transpose_project", "project_report"]),
    ("Sounds, samples & bookmarks", ["search_presets", "load_preset", "refresh_preset_index", "search_samples",
                                     "load_sample", "preview_sample", "sample_folders", "suggest_samples", "bookmark"]),
    ("Devices", ["list_devices", "get_device", "set_param", "set_device_enabled", "open_device_browser"]),
    ("Deep devices & mid/side EQ", ["device_tree", "deep_params", "deep_set", "eq_set", "device_insert", "device_delete",
                                    "mid_side_eq", "mix_audit", "recipe", "ab_test", "device_catalog",
                                    "preset_inspect", "preset_patch_and_load"]),
    ("Mastering, metering & monitoring", ["get_levels", "gain_stage", "master_meters", "mastering_chain", "master_control",
                                          "analyze_master", "auto_master", "compare_reference", "live_monitor",
                                          "check_tuning"]),
    ("Arrangement", ["record_arrangement", "perform_plan", "perform_ramp", "perform_status", "perform_abort", "return_to_arrangement",
                                    "get_arranger_clip_notes", "edit_arranger_clip"]),
    ("MIDI files & references", ["inspect_midi_file", "import_midi_file", "export_clip_midi", "add_reference",
                                 "list_references", "remove_reference", "reference_target", "compare_to_library"]),
    ("Mix problem-solving", ["masking_report", "masking_fix"]),
    ("Bitwig actions & grouping", ["list_bitwig_actions", "run_bitwig_action", "group_tracks", "ungroup_track",
                                   "get_groups", "select_tracks", "run_action_on_tracks"]),
]


async def main():
    params = StdioServerParameters(command=sys.executable, args=[str(HERE / "server.py")])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = {t.name: t for t in (await s.list_tools()).tools}
    placed, lines = set(), ["# Tool reference", "",
                            f"Generated from the running connector ({len(tools)} tools) by `make_docs.py`. "
                            "Each entry is the description Claude sees.", ""]
    for heading, names in GROUPS:
        lines += [f"## {heading}", ""]
        for n in names:
            if n not in tools:
                raise SystemExit(f"GROUPS mentions unknown tool {n!r}")
            placed.add(n)
            lines += _entry(tools[n])
    rest = sorted(set(tools) - placed)
    if rest:
        lines += ["## Other", ""]
        for n in rest:
            lines += _entry(tools[n])
    (HERE / "TOOLS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote TOOLS.md: {len(tools)} tools" + (f" ({len(rest)} ungrouped: {rest})" if rest else ""))


def _entry(t):
    props = (t.input_schema or {}).get("properties", {})
    args = ", ".join(props)
    desc = " ".join((t.description or "").split())
    return [f"### `{t.name}({args})`", "", desc, ""]


if __name__ == "__main__":
    asyncio.run(main())
