# Claude <-> Bitwig Studio connector

A Bitwig controller script (JavaScript) plus a Python MCP server. Claude drives Bitwig through MCP tools. Owner: S.Simpson
(GitHub `stuart170180`, Windows 11). Private repo `stuart170180/bitwig-claude-connector`, branch `main`.
Full docs: `README.md` (overview, install, known limits), `docs/TOOLS.md` (generated tool list), `TODO.md` (open work).

## How to work with this user
- Do not ask questions; take their answers as yes and carry on. Pick a sensible default and say what you chose.
- Commit and push is pre-approved after each finished piece of work. Co-author line as the system reminder gives it.
- After every piece of work update `TODO.md`, and `README.md` / `docs/TOOLS.md` when tools change (`python manage.py docs`).
- Use workers (subagents) only when asked. Say what you are doing during long steps.
- Report honestly: say what was tested live and what was not.

## Layout (details in README "Project layout")
- `server.py` is only the entry point (registered with `claude mcp add`). The tools live in `bwmcp/tools/` by topic:
  `session`, `tracks`, `clips`, `devices`, `presets`, `mixing`, `library`, `extras`. Shared connection and helpers: `bwmcp/core/`
  (`bridge.py` has `mcp`, `tool`, `bw`, `deep`; `util.py`; `paths.py` has `ROOT` and `DATA`).
- Helper packages by area: `bwmcp/music/`, `devices/` (deepdev, compdev, recipes, presets, presetpatch, genres), `analysis/`,
  `control/` (actions, performance, arranger clips), `library/` (samples, bookmarks, backup, sync), `monitor/`.
- A new tool: write a `@tool()` function in the matching `bwmcp/tools/*.py` file (import what it needs; keep imports one-way,
  no tool module imports a later one: presets < tracks < clips/mixing/library), add the name to a group in
  `scripts/make_docs.py`, run `python manage.py docs`. `server.<name>` still resolves for every tool and helper.
- Personal and generated files live in `data/` (caches, recipes, snapshots, bookmarks, device IDs); docs in `docs/`.
- `bitwig_script/` is the git copy of the controller script. The live copy Bitwig loads is in
  `Documents\Bitwig Studio\Controller Scripts\BitwigMCP\`. Edit the live copy, then `python manage.py sync` before committing
  (`sync --install` goes the other way). Bitwig reloads the script about 5 s after a file changes.
- `tests/`: `live_test.py` (needs Bitwig running), plus offline `test_*.py` (`python manage.py test`). `research/`: experiments only (see its README; scripts find the repo root themselves, live ones need Bitwig).

## Commands
`python manage.py` lists them: `install` (`--check` is the doctor), `sync`, `docs`, `monitor`, `autostart`, `backup`, `test`.

## Protocol
Python sends OSC `/mcp "<json>"` to Bitwig on UDP 8765; replies come back as `/reply` on ports 8766-8771. Call from Python
with `server.bw.call("<command>", **args)`. Live monitor: `python manage.py monitor` on http://127.0.0.1:8780 (autostart:
`python manage.py autostart`).

## Hard-won rules (do not rediscover)
- The Bitwig API has no access to: modulators, Grid, sidechain source choice, FX track names/faders, compressor gain
  reduction. Do not promise these. Direct parameters are not recordable; use remote controls for automation recording.
- Keep the `mcp` package current (>=2.3): older versions made `claude mcp get bitwig` fail its handshake check (-32022).
- Direct-parameter display text never arrives. Real units (ms, dB, 1:N) come from `createSpecificBitwigDevice` parameter
  objects, which can only be created at script start (`DISP_DEVICES` in `deep.js`)
- `setDirectParameterValueNormalized(id, value*16384, 16384)`: pass value in 0..resolution, not 0..1.
- A fresh EQ+ has all bands Off; set types explicitly (`eq_set`). Mid/side EQ gain = 0.5 + dB/48.
- Grouping works only with the ARRANGE layout showing and the track header focused; `group_tracks` does both itself.
- `get_clip_notes` right after a write can return 0; wait or use `read_clip_settled`. Call `transport.returnToArrangement()`
  after launching clips (record_arrangement does).
- Preset files: container "BtWg00030002" parses and round-trips; same-length patches work, length-changing edits are
  unproven and one edited Grid file crashed the audio engine. Never load experimental patched presets into a real project.
- Parallel workers that each build tracks will wipe each other's project. Run live Bitwig tests one at a time.
- Audio analysis: BS.1770 LUFS, true peak, mid/side. Live capture uses Bitwig's own master recorder first (`bwmcp/analysis/capture.py`, any
  driver, exact length, temp file deleted after reading) and falls back to WASAPI loopback.
- NEVER call `Signal.fire()` (document-state signal) from the controller script: it throws inside Bitwig and crashes the whole app.
  `markInterested()` only works during init, so any new readable value needs an `extras.js`-style init edit and a reload.
- The controller script runs at `loadAPI(25)` (v6.1, `extras.js`). Real-unit display text exists for Compressor+, EQ+, Delay+, Reverb,
  Peak Limiter, Tool, De-Esser, Gate, Saturator (`DISP_DEVICES` in deep.js; `device_units`). No device exposes gain reduction or meters:
  read those with `look_at_bitwig` (a window picture; Windows UI Automation finds nothing because Bitwig draws its own window).
- Grid editing (`grid_add_module`): proven to work with audio on effects Grids and Poly Grid. NEVER load an edited Polymer file: more than 19
  modules crashes the audio engine (tool refuses it). After any engine crash: Bitwig shows an 'Audio Engine Crashed' dialog; press Cancel (never
  Send Report), the crashed track must be deleted (manual: the auto-mode check blocks my click+Delete), then `engine_recover` clicks Activate Audio Engine.
- Evidence for all of this: `research/discoveries/FULL_LOG.md` and `CANDIDATES.md`.
- Music is original only: no copyrighted melodies. Keys/tempo are generic; do not assume a genre or 140 bpm.

## Working on the user's real song (learned 2026-10-05)
- ALWAYS check which project is open first (`get_session`: tempo/track names). The user can switch project tabs at any time; a test script once ran on the real song.
- `list_devices` / `device_delete` follow Bitwig's *selected* track, and `select_track` lags: after `select_track` wait ~1 s and check that `list_devices()['track']` is the expected name
  BEFORE any delete. A delete on track 18 once removed the Spire plug-in from track 15; fixed with `undo_redo` (11 steps) - undo is the safety net. Verify other tracks after every delete.
- Selecting a track auto-arms it (Bitwig default): restore arm afterwards (the song had only the Spire track armed).
- `masking_report` solos each track in turn for ~5.4 s while the song plays: valid for looping launcher clips only. In an arranger song every track is measured at a different place, so do not apply its fixes.
- Save a `snapshot` before changing a real song; never save the project file.

## Driving Bitwig's screen (`bwmcp/control/uidriver.py`, tools in `tools/uitools.py`)
Real screen grab (popups included) + offline OCR (rapidocr) + mouse/keyboard. NEVER type text unless the screen shows the field in edit mode (a darker
box): stray letters trigger Bitwig shortcuts (solo all, arm, metronome, space = play). Alt+click renames, right-click menus have DELETE, double-click shows devices.
After any UI experiment check `get_session` for stray solo/arm/metronome/playing and restore. Never press Send Report. FX tracks cannot be deleted by the API: use `delete_fx_track`.

## Genre handling
Presets are per genre and tempo-independent (`bwmcp/devices/genres.py`: release is a fraction of a beat). `sidechain_setup(genre=..., depth=...)`
reads the project tempo. Add a genre by adding one row to `GENRES` in `bwmcp/devices/genres.py`.

## Sidechain
`sidechain_setup` makes the trigger bus, the sends and the ducking Compressor+ on the targets. Still manual: pick the bus as
each compressor's sidechain source, lower the bus fader, rename the FX track. FX tracks left by tests cannot be deleted from
the API; ask the user to delete them.

## Before finishing a task
1. `python -m pyflakes bwmcp` and `python -c "import server"` (clean; the tool count in docs/TOOLS.md must match).
2. Test live where a project allows it; leave the project empty and tidy afterwards.
3. `python manage.py sync`, `python manage.py docs`, update `TODO.md` / `README.md`, commit, push.
