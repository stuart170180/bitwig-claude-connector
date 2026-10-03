// Arranger clip access via host.createArrangerCursorClip (follows the clip SELECTED on the arranger timeline).
// Own file; needs NOTE_STEP / noteRecord / interest / need / clamp01 from the other scripts.
var arrClip = null, arrNotes = {}, arrEvents = 0, arrRefreshing = false;

function initArrClips() {
   try {
      arrClip = host.createArrangerCursorClip(8192, 128);
      interest(arrClip.exists()); interest(arrClip.getLoopLength()); interest(arrClip.getLoopStart());
      interest(arrClip.isLoopEnabled()); interest(arrClip.getPlayStart()); interest(arrClip.getPlayStop());
      try { var t = arrClip.getTrack(); interest(t.name()); interest(t.position()); } catch (e) {}
      arrClip.setStepSize(NOTE_STEP);
      arrClip.scrollToKey(0);
      arrClip.scrollToStep(0);
      arrClip.addNoteStepObserver(function (step) {
         arrEvents++;
         var key = step.x() + ":" + step.y();
         if (String(step.state()) === "NoteOn") arrNotes[key] = noteRecord(step);
         else delete arrNotes[key];
      });
   } catch (e) { arrClip = null; }
}

function handleArrClips(cmd, a) {
   if (cmd.indexOf("arrclip_") !== 0) return undefined;
   if (!arrClip) throw "arranger cursor clip not available";
   switch (cmd) {
      case "arrclip_info": {
         var tr = null;
         try { var t = arrClip.getTrack(); tr = { name: t.name().get(), position: t.position().get() }; } catch (e) {}
         return { exists: arrClip.exists().get(), loop_start: arrClip.getLoopStart().get(), loop_length: arrClip.getLoopLength().get(),
                  loop_enabled: arrClip.isLoopEnabled().get(), play_start: arrClip.getPlayStart().get(),
                  play_stop: arrClip.getPlayStop().get(), track: tr, cached_notes: Object.keys(arrNotes).length, events: arrEvents };
      }
      case "arrclip_refresh": {   // same scroll-away trick as pro.js focus_clip: forces every note to be re-reported
         arrNotes = {};
         arrClip.scrollToStep(1000000);
         host.scheduleTask(function () { arrNotes = {}; arrClip.scrollToStep(0); }, 150);
         return "ok";
      }
      case "arrclip_notes": {
         var list = [];
         for (var k in arrNotes) list.push(arrNotes[k]);
         list.sort(function (x, y) { return x.start - y.start || x.pitch - y.pitch; });
         var off = a.offset || 0, lim = a.limit || 120;
         return { exists: arrClip.exists().get(), notes: list.slice(off, off + lim), total: list.length, offset: off,
                  loop_length: arrClip.getLoopLength().get() };
      }
      case "arrclip_set_name": arrClip.setName(String(need(a, "name"))); return "ok";
      case "arrclip_clear": arrClip.clearSteps(); arrNotes = {}; return "ok";
      case "arrclip_write": {
         if (!arrClip.exists().get()) throw "no arranger clip selected";
         if (a.replace !== false) arrClip.clearSteps();
         var notes = a.notes || [];
         for (var n = 0; n < notes.length; n++) {
            var nt = notes[n];
            arrClip.setStep(Math.round(nt.start / NOTE_STEP), nt.pitch, nt.velocity == null ? 100 : nt.velocity, nt.duration || NOTE_STEP);
         }
         if (a.length_beats) arrClip.getLoopLength().set(a.length_beats);
         return "wrote " + notes.length;
      }
      case "arrclip_op": {   // op: duplicate | duplicate_content | show_in_editor | quantize | transpose | launch | return_to_arrangement | return_to_arrangement
         var op = String(need(a, "op"));
         if (op === "duplicate") arrClip.duplicate();
         else if (op === "duplicate_content") arrClip.duplicateContent();
         else if (op === "show_in_editor") arrClip.showInEditor();
         else if (op === "quantize") arrClip.quantize(clamp01(a.amount == null ? 1 : a.amount));
         else if (op === "transpose") arrClip.transpose(need(a, "semitones"));
         else if (op === "launch") arrClip.launch();
         else if (op === "return_to_arrangement") { transport.returnToArrangement(); for (var i = 0; i < NUM_TRACKS; i++) { try { trackBank.getItemAt(i).returnToArrangement(); } catch (e) {} } }
         else throw "unknown op " + op;
         return "ok";
      }
   }
   return undefined;
}
