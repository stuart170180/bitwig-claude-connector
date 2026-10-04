# Changelog

Connector version = the Python package (`bwmcp.__version__`). The Bitwig controller script has its own number (shown by `capabilities`).

## 7.1.0 - 2026-10-04 (script 6.1)
- Chords and voicings: 44 chord qualities, 20 voicing styles (drop 2/3, shell, rootless A/B, quartal, So What, upper-structure, neo-soul, supersaw, ...), genre suggestions,
  voice-led progressions. Tools `chord_library`, `suggest_voicing`, `chord_voicings`, `write_voiced_chords`; offline tests; docs/CHORDS_AND_VOICINGS.md.
- 125 tools.

## 7.0.0 - 2026-10-04 (script 6.1)
- Package reorganised into `bwmcp/` (tools by topic, helpers by area), `manage.py` front door, `data/`, `docs/`, `scripts/`.
- Master recorder as the live capture source, API level 25, project state / notes / UI layout / undo / window picture / project file report, device units, edit actions.
- Genre-aware sidechain (17 genres), Compressor+ in real units, Compressors card in the live monitor.
- Grid patch editing (`grid_*` tools): added modules proven with audio on effects Grids and Poly Grid; Polymer limit found (19 modules).
- Automatic crash recovery (`manage.py recover`, `engine_recover`).
- 121 tools, 120 live checks.

## 6.0.0 - 2026-10-03 (script 6.0)
- MIDI files, reference library, masking finder, Bitwig actions, automation by performance, arranger clips (102 tools).
- Deep device access: nested chains, every parameter, EQ+ in real units, mid/side EQ, mix audit, recipes, A/B test, insert by UUID, preset patching.
- One-step installer, grouping fix, backups.

## 1.0.0 - 2026-10-01 (script 1.0-5.x)
- First connector: controller script + MCP server, music generation, expert note editing, sounds and samples, mastering analysis, live monitor with autostart.
