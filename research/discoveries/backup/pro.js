// Pro features for the Bitwig MCP bridge: metering, clip note reading, transport/groove, cue markers.
// Loaded by BitwigMCP.control.js; every optional API is wrapped so a missing one never stops the script.

var METER_RANGE = 1000;
var NOTE_STEP = 0.125; // 1/32 note grid used for reading/writing clip notes
var peaks = [], holds = [], masterPeak = 0, masterHold = 0;
var masterTrack, groove, cueBank, loopEnabled, loopStart, loopLength, tsNum, tsDen, launchQuant, punchIn, punchOut;
var clipNotes = {};
var mPeakL = 0, mPeakR = 0, mRmsL = 0, mRmsR = 0, mHoldL = 0, mHoldR = 0;
var noteEvents = 0, lastState = null, focusedClip = null;
var autoWrite, autoMode, arrRec, tsObj;

function tryDo(label, fn) {
   try { return fn(); } catch (e) { missingApis.push(label); return null; }
}

function initPro() {
   for (var t = 0; t < NUM_TRACKS; t++) {
      peaks.push(0); holds.push(0);
      (function (i) {
         tryDo("vuMeter", function () {
            trackBank.getItemAt(i).addVuMeterObserver(METER_RANGE, -1, true, function (v) {
               peaks[i] = v / METER_RANGE;
               if (peaks[i] > holds[i]) holds[i] = peaks[i];
            });
         });
      })(t);
   }
   masterTrack = host.createMasterTrack(0);
   interest(masterTrack.volume().value()); interest(masterTrack.volume().displayedValue());
   // Per-channel master meters (0 = left, 1 = right), peak and RMS.
   tryDo("masterStereoMeters", function () {
      masterTrack.addVuMeterObserver(METER_RANGE, 0, true, function (v) { mPeakL = v / METER_RANGE; if (mPeakL > mHoldL) mHoldL = mPeakL; });
      masterTrack.addVuMeterObserver(METER_RANGE, 1, true, function (v) { mPeakR = v / METER_RANGE; if (mPeakR > mHoldR) mHoldR = mPeakR; });
      masterTrack.addVuMeterObserver(METER_RANGE, 0, false, function (v) { mRmsL = v / METER_RANGE; });
      masterTrack.addVuMeterObserver(METER_RANGE, 1, false, function (v) { mRmsR = v / METER_RANGE; });
   });
   tryDo("masterVuMeter", function () {
      masterTrack.addVuMeterObserver(METER_RANGE, -1, true, function (v) {
         masterPeak = v / METER_RANGE;
         if (masterPeak > masterHold) masterHold = masterPeak;
      });
   });

   // Clip notes: Bitwig re-reports every note whenever the cursor clip or its grid changes.
   cursorClip.setStepSize(NOTE_STEP);
   cursorClip.scrollToKey(0);
   cursorClip.scrollToStep(0);
   tryDo("noteStepObserver", function () {
      cursorClip.addNoteStepObserver(function (step) {
         noteEvents++; lastState = String(step.state());
         var key = step.x() + ":" + step.y();
         if (String(step.state()) === "NoteOn")
            clipNotes[key] = noteRecord(step);  // defined in expert.js
         else delete clipNotes[key];
      });
   });

   loopEnabled = opt(transport, ["isArrangerLoopEnabled", "isArrangementLoopEnabled"]);
   loopStart = opt(transport, ["arrangerLoopStart", "arrangementLoopStart"]);
   loopLength = opt(transport, ["arrangerLoopDuration", "arrangementLoopDuration"]);
   punchIn = opt(transport, ["isPunchInEnabled"]);
   punchOut = opt(transport, ["isPunchOutEnabled"]);
   launchQuant = opt(transport, ["defaultLaunchQuantization"]);
   tsObj = opt(transport, ["timeSignature", "getTimeSignature"]);
   var ts = tsObj;
   autoWrite = opt(transport, ["isArrangerAutomationWriteEnabled"]);
   autoMode = opt(transport, ["automationWriteMode"]);
   arrRec = opt(transport, ["isArrangerRecordEnabled"]);
   if (ts) {
      tsNum = opt(ts, ["numerator", "getNumerator"]);
      tsDen = opt(ts, ["denominator", "getDenominator"]);
   }
   var vals = [autoWrite, autoMode, arrRec, loopEnabled, loopStart, loopLength, punchIn, punchOut, launchQuant, tsNum, tsDen];
   for (var v = 0; v < vals.length; v++) if (vals[v]) interest(vals[v]);

   groove = tryDo("groove", function () { return host.createGroove(); });
   if (groove) {
      var gp = [groove.getEnabled(), groove.getShuffleAmount(), groove.getShuffleRate(),
                groove.getAccentAmount(), groove.getAccentRate(), groove.getAccentPhase()];
      for (var g = 0; g < gp.length; g++) { interest(gp[g].value()); interest(gp[g].displayedValue()); }
   }

   cueBank = tryDo("cueMarkers", function () { return host.createArranger().createCueMarkerBank(32); });
   if (cueBank) {
      for (var m = 0; m < 32; m++) {
         var mk = cueBank.getItemAt(m);
         interest(mk.exists()); interest(mk.getName()); interest(mk.position());
      }
   }
}

function grooveState() {
   if (!groove) return null;
   function p(x) { return { value: x.value().get(), display: x.displayedValue().get() }; }
   return { enabled: p(groove.getEnabled()), shuffle_amount: p(groove.getShuffleAmount()),
            shuffle_rate: p(groove.getShuffleRate()), accent_amount: p(groove.getAccentAmount()),
            accent_rate: p(groove.getAccentRate()), accent_phase: p(groove.getAccentPhase()) };
}

function handlePro(cmd, a) {
   switch (cmd) {
      // --- Metering ---
      case "get_meters": {
         var out = [];
         for (var t = 0; t < NUM_TRACKS; t++) {
            var tr = trackBank.getItemAt(t);
            if (tr.exists().get())
               out.push({ index: t, name: tr.name().get(), peak: peaks[t], hold: holds[t],
                          volume_display: tr.volume().displayedValue().get(), muted: tr.mute().get() });
         }
         return { tracks: out, master: { peak: masterPeak, hold: masterHold,
                  volume_display: masterTrack.volume().displayedValue().get() },
                  playing: transport.isPlaying().get() };
      }
      case "reset_meters":
         for (var i = 0; i < holds.length; i++) holds[i] = 0;
         masterHold = 0;
         return "ok";
      case "set_master_volume": masterTrack.volume().setImmediately(clamp01(a.value)); return "ok";

      // --- Clip notes ---
      case "focus_clip": {
         var trf = track(need(a, "track_index"));
         var slot = slotOf(trf, need(a, "slot"));
         if (!slot.hasContent().get()) throw "no clip in track " + a.track_index + " slot " + a.slot;
         // The note map tracks whatever clip the cursor shows, on one fixed grid. Only reset it
         // when switching clips; re-focusing the same clip fires no events, so keep its notes.
         var id = a.track_index + "/" + a.slot;
         if (id !== focusedClip) clipNotes = {};
         focusedClip = id;
         cursorTrack.selectChannel(trf);
         host.scheduleTask(function () {
            slot.select();
            // Scroll the grid to an empty region far past any content and back. Every note cell then
            // goes NoteOn -> Empty -> NoteOn, so Bitwig re-reports all of them. (A one-step nudge
            // misses neighbouring notes of the same pitch, whose cells never change state.)
            cursorClip.scrollToStep(1000000);
            host.scheduleTask(function () {
               clipNotes = {};
               cursorClip.scrollToStep(0);
            }, 150);
         }, 150);
         return "ok";
      }
      case "get_notes": {
         var list = [];
         for (var k in clipNotes) list.push(clipNotes[k]);
         list.sort(function (x, y) { return x.start - y.start || x.pitch - y.pitch; });
         // Paged so replies stay well under the UDP packet limit.
         var off = a.offset || 0, lim = a.limit || 120;
         return { notes: list.slice(off, off + lim), total: list.length, offset: off,
                  loop_length: cursorClip.getLoopLength().get() };
      }
      case "quantize_clip": cursorClip.quantize(clamp01(a.amount == null ? 1 : a.amount)); return "ok";
      case "duplicate_clip_content": cursorClip.duplicateContent(); return "ok";

      // --- Transport & groove ---
      case "get_transport": {
         var cues = [];
         if (cueBank) for (var m = 0; m < 32; m++) {
            var mk = cueBank.getItemAt(m);
            if (mk.exists().get()) cues.push({ index: m, name: mk.getName().get(), position: mk.position().get() });
         }
         return {
            tempo: transport.tempo().value().getRaw(), playing: transport.isPlaying().get(),
            position: transport.getPosition().get(),
            time_signature: tsNum && tsDen ? tsNum.get() + "/" + tsDen.get() : null,
            loop: loopEnabled ? { enabled: loopEnabled.get(), start: loopStart ? loopStart.get() : null,
                                  length: loopLength ? loopLength.get() : null } : null,
            arranger_record: arrRec ? arrRec.get() : null,
            automation_write: autoWrite ? autoWrite.get() : null, automation_mode: autoMode ? autoMode.get() : null,
            punch_in: punchIn ? punchIn.get() : null, punch_out: punchOut ? punchOut.get() : null,
            launch_quantization: launchQuant ? launchQuant.get() : null,
            groove: grooveState(), cue_markers: cues, missing_apis: missingApis
         };
      }
      case "set_loop":
         if (!loopEnabled) throw "arrangement loop not supported by this Bitwig API";
         if (a.start != null && loopStart) loopStart.set(a.start);
         if (a.length != null && loopLength) loopLength.set(a.length);
         if (a.enabled != null) loopEnabled.set(!!a.enabled);
         return "ok";
      case "set_time_signature":
         if (!tsNum) throw "time signature not supported by this Bitwig API";
         var num = need(a, "numerator"), den = a.denominator || 4;
         try { tsObj.set(num + "/" + den); }
         catch (e) {
            tsNum.set(num);
            try { tsDen.set(den); } catch (e2) { throw "this Bitwig version only lets scripts set the numerator (" + e2 + ")"; }
         }
         return "ok";
      case "set_punch":
         if (a.punch_in != null && punchIn) punchIn.set(!!a.punch_in);
         if (a.punch_out != null && punchOut) punchOut.set(!!a.punch_out);
         return "ok";
      case "set_launch_quantization":
         if (!launchQuant) throw "launch quantization not supported by this Bitwig API";
         launchQuant.set(String(need(a, "value"))); return "ok";
      case "set_groove": {
         if (!groove) throw "groove not supported by this Bitwig API";
         var map = { enabled: groove.getEnabled(), shuffle_amount: groove.getShuffleAmount(),
                     shuffle_rate: groove.getShuffleRate(), accent_amount: groove.getAccentAmount(),
                     accent_rate: groove.getAccentRate(), accent_phase: groove.getAccentPhase() };
         for (var key in map) if (a[key] != null) map[key].setImmediately(clamp01(a[key]));
         return grooveState();
      }
      case "set_automation": {
         if (a.write != null && autoWrite) autoWrite.set(!!a.write);
         if (a.mode && autoMode) autoMode.set(String(a.mode)); // latch, touch, write
         return "ok";
      }
      case "set_arranger_record": if (!arrRec) throw "not supported"; arrRec.set(!!a.enabled); return "ok";
      case "add_cue_marker": transport.addCueMarkerAtPlaybackPosition(); return "ok";
      case "launch_cue_marker": {
         if (!cueBank) throw "cue markers not supported by this Bitwig API";
         cueBank.getItemAt(need(a, "index")).launch(true); return "ok";
      }
      case "debug_methods": {
         var obj = a.target === "application" ? application : transport, names = [];
         for (var k in obj) names.push(k);
         if (!names.length) try { var ms = obj.getClass().getMethods(); for (var j = 0; j < ms.length; j++) names.push(String(ms[j].getName())); } catch (e) { names.push("reflect failed: " + e); }
         return names;
      }
      case "select_master": cursorTrack.selectChannel(masterTrack); return "ok";
      case "get_master_meters": {
         return { left: { peak: mPeakL, rms: mRmsL }, right: { peak: mPeakR, rms: mRmsR },
                  hold_left: mHoldL, hold_right: mHoldR };
      }
      case "reset_master_meters": mHoldL = 0; mHoldR = 0; return "ok";
      case "debug_track_methods": {
         var tr = trackBank.getItemAt(need(a, "track_index")), names = [];
         for (var k in tr) names.push(k);
         return names;
      }
      case "debug_notestep": {
         var st = cursorClip.getStep(0, need(a, "x"), need(a, "y")), names = [];
         for (var k in st) names.push(k);
         var cnames = [];
         for (var k2 in cursorClip) cnames.push(k2);
         return { state: String(st.state()), step: names, clip: cnames };
      }
      case "tap_tempo": transport.tapTempo(); return "ok";
      case "save_project": {
         var act = application.getAction("Save");
         if (!act) throw "Save action not available";
         act.invoke(); return "ok";
      }
   }
   return undefined;
}
