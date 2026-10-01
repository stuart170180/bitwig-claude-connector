// Expert note editing: Bitwig per-note expressions and clip settings for the MCP bridge.

function r3(v) { return Math.round(v * 1000) / 1000; }

// Full note record from a NoteStep. Expression fields use Bitwig's ranges:
// gain 0..1, pan -1..1, timbre -1..1, pressure 0..1, transpose semitones, chance 0..1.
function noteRecord(step) {
   var n = { pitch: step.y(), start: step.x() * NOTE_STEP, duration: step.duration(),
             velocity: Math.round(step.velocity() * 127) };
   try {
      n.release_velocity = Math.round(step.releaseVelocity() * 127);
      n.velocity_spread = r3(step.velocitySpread());
      // Bitwig reports note gain at 2x the setGain scale; halve it so reads match writes.
      n.gain = r3(step.gain() / 2); n.pan = r3(step.pan()); n.timbre = r3(step.timbre());
      n.pressure = r3(step.pressure()); n.transpose = r3(step.transpose());
      n.muted = step.isMuted();
      n.chance = step.isChanceEnabled() ? r3(step.chance()) : 1;
      if (step.isRepeatEnabled() && step.repeatCount() !== 0) n.repeat = { count: step.repeatCount(), curve: r3(step.repeatCurve()),
         velocity_curve: r3(step.repeatVelocityCurve()), velocity_end: r3(step.repeatVelocityEnd()) };
      if (step.isOccurrenceEnabled() && String(step.occurrence()) !== "ALWAYS") n.occurrence = String(step.occurrence());
      if (step.isRecurrenceEnabled() && step.recurrenceLength() > 1) n.recurrence = { length: step.recurrenceLength(), mask: step.recurrenceMask() };
   } catch (e) {}
   return n;
}

var NoteOccurrence = null;
try { NoteOccurrence = Java.type("com.bitwig.extension.controller.api.NoteOccurrence"); } catch (e) {}

function applyNoteProps(p) {
   var x = Math.round(need(p, "start") / NOTE_STEP), y = need(p, "pitch");
   var st = cursorClip.getStep(p.channel || 0, x, y);
   if (String(st.state()) !== "NoteOn") return false;
   if (p.velocity != null) st.setVelocity(Math.max(1, Math.min(127, p.velocity)) / 127);
   if (p.release_velocity != null) st.setReleaseVelocity(Math.max(0, Math.min(127, p.release_velocity)) / 127);
   if (p.velocity_spread != null) st.setVelocitySpread(clamp01(p.velocity_spread));
   if (p.duration != null) st.setDuration(Math.max(NOTE_STEP / 4, p.duration));
   if (p.gain != null) st.setGain(clamp01(p.gain));
   if (p.pan != null) st.setPan(Math.max(-1, Math.min(1, p.pan)));
   if (p.timbre != null) st.setTimbre(Math.max(-1, Math.min(1, p.timbre)));
   if (p.pressure != null) st.setPressure(clamp01(p.pressure));
   if (p.transpose != null) st.setTranspose(Math.max(-24, Math.min(24, p.transpose)));
   if (p.muted != null) st.setIsMuted(!!p.muted);
   if (p.chance != null) {
      st.setIsChanceEnabled(p.chance < 1);
      if (p.chance < 1) st.setChance(clamp01(p.chance));
   }
   if (p.repeat != null) {
      if (!p.repeat || !p.repeat.count) st.setIsRepeatEnabled(false);
      else {
         st.setIsRepeatEnabled(true);
         st.setRepeatCount(p.repeat.count);
         if (p.repeat.curve != null) st.setRepeatCurve(p.repeat.curve);
         if (p.repeat.velocity_curve != null) st.setRepeatVelocityCurve(p.repeat.velocity_curve);
         if (p.repeat.velocity_end != null) st.setRepeatVelocityEnd(p.repeat.velocity_end);
      }
   }
   if (p.recurrence != null) {
      if (!p.recurrence || !p.recurrence.length) st.setIsRecurrenceEnabled(false);
      else { st.setIsRecurrenceEnabled(true); st.setRecurrence(p.recurrence.length, p.recurrence.mask); }
   }
   if (p.occurrence != null) {
      if (!p.occurrence || p.occurrence === "Always") st.setIsOccurrenceEnabled(false);
      else {
         if (!NoteOccurrence) throw "occurrence conditions are not available in this Bitwig version";
         st.setIsOccurrenceEnabled(true);
         st.setOccurrence(NoteOccurrence.valueOf(String(p.occurrence)));
      }
   }
   return true;
}

var clipLoopStart, clipLoopEnabled, clipShuffle, clipAccent, clipLaunchMode, clipLaunchQuant, clipPlayStart, clipPlayStop;

function initExpert() {
   clipLoopStart = cursorClip.getLoopStart(); interest(clipLoopStart);
   clipLoopEnabled = cursorClip.isLoopEnabled(); interest(clipLoopEnabled);
   clipShuffle = cursorClip.getShuffle(); interest(clipShuffle);
   clipAccent = cursorClip.getAccent(); interest(clipAccent);
   clipPlayStart = cursorClip.getPlayStart(); interest(clipPlayStart);
   clipPlayStop = cursorClip.getPlayStop(); interest(clipPlayStop);
   clipLaunchMode = tryDo("clipLaunchMode", function () { var v = cursorClip.launchMode(); interest(v); return v; });
   clipLaunchQuant = tryDo("clipLaunchQuantization", function () { var v = cursorClip.launchQuantization(); interest(v); return v; });
   interest(cursorClip.color());
}

function clipSettings() {
   return {
      loop_start: clipLoopStart.get(), loop_length: cursorClip.getLoopLength().get(),
      loop_enabled: clipLoopEnabled.get(), play_start: clipPlayStart.get(), play_stop: clipPlayStop.get(),
      shuffle: clipShuffle.get(), accent: r3(clipAccent.get()),
      launch_mode: clipLaunchMode ? clipLaunchMode.get() : null,
      launch_quantization: clipLaunchQuant ? clipLaunchQuant.get() : null
   };
}

function handleExpert(cmd, a) {
   switch (cmd) {
      case "set_note_props": {
         var list = a.notes || [], done = 0, missing = [];
         for (var i = 0; i < list.length; i++) {
            if (applyNoteProps(list[i])) done++;
            else missing.push({ pitch: list[i].pitch, start: list[i].start });
         }
         return { updated: done, not_found: missing };
      }
      case "move_notes": {  // [{start, pitch, d_start, d_pitch}] - Bitwig keeps all expressions
         var mv = a.notes || [];
         for (var m = 0; m < mv.length; m++) {
            cursorClip.moveStep(0, Math.round(mv[m].start / NOTE_STEP), mv[m].pitch,
               Math.round((mv[m].d_start || 0) / NOTE_STEP), mv[m].d_pitch || 0);
         }
         return "moved " + mv.length;
      }
      case "delete_notes": {
         var dl = a.notes || [];
         for (var d = 0; d < dl.length; d++) cursorClip.clearStep(0, Math.round(dl[d].start / NOTE_STEP), dl[d].pitch);
         return "deleted " + dl.length;
      }
      case "get_clip_settings": return clipSettings();
      case "set_clip_settings": {
         if (a.loop_start != null) clipLoopStart.set(a.loop_start);
         if (a.loop_length != null) cursorClip.getLoopLength().set(a.loop_length);
         if (a.loop_enabled != null) clipLoopEnabled.set(!!a.loop_enabled);
         if (a.play_start != null) clipPlayStart.set(a.play_start);
         if (a.play_stop != null) clipPlayStop.set(a.play_stop);
         if (a.shuffle != null) clipShuffle.set(!!a.shuffle);
         if (a.accent != null) clipAccent.setImmediately(clamp01(a.accent));
         if (a.launch_mode != null && clipLaunchMode) clipLaunchMode.set(String(a.launch_mode));
         if (a.launch_quantization != null && clipLaunchQuant) clipLaunchQuant.set(String(a.launch_quantization));
         if (a.name != null) cursorClip.setName(String(a.name));
         if (a.color != null) cursorClip.color().set(a.color[0], a.color[1], a.color[2]);
         return "ok";
      }
      case "show_clip_in_editor": cursorClip.showInEditor(); return "ok";
   }
   return undefined;
}
