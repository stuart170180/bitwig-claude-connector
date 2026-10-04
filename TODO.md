# To do

Connector v7.5.0 (142 tools, controller script 6.1). Repo: private GitHub `stuart170180/bitwig-claude-connector`. History: [CHANGELOG.md](CHANGELOG.md).
Updated 2026-10-04.

## Overnight plan (autonomous, with the user's full permission to drive Bitwig with the mouse)
- [ ] Update the portfolio with version numbers at every milestone (v7.0.0 done on 2026-10-04).
- [x] Chords and voicings engine and tools (v7.1.0). [ ] still to do: show them in the live remote.
- [x] Audio pitch controls and colour controls (v7.2.0).
- [x] Preset library: reverb, Delay+, compressor, saturator, de-esser, gate, limiter, pitch shifter, tool (v7.2.0).
- [x] Live remote as a desktop window: `python manage.py app` (v7.2.0). [ ] A real VST/CLAP plugin would need a C++ toolchain (JUCE); not started.
- [ ] Work through the build list below.

## Needs the user's song (needs a real project open)
- [ ] Reopen the song project (the open project is an empty "New 1").
- [ ] Group the song's tracks with `group_tracks`, then bus compressors on the groups.
- [ ] Run `mix_audit`, master `mid_side_eq`, `masking_report` / `masking_fix`, `perform_ramp` builds, save chains with `recipe`.
- [ ] Try plugin control on Serum and Spire with `deep_params` / `deep_set`.
- [ ] Test `edit_action` (consolidate, normalize, quantize audio, stretch, bounce) on a selected arranger clip; `undo_redo`; `last_clicked`; look at `project_notes` in Bitwig's controller settings.
- [ ] Tune the genre sidechain presets by ear (`genres.py`).
- [ ] Share the portfolio page from its Share menu if other people should see it (it is private).

## Build
- [x] Sidechain source and FX track names/deletion by driving the UI (v7.3.0). [ ] FX track fader (pull the bus down) not done: the tap is pre-fader so ducking is unaffected.
- [ ] Why Polymer cannot take a 20th module (Poly Grid takes 32). Decisive test: a module added in Bitwig's own UI, saved, diffed against the factory file.
- [x] Modulators PROVEN with audio (v7.5.0): amounts are in the parameter's own units; `grid_add_modulator`.
- [x] Arranger clips recorded by `record_arrangement` can be selected and read: `select_arranger_clip` (v7.4.1).
- [ ] Real-unit presets for more devices; gain reduction has no API parameter (read it from a picture).
- [x] Parallel compression and layer chains (v7.4.0: `layer_chain`, `parallel_compression`, `add_layer`).
- [x] Reference library decodes MP3, FLAC and OGG (soundfile).
- [x] `masking_fix` verifies its own improvement (v7.4.2). [ ] confirm bounce / consolidate / normalize worked.
- [ ] PopupBrowser (browser-based preset loading) and the project file's track tree.

## Done
- [x] v7.0.0: package reorganised, installer, `manage.py`, `CLAUDE.md`, docs.
- [x] Genre-aware sidechain, Compressor+ in real units, Compressors card in the live monitor.
- [x] Master recorder capture, API 25, project state / notes / UI layout / undo / window picture / project file report, device units, edit actions.
- [x] Grid editing: added modules proven with audio (effects Grid, Poly Grid), `grid_*` tools, Polymer 19-module limit found.
- [x] Crash recovery: `manage.py recover` / `engine_recover` (cancel dialog, delete crashed track, reactivate).
- [x] Grouping fixed; deep device access, EQ+ in real units, mid/side EQ, mix audit, recipes, A/B; MIDI files, reference library, masking finder, actions, automation by performance.
- [x] Backups, git history, private GitHub repo, portfolio page.
