# CANDIDATES - features worth implementing (ranked within theme)

The run was cut short: Bitwig crashed at experiment E12 (Signal.fire() from the script) and the coordinator stopped live work.
Evidence links point to FULL_LOG.md entries. PROVEN = worked live; LIKELY = API exists in bitwig.jar (api_surface.json), untested; BLOCKED = not possible or dangerous.

## A. Cheap, high value (PROVEN)
1. **Master output recorder to WAV** - PROVEN (E8). `host.createMasterRecorder()` (needs `loadAPI(20+)`), methods `start/stop/toggle/isActive/duration`. Writes a 24-bit 44.1k stereo WAV into the project's `master-recordings` folder (temp-projects\<guid>\ for an unsaved project). Gives loudness/spectrum analysis, A/B and reference comparison without WASAPI loopback, with exact timing and no driver dependency. Effort S-M (script: init + 3 commands; Python: find newest file, feed the existing analysis). Risk low. Needs markInterested on isActive/duration in init.
2. **Raise `loadAPI(17)` to `loadAPI(25)`** - PROVEN (E7). One-line change; host reports API 25 (max for Bitwig 6.1; higher values are clamped). Unlocks API 18-25 objects. Effort S; risk low-medium (run tests/live_test.py after).
3. **Show/hide UI sections and read state** - PROVEN (E2-E6): Arranger (cue marker lane, playback follow, launcher, IO, FX tracks visible), Mixer (meter, crossfade, IO, device, sends sections), project name, canUndo/canRedo, panel layout, display profile, `Project.hasSoloedTracks/hasMutedTracks/hasArmedTracks` (quick flag check for mix_audit). Effort S; risk low.
4. **Project-persistent notes and user-to-Claude settings** - PROVEN on the script side (E11): `DocumentState` string/number/enum settings are stored in the project; `Preferences` settings are global. Use as Claude's per-project notebook (genre, targets, snapshots) and as a "tell Claude" field the user edits in Controller settings. Effort M. Risk low if Signals are only observed. How they look in the UI and the user-to-script observer path are not yet verified.

## B. LIKELY (API exists, untested)
5. **Last clicked parameter** (E9/E10): `createLastClickedParameter` gives name/value/display of whatever the user last touched ("what is this knob", "automate the thing I just touched"). Created fine at API 25; needs a user click to verify. S-M.
6. **Transport extras**: punch in/out, pre-roll, loop start/duration, post-recording action, time signature, cue-marker jumps, `playPositionInSeconds`, tap tempo, `Project.createSceneFromPlayingLauncherClips`, `unmuteAll/unsoloAll/unarmAll`, `cueMix/cueVolume`. Reads proven in E10; setters untested. S.
7. **Track routing/monitor**: `sourceSelector()` (has-audio/note input selected; the API does not expose choosing the input), `monitorMode`, `createParentTrack`, `recordNewLauncherClip`, `playNote/startNote/stopNote` (audition notes without clips). Several markInterested calls on bank tracks failed (E10), so retest on the cursor track. M.
8. **PopupBrowser / Browser sessions**: columns (category, creator, tag, device, location, results), select/commit, audition. Could replace file-based preset loading with real browser use. Objects were created at init but not exercised. M-L; medium risk (UI popup state).
9. **Device preset browsing and structure**: `switchToNext/PreviousPreset`, `presetCategory/Creator` (init-time markInterested), `createChainSelector`, `createDrumPadBank`, `createCursorLayer` for layers and drum pads. M.
10. **Application navigation**: zoom, panel focus, undo/redo state, `recordQuantizationGrid`, arrow/enter/escape key simulation. S-M; key simulation acts on whatever is focused, so risky.
11. **More display units**: `DISP_DEVICES` in deep.js accepts any UUID plus parameter ids, so the Compressor+/EQ+ pattern extends to Delay+, Reverb, Filter+, Limiter etc. (UUIDs: research/device_uuids.json; ids from `deep_params`). Created at script start only, so a fixed list. Not tested live. M.
12. **Actions not yet wrapped** (E14): consolidate, bounce in place (pre-FX/pre-fader/post-fader), quantize audio/length/to key, normalize, fades, stretch to project tempo / detect tempo, reverse, zoom to fit, loop selected region, duplicate as alias, comping take select, DAWproject/MIDI export. All through run_bitwig_action; they need a selected arranger clip or track; the deny-list still applies. S each.
13. **UserControls, UDP datagrams, MidiOut, HardwareSurface**: `createUserControls` (8 controls readable, E10), `sendDatagramPacket/addDatagramPacketObserver` (talk to other software), `MidiOut` (needs defineMidiPorts > 0, which changes the controller definition). M-L.

## C. Areas requested by the user (second pass)
### C1 Windows UI inspection (E15, E18)
- UI Automation / child windows: **BLOCKED** (custom-drawn window, 0 UIA elements; pywinauto/comtypes installed with pip for the test).
- **Screenshot of the window via PrintWindow: PROVEN, read-only.** Lets Claude read FX track names/faders, sidechain dropdown text, device displays and meters as an image. Candidate: `look_at_bitwig` tool (S, risk low, saves PNG, Claude views it). Window title also gives project name and dirty flag ("New 1*").
- Clicking/typing into the UI (to pick a sidechain source, rename an FX track): LIKELY possible with synthetic mouse + screenshot verification, but untested, fragile (layout/zoom/DPI dependent) and can alter the project. Effort L, risk high.
### C2 Sidechain / routing (E19)
- **BLOCKED** in the API (only read-only SourceSelector getters). Only route: UI clicks (C1) or user does it by hand.
### C3 Project/preset/settings files (E16, E17)
- **PROVEN** read-only: .bwproject strings give tracks, plugin names, stock devices, sample paths, version, parameter ids. Candidate: `project_file_report` (offline, any project, missing-sample check, plugin inventory, disk-hygiene: `master-recordings` of one project holds 3.6 GB, bounce folders). Effort M (use research/bwformat.py for a proper parse), risk low (read only; copy before reading large files).
- DAWproject export: **LIKELY** (action `Project:export_project` opens a dialog, so user must complete it); a DAWproject zip reader is easy and gives clean XML of tracks/devices/clips.
### C4 Stock device display and meters (E20)
- Ids for Delay+, Reverb, Peak Limiter, Tool, De-Esser, Gate, Saturator recorded in ids.txt: **LIKELY** usable with `createSpecificBitwigDevice(uuid).createParameter(id)` in `DISP_DEVICES` (not wired/tested). Gain reduction / meters: **BLOCKED** (no parameter for them; UI-only, readable by screenshot).
### C5 PopupBrowser (E21)
- **LIKELY**, partial: objects create; not exercised.

## D0. Other not investigated

- FX-track rename/fader: UI only (screenshot can read them).

## D. BLOCKED / DANGEROUS
- **Signal.fire() from a script CRASHES Bitwig** (E12): `IllegalStateException: This signal cannot be invoked`. Signals from `getSignalSetting` are user-to-script only. Never call.
- `Device.getMacro()` and `getModulationSource()` are deprecated since API 2 and throw; use remote controls.
- `markInterested()` works only in init: every new readable value needs a script edit and reload.
- `createMasterRecorder` / `createLastClickedParameter` throw below API 20 (fixed by item 2).
- `getMidiInPort(0)` fails because the script defines 0 MIDI ports.
- `Track.crossFadeMode`, `isPreFader`, `monitor`, `autoMonitor`, `canHoldAudioData` markInterested fail on bank/cursor tracks ("Message not supported", E10).

## Housekeeping
- Live controller folder restored; `manage.py sync --check` = in sync. Backups in research/discoveries/backup/. Throw-away tools: enum_api.py (+ api_surface.json, api_unused.json), probe.js, probe2.js, px.py.
- After the Bitwig restart the open project holds the user's "Inst 1" and "Audio 2" (untouched), not the empty "New 1".
