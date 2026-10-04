# To do

Last updated 2026-10-04. Connector: 106 tools, controller script 6.0. Repo: private GitHub `stuart170180/bitwig-claude-connector`.

## Needs you (Bitwig)
- [ ] Reopen your song project in Bitwig. The open project is an empty "New 1"; everything below that touches your mix needs the song.
- [x] Grouping fixed: `group_tracks` / `ungroup_track` now switch to the ARRANGE layout and focus the track header automatically.
- [ ] Group the song's tracks with `group_tracks`, then ask for bus compressors on the new groups.
- [ ] Share the portfolio page from its Share menu if other people should see it (it is private).
- [ ] Confirm the live monitor starts by itself at your next Windows login (`python autostart.py --status`).

## Next, on your song
- [ ] Run `mix_audit` and let it fix EQ+ bands that have a gain but type Off (earlier EQ moves may have done nothing).
- [ ] Add the master `mid_side_eq` (low-cut on the Side, a little air) and re-measure with `analyze_master`.
- [ ] Run `masking_report` with a capture at least one loop long, then `masking_fix` if the clashes are real.
- [ ] Try `perform_ramp` for builds (strings volume, filter rise) and check the lanes in the Arrange view.
- [ ] Save your good chains with `recipe` (vocal chain, master chain) so they can be rebuilt.
- [ ] Try plugin control on Serum and Spire by parameter name with `deep_params` / `deep_set`.

## Build
- [ ] Arranger clips: point `get_arranger_clip_notes` at the clip `record_arrangement` recorded (unsolved; works on a clip you select by hand).
- [ ] Real-unit mappings for more Bitwig devices (Compressor, Filter, Delay+), as `eq_set` does for EQ+.
- [ ] Parallel compression and layer chains (needs a way to add layers to FX Layer from a script).
- [ ] Grid and modulators: isolate the engine crash from `D5_polymer_insert_lowpass.bwpreset` on a fresh track (with your OK), then prove an added module works with audio.
- [ ] Reference library: decode MP3 and FLAC (no decoder installed) and add full songs as references, not loops.
- [ ] Make `masking_fix` verify its improvement (captures cover a full loop; per-fix level change).
- [ ] Bounce in place / consolidate / normalize: find a way to confirm they worked.

## Done
- [x] Bitwig controller script and Python MCP server: 102 tools, 105 live checks passing
- [x] Music generation, expert note editing, sounds, samples, bookmarks, auto-naming
- [x] Mastering analysis (LUFS, true peak, mid/side), live monitor web page, tuner, UK time and weather
- [x] Deep device access, EQ+ in real units, mid/side EQ, mix audit, recipes, A/B test
- [x] Insert devices by UUID, preset inspect and patch, preset file parser (396 of 396 round trip)
- [x] MIDI file import/export, reference library, masking finder, Bitwig actions, automation by performance
- [x] Arranger clip reading for a selected clip; tracks return to the arrangement after recording
- [x] Backups, git history, private GitHub repo, portfolio page
- [ ] Sidechain: `sidechain_setup` builds the trigger bus, sends and ducking compressors. Still manual (not in the API): pick the bus as each Compressor+'s sidechain source, lower the bus fader, rename the FX track. Idea: patch the source into a preset (risky, see docs/PRESET_FORMAT.md).
- [ ] Compressor+ gain reduction has no API parameter (checked 10 guessed names); other devices' display text only works for Compressor+ and EQ+ (add their UUID + parameter ids to DISP_DEVICES in deep.js to extend).
- [ ] Sidechain presets are starting points per genre (`genres.py`); tune by ear on a real song and adjust the rows.
- [x] Repo reorganised into the `bwmcp/` package (tools by topic, helpers by area), `manage.py` front door, `data/`, `docs/`, `scripts/`.
