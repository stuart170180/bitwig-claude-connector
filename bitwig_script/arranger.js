// Scene-to-arrangement recorder. Bitwig's API can't place clips on the arranger timeline, but it can
// record them: with arranger record on, launching scenes in time writes the playing clips to the
// arrangement. Timing runs inside Bitwig (polling the play position) so launches land on bar lines.

var rec = { running: false, plan: [], next: 0, total: 0, pos: 0, saved: null, phase: "idle", error: null, launched: [] };
var REC_POLL_MS = 25, REC_LEAD_BEATS = 1.0;  // launch one beat ahead; launch quantization snaps it to the bar

function recFinish(reason) {
   try { if (launchQuant) launchQuant.set("none"); trackBank.getClipLauncherScenes().stop(); } catch (e) {}  // drop queued launches
   try { transport.stop(); } catch (e) {}
   try { if (arrRec) arrRec.set(false); } catch (e) {}
   try { if (rec.saved !== null && launchQuant) launchQuant.set(rec.saved); } catch (e) {}
   rec.running = false; rec.phase = reason;
}

function recLaunch(item) {
   sceneBank.getScene(item.scene).launch();
   // A scene launch only affects tracks that have a clip in it; stop the rest so the section is exactly
   // what the scene contains (e.g. a breakdown without drums).
   for (var t = 0; t < NUM_TRACKS; t++) {
      var tr = trackBank.getItemAt(t);
      if (!tr.exists().get()) continue;
      if (!tr.clipLauncherSlotBank().getItemAt(item.scene).hasContent().get()) tr.stop();
   }
   rec.launched.push({ scene: item.scene, start_beat: item.start, at_position: Math.round(rec.pos * 100) / 100 });
}

function recPoll() {
   if (!rec.running) return;
   try {
      rec.pos = transport.getPosition().get();
      if (rec.phase === "positioning") {  // wait until the playhead really reads 0 before launching anything
         if (rec.pos > 0.05) {
            if (++rec.tries > 80) { rec.error = "couldn't move the playhead to the start"; recFinish("error"); return; }
            seekTo(rec.tries % 2 ? 1 : 0);  // if a seek to 0 is ignored, hop elsewhere and back
         } else {
            if (launchQuant) launchQuant.set("none");
            arrRec.set(true);
            recLaunch(rec.plan[0]);  // first section starts immediately, together with the transport
            transport.play();
            rec.phase = "starting";
         }
         host.scheduleTask(recPoll, REC_POLL_MS);
         return;
      }
      if (rec.phase === "starting" && rec.pos > 0.05) {  // first scene is live; switch to bar-quantized launches
         if (launchQuant) launchQuant.set("1");
         rec.phase = "recording";
      }
      while (rec.next < rec.plan.length && rec.pos >= rec.plan[rec.next].start - REC_LEAD_BEATS) {
         if (rec.plan[rec.next].start > 0) recLaunch(rec.plan[rec.next]);
         rec.next++;
      }
      if (rec.pos >= rec.total) { recFinish("done"); return; }
   } catch (e) { rec.error = String(e); recFinish("error"); return; }
   host.scheduleTask(recPoll, REC_POLL_MS);
}

function handleArranger(cmd, a) {
   switch (cmd) {
      case "arranger_start": {
         if (rec.running) throw "a recording is already running (arranger_abort to cancel)";
         if (!arrRec) throw "this Bitwig version doesn't expose arranger record to scripts";
         var plan = need(a, "plan");
         if (!plan.length || plan[0].start !== 0) throw "plan must start at beat 0";
         rec = { running: true, plan: plan, next: 1, total: need(a, "total_beats"), pos: 0,
                 saved: launchQuant ? launchQuant.get() : null, phase: "starting", error: null, launched: [] };
         transport.stop();
         seekTo(0);
         rec.phase = "positioning"; rec.tries = 0;
         host.scheduleTask(recPoll, REC_POLL_MS);
         return "started";
      }
      case "arranger_status":
         return { running: rec.running, phase: rec.phase, position: Math.round(rec.pos * 100) / 100, total: rec.total,
                  next_section: rec.next, sections: rec.plan.length, launched: rec.launched, error: rec.error };
      case "arranger_abort":
         if (rec.running) recFinish("aborted");
         return "ok";
   }
   return undefined;
}
