# FULL LOG - Bitwig connector discovery run (2026-10-04)

Chronological. Tools: `enum_api.py` (class-file parser), `probe.js` (temporary controller-script probe, loaded from the live script
during the run and removed afterwards), `px.py` (python harness; logs below were appended by it or by hand).
Entries: Verdict = worked / failed / partial.

### E0 Enumerate API surface from bitwig.jar
- Verdict: **worked**
- Code: `enum_api.py` parses constant pools + method tables of every class in com/bitwig/extension/controller/api (zipfile + struct, no javap).
- Result: 210 classes, 1485 distinct method names (`api_surface.json`). Diff against names called anywhere in bitwig_script/*.js: 161 classes have
  unused methods, 1151 unused method names (`api_unused.json`, name-level match so it over-counts "used"; a method name used on one class hides it on others).
- Learned: Big unused areas: Application (undo/redo state, zoom, project name, panel focus), Arranger/Mixer visibility toggles, Project (cueMix, hasSoloed/Muted/Armed, unarm/unmute/unsolo all, createScene*),
  PopupBrowser (full browser columns), Browser sessions, Track (sourceSelector, monitorMode, crossFadeMode, playNote/startNote/stopNote, createParentTrack, recordNewLauncherClip),
  Transport (punch, preRoll, postRecordingAction, cue marker jumps, loop range, time signature), Device (preset browsing, macros, modulation sources, getEnvelopeParameter, createSpecificVst2/3Device, createChainSelector),
  NoteInput (arpeggiator, noteLatch, expressive midi), HardwareSurface, MidiOut, ControllerHost (UDP datagram, remote connection, createMasterRecorder, createLastClickedParameter).

### E1 Probe harness installed
- Verdict: **worked**
- Code: backup of live scripts in research/discoveries/backup/; added `load("probe.js")`, `initProbe()` and a `handleProbe` fallback to the LIVE BitwigMCP.control.js (restored at the end). New commands: px_eval, px_err, px_methods.
- Result: reload in <10 s; `px_err` shows which init-time objects failed: lastclicked + recorder need API >= 20 (script uses loadAPI(17)); `getMidiInPort(0)` invalid because defineMidiPorts(0,0).
- Learned: `eval` in script scope works, so arbitrary read-only API calls can be tested with `px_eval`.

### E2 app project name
- Verdict: **worked**
- Call/code: `application.projectName().get()`
- Result: `New 1`

### E2b undo/redo state
- Verdict: **worked**
- Call/code: `[application.canUndo().get(), application.canRedo().get()]`
- Result: `[True, False]`

### E2c panel layout/profile
- Verdict: **worked**
- Call/code: `[application.panelLayout().get(), application.displayProfile().get(), application.hasActiveEngine().get()]`
- Result: `['ARRANGE', 'Single Display (Large)', True]`

### E3 arranger visibility
- Verdict: **worked**
- Call/code: `['dbl',PX.arranger.hasDoubleRowTrackHeight().get(),'launcher',PX.arranger.isClipLauncherVisible().get(),'timeline',PX.arranger.isTimelineVisible().get(),'io',PX.arranger.isIoSectionVisible().get(),'fx',PX.arranger.areEffectTracksVisible().get(),'follow',PX.arranger.isPlaybackFollowEnabled().get(),'cues',PX.arranger.areCueMarkersVisible().get()]`
- Result: `['dbl', False, 'launcher', True, 'timeline', True, 'io', False, 'fx', True, 'follow', True, 'cues', False]`

### E4 mixer visibility
- Verdict: **worked**
- Call/code: `[PX.mixer.isClipLauncherSectionVisible().get(),PX.mixer.isCrossFadeSectionVisible().get(),PX.mixer.isDeviceSectionVisible().get(),PX.mixer.isIoSectionVisible().get(),PX.mixer.isMeterSectionVisible().get(),PX.mixer.isSendSectionVisible().get()]`
- Result: `[True, False, True, True, False, True]`

### E5 project flags
- Verdict: **worked**
- Call/code: `[PX.project.hasSoloedTracks().get(),PX.project.hasMutedTracks().get(),PX.project.hasArmedTracks().get()]`
- Result: `[False, False, False]`

### E6 project name via project
- Verdict: **worked**
- Call/code: `PX.project.getName ? 1:0`
- Result: `0`

### E7 px_methods popup
- Verdict: **worked**
- Call/code: `Object.keys(PX.popup).length`
- Result: `91`

### A1 arranger IO section toggle
- Verdict: **worked**
- Call/code: `PX.arranger.toggleIoSection ? PX.arranger.toggleIoSection():'x'`
- Result: `x`

### A1 arranger IO section toggle back
- Verdict: **worked**
- Call/code: `PX.arranger.toggleIoSection ? PX.arranger.toggleIoSection():'x'`
- Result: `x`

### A1 arranger IO section RESULT
- Verdict: **partial/no-change**
- Call/code: `PX.arranger.toggleIoSection ? PX.arranger.toggleIoSection():'x' / PX.arranger.isIoSectionVisible().get()`
- Result: `[False, False, False]`
- Learned: before,after,restored

### A2 arranger double row toggle
- Verdict: **worked**
- Call/code: `PX.arranger.toggleTrackRowHeight()`
- Result: `None`

### A2 arranger double row toggle back
- Verdict: **worked**
- Call/code: `PX.arranger.toggleTrackRowHeight()`
- Result: `None`

### A2 arranger double row RESULT
- Verdict: **partial/no-change**
- Call/code: `PX.arranger.toggleTrackRowHeight() / PX.arranger.hasDoubleRowTrackHeight().get()`
- Result: `[False, False, False]`
- Learned: before,after,restored

### A3 arranger cue markers toggle
- Verdict: **worked**
- Call/code: `PX.arranger.toggleCueMarkerVisibility()`
- Result: `None`

### A3 arranger cue markers toggle back
- Verdict: **worked**
- Call/code: `PX.arranger.toggleCueMarkerVisibility()`
- Result: `None`

### A3 arranger cue markers RESULT
- Verdict: **worked**
- Call/code: `PX.arranger.toggleCueMarkerVisibility() / PX.arranger.areCueMarkersVisible().get()`
- Result: `[False, True, False]`
- Learned: before,after,restored

### A4 playback follow toggle
- Verdict: **worked**
- Call/code: `PX.arranger.togglePlaybackFollow()`
- Result: `None`

### A4 playback follow toggle back
- Verdict: **worked**
- Call/code: `PX.arranger.togglePlaybackFollow()`
- Result: `None`

### A4 playback follow RESULT
- Verdict: **worked**
- Call/code: `PX.arranger.togglePlaybackFollow() / PX.arranger.isPlaybackFollowEnabled().get()`
- Result: `[True, False, True]`
- Learned: before,after,restored

### A5 mixer meter section toggle
- Verdict: **worked**
- Call/code: `PX.mixer.toggleMeterSectionVisibility()`
- Result: `None`

### A5 mixer meter section toggle back
- Verdict: **worked**
- Call/code: `PX.mixer.toggleMeterSectionVisibility()`
- Result: `None`

### A5 mixer meter section RESULT
- Verdict: **worked**
- Call/code: `PX.mixer.toggleMeterSectionVisibility() / PX.mixer.isMeterSectionVisible().get()`
- Result: `[False, True, False]`
- Learned: before,after,restored

### A6 mixer crossfade section toggle
- Verdict: **worked**
- Call/code: `PX.mixer.toggleCrossFadeSectionVisibility()`
- Result: `None`

### A6 mixer crossfade section toggle back
- Verdict: **worked**
- Call/code: `PX.mixer.toggleCrossFadeSectionVisibility()`
- Result: `None`

### A6 mixer crossfade section RESULT
- Verdict: **worked**
- Call/code: `PX.mixer.toggleCrossFadeSectionVisibility() / PX.mixer.isCrossFadeSectionVisible().get()`
- Result: `[False, True, False]`
- Learned: before,after,restored

### A7 mixer io section toggle
- Verdict: **worked**
- Call/code: `PX.mixer.toggleIoSectionVisibility()`
- Result: `None`

### A7 mixer io section toggle back
- Verdict: **worked**
- Call/code: `PX.mixer.toggleIoSectionVisibility()`
- Result: `None`

### A7 mixer io section RESULT
- Verdict: **worked**
- Call/code: `PX.mixer.toggleIoSectionVisibility() / PX.mixer.isIoSectionVisible().get()`
- Result: `[True, False, True]`
- Learned: before,after,restored

### B1 host api version
- Verdict: **worked**
- Call/code: `[host.getHostApiVersion(), host.getHostVendor(), host.getHostProduct(), host.getHostVersion()]`
- Result: `[25, 'Bitwig', 'Bitwig Studio', '6.1']`

### E2-E5 Read-only state of Application / Arranger / Mixer / Project (px_eval)
- Verdict: **worked**
- Code: `application.projectName().get()`, `canUndo/canRedo`, `panelLayout`, `displayProfile`, `hasActiveEngine`, `PX.arranger.*Visible()`, `PX.mixer.*SectionVisible()`, `PX.project.hasSoloedTracks/hasMutedTracks/hasArmedTracks()` (objects created in init: host.createArranger()/createMixer()/getProject())
- Result: project name "New 1", canUndo true/canRedo false, layout ARRANGE, profile "Single Display (Large)", engine active; arranger launcher/timeline/fx visible, mixer sections readable; project flags all false.
- Learned: all these state getters work and are cheap. Project name is readable (connector currently has no project name tool). hasSoloed/Muted/Armed give a one-call "anything soloed?" check.

### E6 Toggle visibility (arranger and mixer sections)
- Verdict: **worked** (except noted)
- Code: `PX.arranger.toggleCueMarkerVisibility() / togglePlaybackFollow() / toggleTrackRowHeight()`, `PX.mixer.toggleMeterSectionVisibility() / toggleCrossFadeSectionVisibility() / toggleIoSectionVisibility()`; each toggled and toggled back, state read before/after/restored.
- Result: cue markers False->True->False, playback follow True->False->True, mixer meter False->True->False, crossfade False->True->False, mixer IO True->False->True. toggleTrackRowHeight: no observable change (False/False/False; likely needs a layout refresh or a track present). Arranger has no toggle for IO section (read-only `isIoSectionVisible`).
- Learned: Claude can show/hide the Mixer IO section (needed to see routing/sidechain selectors in the UI), meter, crossfade, cue marker lane and playback-follow. Safe and reversible.

### E7 API version
- Verdict: **worked**
- Code: edited live script `loadAPI(17)` -> `loadAPI(25)` (also tried 30/40/99). `host.getHostApiVersion()` returns 25 for all of them (clamped to Bitwig 6.1's max, no error).
- Result: with API 17 `host.createLastClickedParameter()` and `host.createMasterRecorder()` threw "only available for API versions after 20"; with 25 both are created. Everything else in the script still loaded (ping ok).
- Learned: raising `loadAPI` to 25 is a one-line change that unlocks API 18-25 features (master recorder, last-clicked parameter, and anything else version-gated). To verify nothing in the connector regresses (the live_test.py should be run).

### C1 mark recorder
- Verdict: **failed**
- Call/code: `[PX.recorder.isActive().markInterested(), PX.recorder.duration().markInterested(), PX.lastclicked.exists().markInterested(), PX.lastclicked.isLocked().markInterested(), PX.lastclicked.parameter().name().markInterested(), PX.lastclicked.parameter().displayedValue().markInterested(),PX.lastclicked.parameter().value().markInterested()]`
- Result: `riT: This can only be called during driver initialization`

### C2 lastclicked state
- Verdict: **failed**
- Call/code: `[PX.lastclicked.exists().get(), PX.lastclicked.parameter().name().get(), PX.lastclicked.parameter().displayedValue().get()]`
- Result: `riT: Either call markInterested() or add at least one observer in init in order to access the current value`

### C3 recorder state
- Verdict: **failed**
- Call/code: `[PX.recorder.isActive().get(), PX.recorder.duration().get()]`
- Result: `riT: Either call markInterested() or add at least one observer in init in order to access the current value`

### C4 recorder start
- Verdict: **worked**
- Call/code: `PX.recorder.start()`
- Result: `None`

### C5 recorder active
- Verdict: **failed**
- Call/code: `[PX.recorder.isActive().get(), PX.recorder.duration().get()]`
- Result: `riT: Either call markInterested() or add at least one observer in init in order to access the current value`

### C6 recorder stop
- Verdict: **worked**
- Call/code: `PX.recorder.stop()`
- Result: `None`

### C7 recorder after
- Verdict: **failed**
- Call/code: `[PX.recorder.isActive().get(), PX.recorder.duration().get()]`
- Result: `riT: Either call markInterested() or add at least one observer in init in order to access the current value`

### E8 MasterRecorder (host.createMasterRecorder, needs API >= 20)
- Verdict: **worked** (start/stop); status getters only after init-time markInterested
- Code: init: `host.createMasterRecorder()`; run: `PX.recorder.start()`, sleep 2 s, `PX.recorder.stop()` via px_eval. Reads of isActive()/duration() failed with "Either call markInterested() or add at least one observer in init" (markInterested is init-only: "This can only be called during driver initialization").
- Result: Bitwig logged "Master Recording finished" and wrote `%LOCALAPPDATA%\Bitwig Studio\temp-projects\<guid>\master-recordings\2026-10-04 09.09.08.wav` (529 KB for ~3 s; for a saved project it presumably goes into the project folder). No dialog, no UI interaction.
- Learned: the script can record the master output to a WAV file with start/stop. That replaces WASAPI loopback capture for loudness/spectrum analysis (no driver restriction, no speaker/loopback dependency, exact timing). Methods: start, stop, toggle, isActive, duration.
- Note: scratch recording left a file (mine) in the temp-projects folder; deleted at end of run.

### E9 LastClickedParameter (host.createLastClickedParameter)
- Verdict: **partial** (object creates at API 25; reading needs init-time markInterested; see E10 for the retest)
- Methods: parameter(), exists(), isLocked(), smartToggleLock(), parameterColor().

### D1 lastclicked state
- Verdict: **worked**
- Call/code: `[PX.lastclicked.exists().get(), PX.lastclicked.isLocked().get(), PX.lastclicked.parameter().name().get(), PX.lastclicked.parameter().displayedValue().get()]`
- Result: `[True, False, '', '']`

### D2 recorder state
- Verdict: **worked**
- Call/code: `[PX.recorder.isActive().get(), PX.recorder.duration().get()]`
- Result: `[False, 1905]`

### D3 transport extras
- Verdict: **worked**
- Call/code: `[transport.isPunchInEnabled().get(),transport.preRoll().get(),transport.arrangerLoopStart().get(),transport.arrangerLoopDuration().get(),transport.automationWriteMode().get(),transport.clipLauncherPostRecordingAction().get(),transport.defaultLaunchQuantization().get(), transport.playPositionInSeconds().get()]`
- Result: `[False, 'none', 0, 8, 'latch', 'off', '1', 2.519999999933961]`

### D4 settings read
- Verdict: **worked**
- Call/code: `[PX.sets.pstr.get(),PX.sets.pnum.getRaw(),PX.sets.penum.get(),PX.sets.pbool.get(),PX.sets.dstr.get(),PX.sets.dnum.getRaw()]`
- Result: `['default', 42, 'b', True, 'hello', 3]`

### D5 set pref string
- Verdict: **worked**
- Call/code: `PX.sets.dstr.set('written by claude'), PX.sets.dstr.get()`
- Result: `hello`

### D6 popup exists/title
- Verdict: **worked**
- Call/code: `[PX.popup.exists().get(),PX.popup.title().get(),PX.popup.contentTypeNames().get()]`
- Result: `[False, '', []]`

### D7 master
- Verdict: **worked**
- Call/code: `[PX.master.exists().get(),PX.master.name().get(),PX.master.volume().displayedValue().get()]`
- Result: `[True, 'Master', '0.0 dB']`

### D8 userctl
- Verdict: **worked**
- Call/code: `[PX.uc[0].name().get(),PX.uc[0].value().get()]`
- Result: `['', 0]`

### D9 groove
- Verdict: **failed**
- Call/code: `[PX.groove.getEnabled().get().get(),PX.groove.getShuffleAmount().get().get()]`
- Result: `TypeError: (intermediate value).groove.getEnabled(...).get(...).get is not a function`

### D10 project cue
- Verdict: **worked**
- Call/code: `[PX.project.cueVolume().get(),PX.project.cueMix().get()]`
- Result: `[0.7937005259840999, 1]`

### D11 recordQuantizeGrid
- Verdict: **worked**
- Call/code: `[application.recordQuantizationGrid().get(),application.recordQuantizeNoteLength().get()]`
- Result: `['OFF', True]`

### D5b re-read doc string
- Verdict: **worked**
- Call/code: `PX.sets.dstr.get()`
- Result: `written by claude`

### D12 set number
- Verdict: **worked**
- Call/code: `PX.sets.dnum.setRaw(7)`
- Result: `None`

### D12b number
- Verdict: **worked**
- Call/code: `PX.sets.dnum.getRaw()`
- Result: `7`

### D13 groove
- Verdict: **worked**
- Call/code: `[PX.groove.getEnabled().get(),PX.groove.getShuffleAmount().value().get()]`
- Result: `[0, 0.5]`

### D14 signal fire
- Verdict: **worked**
- Call/code: `PX.sets.dsig.fire(); PX.sigfired`
- Result: `0`

### D14b
- Verdict: **worked**
- Call/code: `PX.sigfired`
- Result: `0`

### E10 Init-time probe objects: LastClickedParameter, recorder status, transport extras, settings
- Verdict: **worked**
- Code: probe2.js (init-time markInterested on ~200 values) then px_eval reads.
- Result: `lastclicked.exists()` true, name "" (nothing clicked yet; needs user interaction to verify); `recorder.isActive()` false, `duration()` 1905 (ms after the E8 recording); transport: punchIn false, preRoll "none", loop start 0 / duration 8 (beats), automationWriteMode "latch", clipLauncherPostRecordingAction "off", defaultLaunchQuantization "1", playPositionInSeconds readable; `application.recordQuantizationGrid()` "OFF"; `project.cueVolume()` 0.79, `cueMix()` 1.
- Failed (Message not supported): `timeSignature().markInterested`, `Transport.crossfade`, `Track.crossFadeMode/canHoldAudioData/canHoldNoteData/isPreFader/autoMonitor/monitor` on track bank items, `Channel.mute()` on master. Deprecated since API 2 (throw "Use remote controls instead"): `Device.getMacro`, `Device.getModulationSource`.
- Learned: `markInterested` is only allowed during init. Anything the connector wants to READ must be marked in init, so new read features need a script change plus reload (5 s).

### E11 Preferences / DocumentState settings (script-defined UI settings)
- Verdict: **worked** (script side); UI appearance untested (see E-UI)
- Code: init `host.getDocumentState().getStringSetting("PX DocString","Probe",60,"hello")`, `getNumberSetting`, `getSignalSetting`, `host.getPreferences().getEnumSetting/getBooleanSetting`; runtime `PX.sets.dstr.set('written by claude')`, `PX.sets.dnum.setRaw(7)`.
- Result: values read back correctly after the next flush (`set` returns before the value changes: get() immediately after set gives the old value; a second call gives 'written by claude' / 7). Signal `fire()` from script does not call its own observer (the observer is for the user's button click).
- Learned: Document settings are stored inside the project; they are a persistent per-project Claude notebook (store session notes, genre, mix targets, last snapshot) and a user->Claude channel (user edits a field or presses a Signal button in Controller preferences, Claude's script sees the observer). Must be declared in init.

### E12 !!! CRASH: Signal.fire() from the script crashed Bitwig (09:13)
- Verdict: **FAILED - BITWIG CRASHED**
- Code: `PX.sets.dsig.fire()` via px_eval, where `dsig = host.getDocumentState().getSignalSetting("PX Signal","Probe","Fire")`.
- Result: Application crashed: `java.lang.IllegalStateException: This signal cannot be invoked at ...SignalProxy.doFire` (BitwigStudio.log, "Application crashing in subsystem Control Surface"). The project was the empty "New 1", so no work lost. User restarted Bitwig.
- Learned: NEVER call Signal.fire() from a script. Document-state Signals are user->script only (the observer fires when the user clicks the button). Same class of risk: calling unknown methods blindly on live objects through px_eval.
- Cleanup: live controller folder restored from backup (probe.js/probe2.js removed, loadAPI back to 17), `sync --check` = in sync. My scratch master recording WAV (E8) deleted. After the restart, no ZZ track existed (my create_instrument_track call at 09:12 came just before the crash / did not land); verified below.
- Experiments stopped. Remaining work is offline (class files, files on disk, docs).

### E13 Post-crash state check
- Verdict: **worked**
- Code: `capabilities`, `get_session` after the user restarted Bitwig.
- Result: controller v6.0 answers; the project now has "Inst 1" (Instrument) and "Audio 2" (Audio): the user's restarted project, not scratch tracks of mine (none of mine survived). Not touched. `px_err` returns "unknown command", confirming the probe hooks are gone; `manage.py sync --check` = in sync.

### E14 Offline: action list scan (research/actions.txt, 781 actions)
- Verdict: **worked**
- Result: candidates not wrapped as dedicated tools (all runnable via run_bitwig_action; none run in this session): zooming (fit/selection for arranger, detail, mixer), Consolidate, Reverse, Reverse Pattern, Bounce In Place (pre-FX/pre-fader/post-fader), Quantize / Quantize Audio / Quantize Length / Quantize to Key, Normalize, Fade In/Out, Auto-Fade, Reset Fades, Loop Selected Region, stretch_to_project_tempo, stretch_to_analyzed_tempo, Duplicate as Alias, Duplicate Time, Flatten as Track Automation, Split, Merge Duplicate Patterns, comping take select, jump/launch from arranger loop start/end, Export DAWproject / MIDI / Audio (dialogs).
- Learned: audio-clip editing (stretch, quantize audio, normalize, fades) is reachable only by actions and needs an arranger clip selected (the known limit).

### Not done
Popup browser exercise, Windows UI Automation, project/preset file reading, stock-device display parameters, sidechain routing: not run because live work was stopped after the crash.

## Resumed run (user said carry on). Low-risk only: no Signal.fire, no blind calls.

### E15 Windows UI Automation on Bitwig's window
- Verdict: **failed (BLOCKED)**
- Code: `pip install pywinauto` (log: installed pywinauto from PyPI); `Desktop(backend="uia").window(handle=<Bitwig>).descendants()`; `win32gui.EnumChildWindows`.
- Result: top window class `bitwig`, title "Bitwig Studio - <project>" (readable: gives the project name!). UIA tree has 0 descendants; no child HWNDs. The UI is custom-drawn (OpenGL).
- Learned: no readable/controllable widgets: sidechain selector, group buttons, FX track names and meters are NOT reachable through UIA. Only options left are screenshots + OCR/vision and synthetic mouse/keyboard (fragile, can damage the project; not tried). Window title works as a cheap project-name check.

### E16 Project file (.bwproject) read-only analysis
- Verdict: **worked**
- Code: python `re.findall(rb"[ -~]{5,}", data)` on `Documents\Bitwig Studio\Projects\New 3\New 3.bwproject` (70 MB), read only.
- Result: container "BtWg0003 0002" (same format as presets; research/bwformat.py can parse it). Plain strings expose: track names (Low End Bus, Synth Bus, Strings Pad...), plugin names (Serum 2, Spire), stock devices as full paths (Library\devices\EQ+.bwdevice, Compressor+, Tool, Peak Limiter, De-Esser, Reverb, Delay+), device UUID e4815188... (EQ+), referenced sample paths (e.g. a stem on the Desktop) and package presets, `application_version_name`, `revision_no`, and parameter ids per device (TYPE1, FREQ1, GAIN1, ENABLE1, CROSSFADE_MODE, GROOVE_ENABLED, SHUFFLE_RATE, ACCENT_*, CUE_MIX ...).
- Learned: a "project report from disk" tool is feasible (offline, no Bitwig needed, works on projects that are not open): track tree, device chains, plugin list, sample usage (missing-file check), version. Also a clean source of parameter-id names for DISP_DEVICES. Other folders: `Projects\*\bounce\*.wav` (bounce-in-place output), `new remix\master-recordings` (3.6 GB of master recordings: a disk-space hygiene item), `auto-backups`.

### E17 Preview of DAWproject export
- Verdict: **not run**: action `Project:export_project` ("Export DAWproject...") opens a file dialog; the connector cannot drive it. DAWproject is a zip with project.xml + audio; it would be the best machine-readable project dump but must be exported by the user (or by a UI click). Parser for the zip would be easy (zipfile + ElementTree).

### E18 Screenshot of Bitwig's window (read-only)
- Verdict: **worked**
- Code: `win32gui.GetWindowDC` + `ctypes.windll.user32.PrintWindow(hwnd, memdc, 2)` + PIL -> `bw_shot.png` (1536x864 client area). No focus change, no input sent.
- Result: full, correct image of the window even though UIA exposes nothing (E15): track list with names/volumes, device chain (EQ-like filter, Gate with a "Device Input" sidechain selector and level meter, Saturator curve with dB values), browser list, transport (110 bpm, C Major). Visible values like "Sidechain FX", "-4.8", "-30.0 dB" are readable by a vision model.
- Learned: the only generic way to READ UI-only state (FX track names/faders, sidechain source dropdowns, gain-reduction and level meters, device displays) is screenshot + vision/OCR. It is read-only and harmless; controlling the UI would need synthetic mouse/keyboard (not tried: could damage the project). Practical use: "verify sidechain source" or "read GR" tools that screenshot and let Claude look; low rate, not a live meter.

### E19 Sidechain / routing via API
- Verdict: **BLOCKED (confirmed from the jar)**
- Evidence: `SourceSelector` has only getHasAudioInputSelected/getHasNoteInputSelected (+ observers). No class has a method with "sidechain", "routing" or "output" in its name. `Channel` has no destination/input choice; `Send` has 4 methods (value/target-ish only). InsertionPoint offers browse/insertBitwigDevice/insertFile/insertVST2/3/insertCLAP/copy/move for tracks, devices and slots.
- Learned: sidechain source and I/O routing cannot be set through the API. Alternatives: (a) devices with built-in sidechain via presets are not a route either (E16 shows the device input source is stored in the project data as device state not exposed); (b) screenshot to verify; (c) synthetic mouse clicks on the "Device Input" dropdown (untested, fragile). Interesting: `insertCLAP/insertVST2/insertVST3` insertion points exist (3rd-party plugin insert by path) and `Device.createSpecificVst2/Vst3Device`.

### E20 Stock-device parameter ids (read-only, via deep_info on a ZZ track)
- Verdict: **worked**
- Code: created track ZZdisc (instrument), `deep_insert_uuid` for 8 stock devices, `select_device` + `deep_info(limit=200)` for each; ids saved in ids.txt.
- Result (id=name): Delay+ 23 params (MIX, FEEDBACK, HICUT, LOCUT, TIME, STEPS, UNIT, WIDTH, BLUR, DUCKING, DETUNE, PAN, CROSSFEED...); Reverb 13 (ROOM_SIZE, DIFFUSION, REVERB_TIME, MIX, BUILDUP, WIDTH, PRE-DELAY, LOFREQ, HIFREQ, LOX, HIX, EARLY_LATE); Peak Limiter 4 (CEILING, GAIN, RELEASE, RELEASE_BIAS); Tool 7 (AMPLITUDE, WIDTH, PAN, VOLUME, INVERT_*, PAN_SWAP); De-Esser 4 (FREQ, AMOUNT, MONITOR, FILTER_TYPE); Gate 4 (THRESHOLD_LEVEL, ATTACK, RELEASE, DEPTH); Saturator 14 (DRIVE, OUTPUT, CUTOFF, POLES, LOW/HIGH_THRESHOLD/RATIO/KNEE...); Filter+ 11 (mostly note/shuffle ids: the audio filter params are not listed as direct params).
- Risk note (logged before any change): wiring these into `DISP_DEVICES` (deep.js) means `createSpecificBitwigDevice(uuid).createParameter(id)` calls at init; a wrong id is caught by try/catch in existing code. NOT wired or tested in this run (stopped short after the crash; no more script edits).
- Learned: the ids are the same strings visible as parameter names in .bwproject files (E16), so a list for every stock device can be harvested offline. No gain-reduction/meter ids exist on Gate/Limiter/De-Esser (their meters are UI-only; see E18 screenshot).
- Cleanup: ZZdisc track and its 8 devices deleted (session back to Inst 1 + Audio 2). FX 1 and Master belong to the project and were not touched.

### E21 PopupBrowser
- Verdict: **partial**
- Evidence: `host.createPopupBrowser()` creates at init (E1), `exists()` false while closed, `contentTypeNames()` empty while closed. Column banks (smartCollection/location/device/category/tag/creator/deviceType/fileType/results) were created in probe2.js but not exercised (the crash ended live work). Needs `insertionPoint.browse()` to open it first (already used by open_device_browser), then read columns/results, `selectNextFile`, `commit`. Not tested: opening a popup changes UI state.
