# Changelog

Connector version = the Python package (`bwmcp.__version__`). The Bitwig controller script has its own number (shown by `capabilities`).

## 7.7.1 - 2026-10-05 (script 6.1)
- Looked inside a community pack of curve-driven native devices (Caviio: CURVECOMP, WAVESHAPER, VOLSHAPER, SHAPER). They are NOT Grid patches: they use Bitwig 6.1's internal device
  format (own curve resources, UI definitions, custom device UUID), saved as `.bwdevice`, and Bitwig only accepts the custom UUIDs if `bitwig.jar` is patched or a native device is
  overwritten (the pack's install tools). We did not run those tools (they modify Bitwig and bypass its integrity check). So no Transfer/Curves module template can be taken from them.
- `grid_templates` / `grid_add_module` now also scan Bitwig's own Library and the user library for readable Grid presets (40 modules, was 37). Transfer/Curves/Wavetable-LFO templates still
  do not exist in any readable file on this machine (all 203 other module files are the scrambled version 0004).
- `.bwdevice` documents of this kind have a different root layout and a meta type 0x15 that `gridedit.dump` cannot write yet (reading works).

## 7.7.0 - 2026-10-04 (script 6.1)
- `device_manual`: the guide's text for any stock device, modulator or Grid module (local copy, 445 entries).
- `compressor_mode`: Compressor+ Character (Vanilla/Smooth/Over/Glue/Resist/Smash), VCA colour, Gain Reduction mode, Stereo Independence mode, Auto Timing %,
  Stereo Independence % - all checked live against Bitwig's display text (enum option i = i/(n-1); the two percentages are not linear, so they are found by display).
- Checked: Bitwig's own `Library/modules` and `modulators` files are the scrambled version 0004 (not a route); Compressor+ exposes 26 parameters that match the guide.
- A bulk "dump every device's parameters" script was tried and dropped: device_delete did not remove each probe device in the loop (left 10 test devices on Inst 1, cleaned up by hand).

## 7.6.0 - 2026-10-04 (script 6.1)
- Bitwig user guide (v5.3, 800+ sections) indexed locally: tools `manual_search`, `manual_section`, command `python manage.py manual <pdf>`; the text is never committed (copyrighted).
- `docs/BITWIG_MANUAL.md`: chapter map, Grid/voicing/signal facts, clip/bounce/operator facts, and ideas.
- `edit_action`: slice_in_place, slice_at_repeats, next_take, previous_take, toggle_groove, unwrap.

## 7.5.1 - 2026-10-04 (script 6.1)
- Modulators can target a parameter of a grid MODULE, not just the device: `grid_add_modulator(..., target='3/CUTOFF')` (full path CONTENTS/MODULES/3/CONTENTS/CUTOFF).
  PROVEN in a Poly Grid (Union -> ADSR -> added Low-pass, LFO on its cutoff): spectral centroid swept 1106 -> 1722 Hz over the chord clip; same patch without the mapping stays flat.
  Gotcha: `insert_file` needs an ABSOLUTE path (a relative one is refused).

## 7.5.0 - 2026-10-04 (script 6.1)
- Modulators PROVEN: an LFO added to a preset file and mapped to a Filter's cutoff swings the sound's centre by 431 Hz (30x the plain filter); on gain it swings the level 8.6 dB. The key
  was that a mapping's amount is in the parameter's own units (semitones, dB), as in Bitwig's Phaser preset. Tool `grid_add_modulator`.

## 7.4.2 - 2026-10-04 (script 6.1)
- `masking_fix` captures at least one full loop and reports a verdict (clash score before/after, per-cut measured level change). Live test: two clashing synths, -4 dB cut measured -3.3 dB, score 9.7 -> 7.6.

## 7.4.1 - 2026-10-04 (script 6.1)
- `select_arranger_clip`: clicks a clip in the Arrange view and reads its notes, so clips recorded by `record_arrangement` can be read and edited (the old limitation).

## 7.4.0 - 2026-10-04 (script 6.1)
- Layers and parallel chains: `device_insert(layer=N)` (insert into a layer of FX Layer / Instrument Layer), `add_layer` (clicks Bitwig's Add-layer gesture, the API cannot),
  `layer_chain` (build parallel chains with devices and library presets inside each layer), `parallel_compression`; `device_units` / the unit setter reach devices inside layers.
- Research: added modulators still show no audible effect in three measurement rounds (docs/PRESET_FORMAT.md 11.4).

## 7.3.0 - 2026-10-04 (script 6.1)
- Drives Bitwig's own screen (screen grab + offline OCR + mouse/keyboard): `sidechain_source` (choose a compressor's sidechain source by name, pre/post tap),
  `rename_fx_track`, `delete_fx_track`, `read_window_text`. `sidechain_setup` now builds the whole sidechain with no manual step (bus renamed, every compressor pointed at it).
- Proven with audio: with the sidechain compressor on, a 55 Hz bass swings 4.2 dB with the kick (0.7 dB with it off).
- Safety rules learned the hard way: typing only after the screen shows the name field in edit mode (stray keystrokes hit Bitwig shortcuts); Alt+click is Rename.
- 142 tools.

## 7.2.0 - 2026-10-04 (script 6.1)
- Audio pitch: `pitch_shift` (Pitch Shifter in real units) and `fix_tuning` (measure a track's tuning on the master recorder and correct it). Finding: the shifter only produces
  frequencies on a grid equal to its grain rate, so fine shifts need 1-2 Hz; measured 40 cents of detune corrected to -0.6 cents.
- Colour: `color_tracks` (roles, rainbow, gradient, mono, warm/cool, 12 named palettes), `color_clips`, `colour_schemes`.
- Device preset library: `device_presets`, `apply_device_preset`, `save_device_preset` (Reverb sized from the tempo, Compressor+, Saturator, De-Esser, Gate, Peak Limiter, Tool).
- Real-unit support for Pitch Shifter, Freq Shifter, Micro-pitch and Tuner; much faster unit setter (interpolation search).
- Reference library and `analyze_master` read MP3, FLAC and OGG (soundfile).
- The live remote as a desktop window: `python manage.py app` (pywebview), Start-menu shortcut with `--shortcut`.
- Transposition actions in `edit_action`.
- 142 tools, 125 live checks, offline tests for voicings and the preset library (values checked against probed device ranges, `data/device_ranges.json`).

## 7.1.0 - 2026-10-04 (script 6.1)
- Chords and voicings: 44 chord qualities, 20 voicing styles (drop 2/3, shell, rootless A/B, quartal, So What, upper-structure, neo-soul, supersaw, ...), genre suggestions,
  voice-led progressions. Tools `chord_library`, `suggest_voicing`, `chord_voicings`, `write_voiced_chords`; offline tests; docs/CHORDS_AND_VOICINGS.md.
- 142 tools.

## 7.0.0 - 2026-10-04 (script 6.1)
- Package reorganised into `bwmcp/` (tools by topic, helpers by area), `manage.py` front door, `data/`, `docs/`, `scripts/`.
- Master recorder as the live capture source, API level 25, project state / notes / UI layout / undo / window picture / project file report, device units, edit actions.
- Genre-aware sidechain (17 genres), Compressor+ in real units, Compressors card in the live monitor.
- Grid patch editing (`grid_*` tools): added modules proven with audio on effects Grids and Poly Grid; Polymer limit found (19 modules).
- Automatic crash recovery (`manage.py recover`, `engine_recover`).
- 142 tools, 120 live checks.

## 6.0.0 - 2026-10-03 (script 6.0)
- MIDI files, reference library, masking finder, Bitwig actions, automation by performance, arranger clips (102 tools).
- Deep device access: nested chains, every parameter, EQ+ in real units, mid/side EQ, mix audit, recipes, A/B test, insert by UUID, preset patching.
- One-step installer, grouping fix, backups.

## 1.0.0 - 2026-10-01 (script 1.0-5.x)
- First connector: controller script + MCP server, music generation, expert note editing, sounds and samples, mastering analysis, live monitor with autostart.
