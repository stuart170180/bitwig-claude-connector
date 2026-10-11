# Bitwig API coverage (2026-10-11)

Source: the controller-API documentation that ships with Bitwig (`resources/doc/control-surface/api`, 170 interfaces, 1,463 methods) and the bundled
open controller scripts. Public documentation only: nothing from the licensing or copy-protection side was looked at.
`python scripts/api_coverage.py` lists, per interface, the documented method names the connector's script does not call. The count is a guide, not a score:
the script reaches some methods through computed names (arranger / mixer toggles), and most of the unused ones are for hardware surfaces (`HardwareSurface`,
`MidiIn`, matchers, lights) which a software connector does not need.

## Taken from this pass (v9.2.0)
- `InsertionPoint.insertVST3Device / insertCLAPDevice / insertVST2Device`: **tool `insert_plugin_by_id`**. Loads a plug-in straight through the API; the old
  `insert_plugin` clicked hard-coded screen positions and read the screen with OCR. VST3 ids come from each plug-in's own `moduleinfo.json`.
  Tested live: BW True Peak on a track and BW Remote on the master, both then removed.
- `Project.unsoloAll / unarmAll / unmuteAll`: **tool `reset_track_states`** (selecting a track in Bitwig arms it, so every test needed a manual clean-up).
- `Project.createSceneFromPlayingLauncherClips`: **tool `scene_from_playing_clips`**.

## Already used (earlier explorations, research/discoveries)
Project name / modified state, arranger and mixer section visibility, master recorder, last-clicked parameter, transport extras (punch, pre-roll, loop), undo / redo,
project notes via the document state, specific-device parameters for real units, insert by Bitwig device UUID.

- `Project.createSceneFromPlayingLauncherClips` is covered by `scene_from_playing_clips`.
- v9.3.0: `masking_live` uses `insert_plugin_by_id` to put BW Remote probes on every track. A dedicated lighter plug-in (telemetry only, no shared audio ring file) would be a cleaner probe if more than ~8 are used at once.

## Still open
- **Bitwig's own browser** (`PopupBrowser`, `BrowsingSession`, `Browser*ColumnBank`): browse, filter by creator / category / tag, audition and commit presets, samples and devices
  from Bitwig's library (including favourites and tags), instead of indexing files. Objects create at init but have not been driven; it opens Bitwig's browser UI
  on screen, so it needs care (always cancel / commit). Biggest remaining gain.
- **Observers for live state**: clip-launcher slot states (playing / queued / recording), `Channel.playingNotes`, transport state callbacks. These would let the app show a live
  clip grid and playing notes without polling.
- `ClipLauncherSlot.duplicateClip`, `ClipLauncherSlotBank.deleteClip / duplicateClip`: native clip duplicate.
- `Arpeggiator` and `NoteInput` settings, `Track.monitorMode / sourceSelector` (partly explored), `Settings` (preferences panel for the script inside Bitwig).
- Not available: sidechain source choice, FX-track fader / name, gain-reduction meters (see CLAUDE.md).
