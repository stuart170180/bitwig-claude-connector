// Extras found by the API exploration (research/discoveries): master recorder, project state, UI sections, project notes,
// last-clicked parameter, transport extras, undo/redo. Needs loadAPI(20+). NEVER call Signal.fire() from here (crashes Bitwig).
var exMaster = null, exLast = null, exArranger = null, exMixer = null, exProject = null, exDoc = {}, exErr = {};
var EX_ARR = { cue_markers: "areCueMarkersVisible", timeline: "isTimelineVisible", launcher: "isClipLauncherVisible", io: "isIoSectionVisible",
               fx_tracks: "areEffectTracksVisible", follow: "isPlaybackFollowEnabled", double_row: "hasDoubleRowTrackHeight" };
var EX_ARR_TOGGLE = { cue_markers: "toggleCueMarkerVisibility", follow: "togglePlaybackFollow", double_row: "toggleTrackRowHeight" };
var EX_MIX = { launcher: ["isClipLauncherSectionVisible", "toggleClipLauncherSectionVisibility"], crossfade: ["isCrossFadeSectionVisible", "toggleCrossFadeSectionVisibility"],
               devices: ["isDeviceSectionVisible", "toggleDeviceSectionVisibility"], io: ["isIoSectionVisible", "toggleIoSectionVisibility"],
               meters: ["isMeterSectionVisible", "toggleMeterSectionVisibility"], sends: ["isSendSectionVisible", "toggleSendsSectionVisibility"] };

function initExtras() {
   try { exMaster = host.createMasterRecorder(); interest(exMaster.isActive()); interest(exMaster.duration()); } catch (e) { exErr.recorder = String(e); }
   try {
      exLast = host.createLastClickedParameter("claude_last_clicked", "Claude last clicked"); var lp = exLast.parameter();
      interest(exLast.exists()); interest(exLast.isLocked()); interest(lp.name()); interest(lp.value()); interest(lp.displayedValue()); interest(lp.exists());
   } catch (e) { exErr.lastclicked = String(e); }
   try { exArranger = host.createArranger(); for (var k in EX_ARR) interest(exArranger[EX_ARR[k]]()); } catch (e) { exErr.arranger = String(e); }
   try { exMixer = host.createMixer(); for (var m in EX_MIX) interest(exMixer[EX_MIX[m][0]]()); } catch (e) { exErr.mixer = String(e); }
   try {
      exProject = host.getProject();
      interest(exProject.hasSoloedTracks()); interest(exProject.hasMutedTracks()); interest(exProject.hasArmedTracks());
   } catch (e) { exErr.project = String(e); }
   try { interest(application.projectName()); interest(application.canUndo()); interest(application.canRedo()); interest(application.hasActiveEngine()); } catch (e) { exErr.app = String(e); }
   try {
      interest(transport.isPunchInEnabled()); interest(transport.isPunchOutEnabled()); interest(transport.preRoll());
      interest(transport.arrangerLoopStart()); interest(transport.arrangerLoopDuration());
   } catch (e) { exErr.transport = String(e); }
   // Per-project settings: they are stored inside the .bwproject and show in Bitwig's controller settings. Read-only for the user's
   // own editing; we only ever set them. (Signals are deliberately not used.)
   try {
      var D = host.getDocumentState();
      exDoc.notes = D.getStringSetting("Notes", "Claude", 500, ""); interest(exDoc.notes);
      exDoc.genre = D.getStringSetting("Genre", "Claude", 40, ""); interest(exDoc.genre);
      exDoc.target = D.getStringSetting("Mix target", "Claude", 40, ""); interest(exDoc.target);
   } catch (e) { exErr.docstate = String(e); }
}

function exBool(v) { try { return v.get(); } catch (e) { return null; } }

function handleExtras(cmd, a) {
   switch (cmd) {
      case "ex_status": return { errors: exErr, api: host.getHostApiVersion(), recorder: !!exMaster, last_clicked: !!exLast, arranger: !!exArranger, mixer: !!exMixer, notes: !!exDoc.notes };
      case "rec_start": if (!exMaster) throw "master recorder unavailable: " + exErr.recorder; exMaster.start(); return "started";
      case "rec_stop": if (!exMaster) throw "master recorder unavailable: " + exErr.recorder; exMaster.stop(); return "stopped";
      case "rec_status": if (!exMaster) throw "master recorder unavailable: " + exErr.recorder; return { active: exMaster.isActive().get(), duration_ms: exMaster.duration().get() };
      case "proj_state": return {
         project: application.projectName().get(), can_undo: exBool(application.canUndo()), can_redo: exBool(application.canRedo()),
         engine_active: exBool(application.hasActiveEngine()),
         has_soloed: exProject ? exBool(exProject.hasSoloedTracks()) : null, has_muted: exProject ? exBool(exProject.hasMutedTracks()) : null,
         has_armed: exProject ? exBool(exProject.hasArmedTracks()) : null
      };
      case "engine": {   // action: state | activate | deactivate (recovering after an audio-engine crash)
         if (a.action === "activate") application.activateEngine();
         else if (a.action === "deactivate") application.deactivateEngine();
         return { active: exBool(application.hasActiveEngine()) };
      }
      case "app_undo": application.undo(); return "ok";
      case "app_redo": application.redo(); return "ok";
      case "ui_get": {
         var out = { arranger: {}, mixer: {} };
         if (exArranger) for (var k in EX_ARR) out.arranger[k] = exBool(exArranger[EX_ARR[k]]());
         if (exMixer) for (var m in EX_MIX) out.mixer[m] = exBool(exMixer[EX_MIX[m][0]]());
         return out;
      }
      case "ui_set": {   // {arranger: {cue_markers: true, ...}, mixer: {meters: false, ...}}; toggles only what differs
         var done = {};
         var arr = a.arranger || {}, mix = a.mixer || {};
         for (var ka in arr) {
            if (!EX_ARR_TOGGLE[ka]) { done["arranger." + ka] = "not togglable from a script"; continue; }
            if (exBool(exArranger[EX_ARR[ka]]()) !== !!arr[ka]) exArranger[EX_ARR_TOGGLE[ka]]();
            done["arranger." + ka] = !!arr[ka];
         }
         for (var km in mix) {
            if (!EX_MIX[km]) { done["mixer." + km] = "unknown section"; continue; }
            if (exBool(exMixer[EX_MIX[km][0]]()) !== !!mix[km]) exMixer[EX_MIX[km][1]]();
            done["mixer." + km] = !!mix[km];
         }
         return done;
      }
      case "note_get": return { notes: exDoc.notes ? exDoc.notes.get() : null, genre: exDoc.genre ? exDoc.genre.get() : null, mix_target: exDoc.target ? exDoc.target.get() : null,
                                available: !!exDoc.notes, error: exErr.docstate || null };
      case "note_set": {
         if (!exDoc.notes) throw "project notes unavailable: " + exErr.docstate;
         if (a.notes != null) exDoc.notes.set(String(a.notes));
         if (a.genre != null) exDoc.genre.set(String(a.genre));
         if (a.mix_target != null) exDoc.target.set(String(a.mix_target));
         return "ok";   // set() returns before the value changes; read again after a moment
      }
      case "last_clicked": {
         if (!exLast) throw "last-clicked parameter unavailable: " + exErr.lastclicked;
         var lp = exLast.parameter();
         return { exists: exLast.exists().get(), locked: exLast.isLocked().get(), name: lp.name().get(), value: lp.value().get(), display: lp.displayedValue().get() };
      }
      case "transport_extras": {
         if (a.punch_in != null) transport.isPunchInEnabled().set(!!a.punch_in);
         if (a.punch_out != null) transport.isPunchOutEnabled().set(!!a.punch_out);
         if (a.pre_roll != null) transport.preRoll().set(String(a.pre_roll));   // none, one_bar, two_bars, four_bars
         if (a.loop_start != null) transport.arrangerLoopStart().set(+a.loop_start);
         if (a.loop_length != null) transport.arrangerLoopDuration().set(+a.loop_length);
         return { punch_in: exBool(transport.isPunchInEnabled()), punch_out: exBool(transport.isPunchOutEnabled()), pre_roll: exBool(transport.preRoll()),
                  loop_start: exBool(transport.arrangerLoopStart()), loop_length: exBool(transport.arrangerLoopDuration()) };
      }
   }
   return undefined;
}
