# Bitwig connector for Claude

Lets Claude drive Bitwig Studio: write and edit MIDI, build whole song sketches, load sounds and samples, mix, master with
live measurements, and record scenes into the arrangement. Everything reads back from Bitwig to confirm it took effect.
137 tools — the full list is in [docs/TOOLS.md](docs/TOOLS.md).

## How it fits together

```
Claude ──MCP (stdio)──> server.py ──OSC over UDP──> BitwigMCP controller script (inside Bitwig)
                          │  8765 → Bitwig, replies on 8766–8771 (one per client)
                          └── bwmcp/    tools/ (the 137 MCP tools, by topic) · core/ (connection) · music/ · devices/
                                        analysis/ · control/ · library/ · monitor/ ──> http://127.0.0.1:8780 live dashboard
```

Bitwig's script API cannot see audio, so analysis works on files or on Windows "loopback" capture of Bitwig's output.

## Quick install (Windows)

1. Install Python 3.10+, Bitwig Studio and Claude Code.
2. Double-click `install.bat` (or run `python manage.py install`). It installs the packages, copies the controller script into
   Bitwig's Controller Scripts folder, and registers the MCP server with Claude. Add `--autostart` to start the live monitor at login.
3. In Bitwig: Settings > Controllers > Add controller > Claude > Bitwig MCP. For live measurements set the audio driver to Windows Audio (WASAPI).
4. Start a new Claude session. `python manage.py install --check` tells you what works; `--dry-run` shows changes first; `--uninstall` removes it.

## Setup (already done on this machine)

1. **Bitwig script:** `Documents\Bitwig Studio\Controller Scripts\BitwigMCP\` (`BitwigMCP.control.js`, `pro.js`, `expert.js`,
   `arranger.js`, `deep.js`). In Bitwig: *Settings → Controllers → Add controller → Claude → Bitwig MCP*. Bitwig reloads the script
   whenever a file changes.
2. **Python:** `pip install -r requirements.txt`
3. **Claude:** `claude mcp add --scope user bitwig -- python C:/Users/stuar/Documents/Bitwig/bitwig_mcp/server.py`
   (then start a new Claude session; tools are loaded at session start).
4. **Live capture (optional):** set Bitwig *Settings → Audio → Driver model* to **Windows Audio (WASAPI)**. Exclusive ASIO
   drivers (e.g. ASIO4ALL) can't be captured; file-based analysis works with any driver.

## Everyday use

Ask Claude in plain language, for example:

- "Sketch a 124 bpm house track in F minor" → `sketch_song` (tracks, sounds, 7 scenes of clips)
- "Record those scenes into the arrangement" → `record_arrangement`
- "Show me the mid/side on the master" → `analyze_master` · "Start the live monitor" → `live_monitor`
- "Is the lead in tune?" → `check_tuning` · "Compare to this reference" → `compare_reference`
- "Put a mid/side EQ on the master, mono the bass" → `mid_side_eq` · "Show what is inside that device" → `device_tree`, `deep_params`
- "Find what is clashing in the mix" → `masking_report` / `masking_fix` · "Group these tracks" → `group_tracks`
- "Import this MIDI file" → `import_midi_file` · "Compare my mix to this reference" → `add_reference`, `compare_to_library`
- "Fade the strings in over 8 bars" → `perform_ramp` (writes real automation) · any Bitwig command → `run_bitwig_action`
- "Audit my mix and fix what does nothing" → `mix_audit` · "Save this vocal chain" → `recipe` · "Did that EQ help?" → `ab_test`
- "Tidy my track names" → `auto_name_tracks` · "Save the mixer as 'before'" → `snapshot`

**Live monitor without Claude:** double-click `scripts/start_monitor.bat` (opens http://127.0.0.1:8780).
**Start automatically at login:** `python manage.py autostart` (hidden, no admin needed); `--status` to check, `--remove` to undo.
Every panel has a × to close it; the **Panels** menu in the header brings them back (or *Compact* for loudness only).
Your layout is remembered in the browser, and a closed Master-controls panel never touches Bitwig.

## Project layout

```
server.py            entry point Claude starts (registered with `claude mcp add`); the tools live in bwmcp/
manage.py            one front door: install · sync · docs · monitor · autostart · backup · test
install.bat          double-click installer
bitwig_script/       the Bitwig controller script (git copy; Bitwig loads its own copy, kept in sync by `manage.py sync`)
bwmcp/               the Python package
  core/              bridge.py (OSC link, MCP server, @tool) · util.py (shared helpers) · paths.py (folders, OneDrive-safe)
  tools/             the MCP tools, one file per topic:
                       session.py   transport, tempo, groove, cue markers, recording to the arrangement
                       tracks.py    tracks, sends, scenes, launching, grouping, mixer snapshots
                       clips.py     notes, drums/bass/chords/melody, song sketches, MIDI files, arranger clips
                       devices.py   device parameters, nested chains, EQ, mid/side, recipes, A/B, actions, performance automation
                       presets.py   preset search/loading, automatic track naming
                       mixing.py    levels, mastering chain, analysis, references, masking, mix audit, sidechain, live monitor
                       library.py   samples and bookmarks
                       grid.py      Grid patch editing: add modules to effects Grid / Poly Grid presets, verified
                       extras.py    master recorder, project state/notes, UI layout, window picture, project file report, device units, editing actions
  music/             theory and generators (music) · expert note edits · variations · pitch/tuning · MIDI files · track naming
  devices/           deep device access (deepdev) · Compressor+ units (compdev) · recipes · presets · preset patching · sidechain genres
  analysis/          loudness/spectrum (mastering) · live capture (capture) · reference comparison · reference library · masking finder · mix audit rules
  control/           Bitwig actions and grouping · automation by performance · arranger-clip reading · window screenshot
  library/           samples · bookmarks · project file reader · backup · script sync
  monitor/           live dashboard server and page · autostart at login
data/                your files: caches, saved recipes, bookmarks, snapshots, reports, device-ID list (mostly git-ignored)
docs/                TOOLS.md (generated) · PRESET_FORMAT.md · MODULATORS_AND_GRID.md
scripts/             install.py · make_docs.py · start_monitor.bat
tests/               live_test.py (needs Bitwig) and offline test_*.py
research/            experiments and evidence (see research/README.md); not used by the connector
```

To find something: tool names are in `docs/TOOLS.md`; each tool sits in the `bwmcp/tools/` file for its topic and calls the
helper package of the same area. Add a tool by writing a `@tool()` function in the right file, adding its name to a group in
`scripts/make_docs.py`, then `python manage.py docs`.

## Maintenance

All commands go through `python manage.py <command>` (run it with no arguments for the list).

- **Back up:** `manage.py backup` (zips this folder and the Bitwig script into `..ackups\`, keeps the newest 10);
  `--list`; `--restore <zip>` (makes a safety copy first).
- **Version control:** before committing run `manage.py sync` so `bitwig_script/` matches what Bitwig is running; on a fresh
  machine `manage.py sync --install` puts the script back into Bitwig.
- **Test:** `manage.py test` runs the offline tests. With Bitwig open and the controller enabled, `python tests/live_test.py`
  calls every tool through a real MCP client; it creates its own tracks and removes them. Lint: `python -m pyflakes bwmcp`.
- **After adding a tool:** `manage.py docs` to refresh `docs/TOOLS.md`.

## After an audio-engine crash

Test files can crash Bitwig's audio engine. `python manage.py recover --tracks N` (or the tool `engine_recover`) presses Cancel on the crash dialog
(never Send Report), deletes the crashed track only when the window clearly shows its 'Device missing' panel, and clicks Activate Audio Engine.
N = how many tracks the project had before the test. To run it without an approval prompt add `Bash(python manage.py recover:*)` (and
`mcp__bitwig__engine_recover`) to `permissions.allow` in `.claude/settings.json`.

## Ports

`8765` requests to Bitwig · `8766–8771` replies (a client takes the first free one, so up to 6 can run at once) ·
`8780` live monitor. All bound to 127.0.0.1 only.

## Troubleshooting

- **"No reply from Bitwig"** — Bitwig isn't open, or the controller isn't enabled (see Setup 1).
- **"all Bitwig reply ports … are in use"** — close other Claude sessions or stray `python server.py` processes.
- **Monitor page won't load** — it isn't running: `python manage.py autostart --status`, or double-click `scripts/start_monitor.bat`.
- **Live capture says it can't capture** — Bitwig is on an exclusive driver; switch to Windows Audio (Setup 4).
- **Script errors** — search `%LOCALAPPDATA%\Bitwig Studio\BitwigStudio.log` for "Bitwig MCP".
- **Tools missing in Claude** — start a new session; check `claude mcp get bitwig` shows *Connected*.

## Known limits
- **Display text:** Bitwig never sends parameter display text for direct parameters, so real units (ms, dB, 1:N) come from device-specific parameter objects, built at script start. Done for Compressor+ and EQ+ (`compressor_read` / `compressor_set`, and the Compressors card in the live monitor). Gain reduction is not exposed at all, so there is no live GR meter.

- **Automation by performance** runs in real time and is audible. It records automation for track volume, pan, sends and the
  8 remote controls of a device (verified by replay, about 1 % error); direct parameters move but are never recorded. Re-recording
  overwrites existing lane content.
- **Masking finder** solos each track in turn, so it is audible, needs playback running and Windows loopback capture, and uses a
  mono analysis. Use captures at least one loop long.
- **Reference library** reads WAV and AIFF only (no MP3/FLAC decoder installed); use full songs, not loops, as references.
- **Arranger clips:** `get_arranger_clip_notes` / `edit_arranger_clip` work on the arranger clip you have selected in Bitwig's Arrange view;
  they could not be pointed at a clip recorded from the script. After recording, `return_to_arrangement` (called automatically) makes tracks
  follow the arranger instead of their launcher clips.
- **Bitwig actions:** `group_tracks` / `ungroup_track` switch Bitwig to the ARRANGE layout and focus the track header themselves (verified live: works even when Bitwig was on the Mix layout); bounce, consolidate and normalize run but their
  effect cannot be confirmed from the script. Export Audio opens a dialog.

- **EQ+ band types:** a freshly loaded EQ+ has every band set to *Off*, so changing gain or frequency alone does nothing.
  `eq_set` sets the type (Bell, shelves, cuts, notch) explicitly; the older `set_param` remote controls cannot.
- **Modulators and Grid:** the controller API cannot read, add or route modulators or Grid modules (see `research/`). Presets that
  contain them can still be inserted, and `preset_patch_and_load` can change the numeric values stored in a plain (version 0002)
  preset before loading it. It cannot add modules, cables or modulators, and factory device/module/modulator files are scrambled.
- **Deep device access** works by selecting each device in turn, so `device_tree` and the nested tools take a few seconds and
  briefly change which device is selected in Bitwig. Parameter *display text* is not available for most parameters
  (values are normalized 0..1); EQ+ is converted to real units (Hz, dB, Q).

- Bitwig's API can't place or read **arranger clips**; `record_arrangement` records scenes instead, and the arrangement can't
  be read back (check the Arrange view yourself).
- Sounds load from preset/device **files** (6,000+ indexed), not by browsing Bitwig's own browser or its favourites.
- Per-note **pressure** can be set but Bitwig doesn't report it back, so it can't be verified.
- Meters are on Bitwig's 0–1 scale; true LUFS / dBTP come from the captured audio, not from Bitwig's meters.
- Master-chain sliders and tools select Bitwig's master track; don't use the monitor's sliders while Claude is also
  changing the master chain.
