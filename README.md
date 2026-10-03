# Bitwig connector for Claude

Lets Claude drive Bitwig Studio: write and edit MIDI, build whole song sketches, load sounds and samples, mix, master with
live measurements, and record scenes into the arrangement. Everything reads back from Bitwig to confirm it took effect.
105 tools — the full list is in [TOOLS.md](TOOLS.md).

## How it fits together

```
Claude ──MCP (stdio)──> server.py ──OSC over UDP──> BitwigMCP controller script (inside Bitwig)
                          │  8765 → Bitwig, replies on 8766–8771 (one per client)
                          ├── music.py / expert.py / variations.py   note generation and editing
                          ├── presets.py / samples.py / bookmarks.py sound libraries
                          ├── deepdev.py                             nested devices, every parameter, mid/side EQ
                          ├── mastering.py / reference.py / pitch.py audio analysis (WAV files or live capture)
                          └── live_monitor.py ──> http://127.0.0.1:8780   live dashboard (loudness, M/S, tuner, master controls)
```

Bitwig's script API cannot see audio, so analysis works on files or on Windows "loopback" capture of Bitwig's output.

## Quick install (Windows)

1. Install Python 3.10+, Bitwig Studio and Claude Code.
2. Double-click `install.bat` (or run `python install.py`). It installs the packages, copies the controller script into
   Bitwig's Controller Scripts folder, and registers the MCP server with Claude. Add `--autostart` to start the live monitor at login.
3. In Bitwig: Settings > Controllers > Add controller > Claude > Bitwig MCP. For live measurements set the audio driver to Windows Audio (WASAPI).
4. Start a new Claude session. `python install.py --check` tells you what works; `--dry-run` shows changes first; `--uninstall` removes it.

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

**Live monitor without Claude:** double-click `start_monitor.bat` (opens http://127.0.0.1:8780).
**Start automatically at login:** `python autostart.py` (hidden, no admin needed); `--status` to check, `--remove` to undo.
Every panel has a × to close it; the **Panels** menu in the header brings them back (or *Compact* for loudness only).
Your layout is remembered in the browser, and a closed Master-controls panel never touches Bitwig.

## Files

| File | Purpose |
|---|---|
| `server.py` | MCP server: all 105 tools, the Bitwig bridge |
| `music.py`, `expert.py`, `variations.py` | Theory, generators, expert note edits, variations |
| `presets.py`, `samples.py`, `bookmarks.py`, `naming.py` | Libraries, bookmarks (`bookmarks.json`), track auto-naming |
| `midifile.py`, `reflib.py` | MIDI file read/write and clip import/export; reference-track library (`references.json`) |
| `masking.py` | Masking finder: solo each track, capture, score clashes, propose and apply EQ cuts |
| `actionsdev.py`, `performdev.py` | Bitwig actions (group/ungroup, run by id) and automation by performance; script sides are `actions.js` and `perform.js` |
| `presetpatch.py`, `bitwig_device_ids.json` | Read/patch plain preset files; UUIDs of Bitwig's 152 built-in devices for `device_insert(by_uuid=True)` |
| `audit.py`, `recipes.py` | Mix audit rules and fixes; saved device-chain recipes (`recipes/*.json`) |
| `research/` | Notes and prototypes on modulators, Grid and preset files (see `MODULATORS_AND_GRID.md`); not used by the connector |
| `deepdev.py` | Deep device access: walks into nested chains (Mid-Side Split slots), reads/sets every parameter, EQ+ in real units, mid/side EQ |
| `mastering.py`, `reference.py`, `pitch.py` | Loudness / M-S / spectrum, reference comparison, pitch and tuning |
| `live_monitor.py` / `.html` | Live dashboard web server and page |
| `autostart.py` | Starts the dashboard hidden at Windows login (`--status`, `--remove`) |
| `start_monitor.bat` | Starts the dashboard in a window on demand |
| `tests/live_test.py` | Regression test that calls every tool through a real MCP client |
| `make_docs.py` | Regenerates `TOOLS.md` |
| `backup.py` | Timestamped zip backups and restore |
| `bitwig_script/` | Git-tracked copy of the Bitwig controller script (Bitwig loads the original from its own folder) |
| `sync_script.py` | Mirrors the script between Bitwig's folder and `bitwig_script/` (`--install`, `--check`) |
| `snapshots/`, `reports/` | Saved mixer snapshots / monitor reports (created on first use) |

## Maintenance

- **Back up:** `python backup.py` (zips this folder and the Bitwig script into `..\backups\`, keeps the newest 10);
  `python backup.py --list`; `python backup.py --restore <zip>` (makes a safety copy first).
- **Version control:** this folder is a git repo. Before committing run `python sync_script.py` so `bitwig_script/` matches what
  Bitwig is running; on a fresh machine run `python sync_script.py --install` to put the script back into Bitwig.
- **Test:** open Bitwig with the controller enabled, then `python tests/live_test.py`. It creates its own tracks and removes
  them again. Lint with `python -m pyflakes *.py`.
- **After adding a tool:** `python make_docs.py` to refresh `TOOLS.md`.

## Ports

`8765` requests to Bitwig · `8766–8771` replies (a client takes the first free one, so up to 6 can run at once) ·
`8780` live monitor. All bound to 127.0.0.1 only.

## Troubleshooting

- **"No reply from Bitwig"** — Bitwig isn't open, or the controller isn't enabled (see Setup 1).
- **"all Bitwig reply ports … are in use"** — close other Claude sessions or stray `python server.py` processes.
- **Monitor page won't load** — it isn't running: `python autostart.py --status`, or double-click `start_monitor.bat`.
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
