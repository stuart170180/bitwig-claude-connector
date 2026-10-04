# Claude <-> Bitwig Studio connector

A Bitwig controller script (JavaScript) plus a Python MCP server. Claude drives Bitwig through MCP tools. Owner: S.Simpson
(GitHub `stuart170180`, Windows 11). Private repo `stuart170180/bitwig-claude-connector`, branch `main`.
Full docs: `README.md` (overview, install, known limits), `TOOLS.md` (generated tool list), `TODO.md` (open work).

## How to work with this user
- Do not ask questions; take their answers as yes and carry on. Pick a sensible default and say what you chose.
- Commit and push is pre-approved after each finished piece of work. Co-author line as the system reminder gives it.
- After every piece of work update `TODO.md`, and `README.md` / `TOOLS.md` when tools change (`python make_docs.py`).
- Use workers (subagents) only when asked. Say what you are doing during long steps.
- Report honestly: say what was tested live and what was not.

## Layout
- `server.py` MCP server (MCP SDK v2, own `@tool()` decorator). **New tools go ABOVE the `if __name__ == "__main__"` block**,
  and into a group in `make_docs.py` (the GROUPS list), then run `python make_docs.py`.
- Helper modules: `deepdev.py` (nested devices, EQ, insert by UUID), `compdev.py` (Compressor+ in real units), `genres.py`
  (sidechain genre presets), `audit.py`, `recipes.py`, `presetpatch.py`, `midifile.py`, `reflib.py`, `masking.py`,
  `actionsdev.py`, `performdev.py`, `arrclipsdev.py`, `paths.py` (folders, OneDrive-safe), `install.py`, `live_monitor.py/.html`.
- `bitwig_script/` is the git copy of the controller script. The live copy Bitwig loads is in
  `Documents\Bitwig Studio\Controller Scripts\BitwigMCP\`. Edit the live copy, then `python sync_script.py` before committing
  (`--install` goes the other way). Bitwig reloads the script about 5 s after a file changes.
- `tests/`: `live_test.py` (needs Bitwig running with a project), plus offline `test_*.py`.
- `research/`: notes and experiments (preset format, modulators/Grid, features). `recipes/`, `snapshots/`: saved data.

## Protocol
Python sends OSC `/mcp "<json>"` to Bitwig on UDP 8765; replies come back as `/reply` on ports 8766-8771. Call from Python
with `server.bw.call("<command>", **args)`. Live monitor: `python live_monitor.py` on http://127.0.0.1:8780 (autostart:
`python autostart.py`).

## Hard-won rules (do not rediscover)
- The Bitwig API has no access to: modulators, Grid, sidechain source choice, FX track names/faders, compressor gain
  reduction. Do not promise these. Direct parameters are not recordable; use remote controls for automation recording.
- Direct-parameter display text never arrives. Real units (ms, dB, 1:N) come from `createSpecificBitwigDevice` parameter
  objects, which can only be created at script start (`DISP_DEVICES` in `deep.js`). Done for Compressor+ and EQ+.
- `setDirectParameterValueNormalized(id, value*16384, 16384)`: pass value in 0..resolution, not 0..1.
- A fresh EQ+ has all bands Off; set types explicitly (`eq_set`). Mid/side EQ gain = 0.5 + dB/48.
- Grouping works only with the ARRANGE layout showing and the track header focused; `group_tracks` does both itself.
- `get_clip_notes` right after a write can return 0; wait or use `read_clip_settled`. Call `transport.returnToArrangement()`
  after launching clips (record_arrangement does).
- Preset files: container "BtWg00030002" parses and round-trips; same-length patches work, length-changing edits are
  unproven and one edited Grid file crashed the audio engine. Never load experimental patched presets into a real project.
- Parallel workers that each build tracks will wipe each other's project. Run live Bitwig tests one at a time.
- Audio analysis: BS.1770 LUFS, true peak, mid/side; capture needs Windows Audio (WASAPI) driver in Bitwig.
- Music is original only: no copyrighted melodies. Keys/tempo are generic; do not assume a genre or 140 bpm.

## Genre handling
Presets are per genre and tempo-independent (`genres.py`: release is a fraction of a beat). `sidechain_setup(genre=..., depth=...)`
reads the project tempo. Add a genre by adding one row to `GENRES`.

## Sidechain
`sidechain_setup` makes the trigger bus, the sends and the ducking Compressor+ on the targets. Still manual: pick the bus as
each compressor's sidechain source, lower the bus fader, rename the FX track. FX tracks left by tests cannot be deleted from
the API; ask the user to delete them.

## Before finishing a task
1. `python -c "import server"` (imports clean, no tool after `mcp.run()`).
2. Test live where a project allows it; leave the project empty and tidy afterwards.
3. `python sync_script.py`, `python make_docs.py`, update `TODO.md` / `README.md`, commit, push.
