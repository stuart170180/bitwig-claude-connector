# To do

Connector v8.3.0 (152 tools, controller script 6.1). Repo: private GitHub `stuart170180/bitwig-claude-connector`. History: [CHANGELOG.md](CHANGELOG.md).
Updated 2026-10-05.

## Overnight plan (autonomous, with the user's full permission to drive Bitwig with the mouse)
- [ ] Update the portfolio with version numbers at every milestone (v7.0.0 done on 2026-10-04).
- [x] Chords and voicings engine and tools (v7.1.0). Shown in the live remote (Chords & voicings card).
- [x] Audio pitch controls and colour controls (v7.2.0).
- [x] Preset library: reverb, Delay+, compressor, saturator, de-esser, gate, limiter, pitch shifter, tool (v7.2.0).
- [x] Live remote as a desktop window: `python manage.py app` (v7.2.0). [ ] A real VST/CLAP plugin would need a C++ toolchain (JUCE); not started.
- [ ] Work through the build list below.

## VST3 (v8.0.0, docs/VST.md)
- [x] BW Remote VST3 64-bit built, on the real song's master, audio + meters reach the live monitor / desktop app / analysis tools; API key per instance.
- [ ] CLAP build (clap-juce-extensions); VST2 is not possible (SDK no longer licensed).
- [x] VST meters/spectrum card in the live monitor page (and so in the desktop app): v8.3.0.
- [x] True-peak limiter on the master: BW True Peak VST3 + `true_peak_limiter` (v8.3.0).

## Added 2026-10-05
- [x] Bitwig user guide indexed (`manual_search`, `device_manual`), `docs/BITWIG_MANUAL.md`; `compressor_mode`; Transfer/Curve/Curves/Wavetable LFO/Clock Grid modules (template built in Bitwig by the UI driver, proven with audio).
- [ ] Drive Bounce / Slice dialogs with the UI driver; set Poly Grid Note Source / Auto-gate for audio tracks; automate master groove/tempo.

## Needs the user's song (needs a real project open)
- [ ] Reopen the song project (the open project is an empty "New 1").
- [ ] Group the song's tracks with `group_tracks`, then bus compressors on the groups.
- [ ] Run `mix_audit`, master `mid_side_eq`, `masking_report` / `masking_fix`, `perform_ramp` builds, save chains with `recipe`.
- [ ] Try plugin control on Serum and Spire with `deep_params` / `deep_set`.
- [ ] Test `edit_action` (quantize audio, stretch; bounce and normalize are done) on a selected arranger clip; `undo_redo`; `last_clicked`; look at `project_notes` in Bitwig's controller settings.
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
- [x] `masking_fix` verifies its own improvement (v7.4.2). bounce_in_place (note clip -> audio clip, track became Hybrid) and normalize (+9.2 dB clip gain) CONFIRMED live on 2026-10-05; consolidate and reverse ran without error but a changed result could not be seen on a one-pass clip.
- [ ] PopupBrowser (browser-based preset loading) and the project file's track tree.

## Done
- [x] v7.0.0: package reorganised, installer, `manage.py`, `CLAUDE.md`, docs.
- [x] Genre-aware sidechain, Compressor+ in real units, Compressors card in the live monitor.
- [x] Master recorder capture, API 25, project state / notes / UI layout / undo / window picture / project file report, device units, edit actions.
- [x] Grid editing: added modules proven with audio (effects Grid, Poly Grid), `grid_*` tools, Polymer 19-module limit found.
- [x] Crash recovery: `manage.py recover` / `engine_recover` (cancel dialog, delete crashed track, reactivate).
- [x] Grouping fixed; deep device access, EQ+ in real units, mid/side EQ, mix audit, recipes, A/B; MIDI files, reference library, masking finder, actions, automation by performance.
- [x] Backups, git history, private GitHub repo, portfolio page.
- [x] v8.4.0: packager for the desktop app (PyInstaller exe + Inno Setup installer). Not yet done: code signing, installer run-through on a clean PC.
